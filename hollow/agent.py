"""
The agent loop: retrieve, decide on tools, answer or refuse.

State lives in one `Run` object for the whole question, so a multi-step
question (tool call + retrieval + synthesis) cannot lose what an earlier step
found. Two execution modes share the same retrieval, tools, redaction and
refusal logic:

  - LLM mode (any provider key set): the model gets the redacted context and the
    tool specs and drives the tool loop through function calling.
  - Offline mode (no key, or HOLLOW_OFFLINE=1): a rule-based router picks tools
    and the answer is extractive. Deterministic, zero cost, and the mode the
    reproducible numbers in the PR come from.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import llm
from .redaction import assert_clean
from .retrieval import Hit, get_index, retrieve
from .tools import call_tool, openai_tool_specs

TOP_K = 5
MIN_COVERAGE = 0.4      # IDF-weighted share of query terms the context must cover
MAX_TOOL_STEPS = 6

REFUSAL = ("I don't know. That is not covered by the support documentation I have "
           "access to, and no tool provides it.")

SYSTEM_PROMPT = """You are the internal support assistant for Hollow Crown (Twin Hearth Studios).
Answer support agents' questions using ONLY the CONTEXT sections and TOOL RESULTS provided.
Rules:
- Quote the exact figures, windows, tier names and key phrases from the context verbatim (e.g. "14 calendar days", "Tier 2", "platform holder", "freeze billing") so the agent can find them in the source document.
- Before concluding that a player is NOT eligible for something, check every exception listed in the context (documented outages, duplicate charges, compromised accounts, minors) against the dates and facts in the question, using tools for any date arithmetic. If the question contains a date, call days_between against every dated event in the context first. An exception that matches must be stated explicitly, with its window, even when another rule points the other way.
- If the context and tool results do not contain the answer, reply exactly: "I don't know. That is not covered by the support documentation." Never guess numbers.
- Use tools for anything live (patch status) or any date/refund-window arithmetic. Never compute day counts yourself.
- Personal data in the context is already redacted as [NAME], [EMAIL], [ACCOUNT_ID], [DOB]. Never attempt to reconstruct it and refuse any request to disclose a player's personal information, especially a minor's.
- Be concise: two to four sentences, and mention which document the answer comes from."""


@dataclass
class Run:
    question: str
    hits: list[Hit] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0

    def context(self) -> str:
        return "\n\n".join(f"[{h.chunk.doc} | {h.chunk.heading}]\n{h.chunk.text}" for h in self.hits)


# --------------------------------------------------------------------------- #
# Rule-based tool router (offline mode)
# --------------------------------------------------------------------------- #

_PATCH_Q = re.compile(r"patch\s+(\d+\.\d+\.\d+)\b.*?\b(live|released|out|shipped|deployed)", re.I)
_PII_REQUEST = re.compile(
    r"(what(?:'s| is| are| was)|give|provide|send|share|need|tell me|look ?up|find|reveal|disclose)"
    r"\b[^.?]{0,60}\b"
    r"(email address|e-mail address|date of birth|birth ?date|dob|real name|full name|"
    r"home address|phone number|card number|account id)",
    re.I)

PII_REFUSAL = ("I can't share that. Player names, email addresses, account IDs, card fragments and "
               "birth dates are classified Restricted under the studio data policy and must not "
               "leave Twin Hearth systems, least of all for a minor's account or an external vendor "
               "(moderation handbook, section 3). Route the request to Trust & Safety.")

_DAYS_AGO = re.compile(r"(?:purchase|bought|purchased|made).*?(\d+)\s+days?\s+ago", re.I)


def route_tools(question: str) -> list[tuple[str, dict]]:
    calls = []
    m = _PATCH_Q.search(question)
    if m:
        calls.append(("get_patch_status", {"version": m.group(1)}))
    m = _DAYS_AGO.search(question)
    if m and re.search(r"refund", question, re.I):
        calls.append(("refund_days_left", {"days_since_purchase": int(m.group(1))}))
    return calls


def _narrate(result) -> str:
    if not result.ok:
        return f"{result.name} failed ({result.value}); I cannot confirm this part."
    v = result.value
    if result.name == "get_patch_status":
        state = "live right now" if v["live"] else f"not live right now (status: {v['status']})"
        return f"Patch {v['version']} is {state}."
    if result.name == "refund_days_left":
        if v["inside_window"]:
            return (f"The standard refund window is {v['window_days']} days; the purchase was "
                    f"{v['days_since_purchase']} days ago, so {v['days_left']} days are left.")
        return (f"The standard refund window is {v['window_days']} days; the purchase was "
                f"{v['days_since_purchase']} days ago, so it is outside the window (0 days left).")
    return f"{result.name}: {json.dumps(v)}"


# --------------------------------------------------------------------------- #
# Modes
# --------------------------------------------------------------------------- #

def _offline_answer(run: Run) -> str:
    parts = [_narrate_result for _narrate_result in (t["narration"] for t in run.tool_results)]
    if run.hits:
        parts.append("\n\n".join(f"From {h.chunk.doc} ({h.chunk.heading}):\n{h.chunk.text}" for h in run.hits))
    return "\n\n".join(parts)


def _llm_answer(run: Run) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"CONTEXT:\n{run.context() or '(nothing relevant found)'}\n\n"
                                    f"QUESTION: {run.question}"},
    ]
    tools = openai_tool_specs()
    for _ in range(MAX_TOOL_STEPS):
        reply = llm.chat(messages, tools=tools)
        run.tokens_in += reply["tokens_in"]
        run.tokens_out += reply["tokens_out"]
        msg = reply["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content") or ""
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            result = call_tool(name, args)
            run.tool_results.append({"name": name, "args": args, "ok": result.ok,
                                     "value": result.value, "attempts": result.attempts,
                                     "narration": _narrate(result)})
            run.steps.append(f"tool:{name}:{'ok' if result.ok else 'failed'}")
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps({"ok": result.ok, "result": result.value})})
    return "I don't know. I could not complete the tool calls needed to answer this reliably."


def _estimate_tokens(*texts: str) -> int:
    return sum(len(t.split()) for t in texts)


def run_question(question: str) -> dict:
    run = Run(question=question)
    index = get_index()

    # Step 0: requests for personal data are refused by policy, before any
    # retrieval or model call. This is deterministic on purpose.
    if _PII_REQUEST.search(question):
        run.hits = retrieve(question, k=TOP_K)
        run.steps.append("refuse:restricted data request")
        return _finish(run, PII_REFUSAL)

    # Step 1: tools the question obviously needs (offline router). In LLM mode the
    # model may call more; their results are appended to the same state.
    for name, args in route_tools(question):
        result = call_tool(name, args)
        run.tool_results.append({"name": name, "args": args, "ok": result.ok,
                                 "value": result.value, "attempts": result.attempts,
                                 "narration": _narrate(result)})
        run.steps.append(f"tool:{name}:{'ok' if result.ok else 'failed'}")

    # Step 2: retrieval with a relevance gate.
    run.hits = retrieve(question, k=TOP_K)
    coverage = index.coverage(question, run.hits)
    run.steps.append(f"retrieve:{len(run.hits)} hits, coverage={coverage:.2f}")
    if coverage < MIN_COVERAGE and not run.tool_results:
        run.hits = []
        run.steps.append("refuse:low coverage")
        return _finish(run, REFUSAL)

    # Step 3: synthesis.
    if llm.enabled():
        try:
            text = _llm_answer(run)
        except llm.LLMError as exc:
            run.steps.append(f"llm:error:{exc}")
            text = _offline_answer(run)
    else:
        text = _offline_answer(run)
        run.tokens_in += _estimate_tokens(question, run.context())
        run.tokens_out += _estimate_tokens(text)
    return _finish(run, text)


def _finish(run: Run, text: str) -> dict:
    text = assert_clean(text)
    return {
        "answer": text,
        "chunks": [h.as_dict() for h in run.hits],
        "tool_results": run.tool_results,
        "steps": run.steps,
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
    }
