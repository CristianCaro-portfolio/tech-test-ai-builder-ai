# AI Builder (AI) — Technical Assessment

**Time limit:** 3 hours max.

---

## Context

**Twin Hearth Studios** runs player support for *Hollow Crown*. Agents answer the same questions
over and over from a pile of internal docs: patch notes, refund policy, account recovery runbooks,
and a moderation handbook.

A previous contractor left a **working but naive RAG assistant** in `baseline/`. It answers. It is
also wrong often enough that support stopped trusting it, and nobody can say *how* wrong, because
there is no evaluation.

Your job is not to rebuild it from scratch. Your job is to **measure it, fix what the numbers say
is broken, and prove the fix**.

## What you're given

```
data/corpus/        4 support documents (markdown), the knowledge base
data/golden.json    22 question/answer pairs with the source doc each answer must come from
eval/run_eval.py    a runnable evaluator: retrieval hit-rate, answer accuracy, latency, token cost
baseline/           the naive RAG assistant (Python, ~150 lines, deliberately mediocre)
```

Run the baseline before you change anything:

```bash
python3 eval/run_eval.py --pipeline baseline
```

Write that number down. It is your starting point.

> The evaluator is given to you so you don't spend the 3 hours building scaffolding. Extend it,
> replace it, or drive it from your own harness — but your final numbers must be reproducible by
> someone running one command.

---

## What to deliver

### 1. A better pipeline

Improve retrieval and answer quality. The baseline has real, findable defects — find them with the
eval, not by guessing. Areas that are fair game:

- Chunking strategy (the baseline's is bad; you should be able to show *why* with a number)
- Embeddings and vector search
- Reranking
- Query handling
- Prompting and context assembly

### 2. Agent behaviour

At least one question in the golden set cannot be answered from the corpus alone — it needs a tool
call. Add tool/function calling for it, and make the agent behave when things go wrong:

- The tool must be able to fail. Handle retries and give up cleanly.
- The agent must **refuse to answer** when retrieval returns nothing relevant. A confident wrong
  answer scores worse than "I don't know."
- Multi-step questions must not lose state mid-run.

### 3. Sensitive data

Support tickets in this corpus contain player emails, real names, and — in one case — data
belonging to a minor's account. Studio policy: **that data must never reach a third-party model
provider.** Implement it. Show it works.

### 4. `DECISIONS.md`

Short. No essays. For each significant change:

| Change | Why | Metric before → after |
|---|---|---|

Plus:
- **One thing you tried that made it worse**, with the number that told you so.
- Cost and latency per query, before and after.
- What you would do next with 3 more hours, and why that and not something else.

### 5. `STACK.md` — what you'd build with code, and what you wouldn't

Half of this job is deciding what *not* to write. Support here already runs on off-the-shelf
tooling; the studio does not want a bespoke service for something a workflow tool does in an hour,
and it does not want a critical path living inside a drag-and-drop canvas either.

Answer, for the assistant you just built, as if it were going to production:

1. **The stack you'd actually ship it on.** Languages, framework, vector store, model(s), hosting.
   Not what you used for a 3-hour test — what you'd defend in a design review, and what changes
   between the two.

2. **The code / no-code line.** Draw it explicitly. Which parts belong in workflow tooling (n8n,
   Make, Zapier, or similar), which parts must be code, and **why the line falls there**. Name the
   property that decides it — not "it's more professional."

3. **One thing you'd deliberately keep no-code**, even though you could write it. And **one thing
   you'd refuse to leave in no-code**, with the failure mode that would eventually bite.

4. **Where an LLM should not be involved at all.** The refund-window arithmetic in this corpus is a
   fair example — point at the others.

5. **Who maintains it in six months**, and what that assumption does to every choice above.

One page. Bullets are fine. We care about the reasoning, not the word count.

### 6. `AI_WORKFLOW.md`

How you used AI coding tools during this assessment:

1. Which tool(s) and why.
2. 3–5 concrete prompts and their outcome.
3. One moment where the AI got it wrong and how you caught it.
4. If you used parallel agents / subagents / worktrees, describe how.

---

## Running the submission

```bash
python3 eval/run_eval.py --pipeline baseline      # starting point
python3 eval/run_eval.py --pipeline hollow        # improved pipeline, offline and deterministic
python3 -m unittest discover -s tests             # redaction, tool failure, refusal, state
docker compose up                                 # tests + both evals in a container
```

No dependencies beyond the standard library. Set one provider key in `.env` (see `.env.example`)
to switch synthesis to an LLM with function calling; `TOOL_FAILURE_RATE=0.5` makes the simulated
deployment API flaky to watch the retry path. Layout: `hollow/chunking.py` (section and table-row
chunks), `hollow/retrieval.py` (BM25 with a relevance gate), `hollow/redaction.py` (Restricted data
never enters the index), `hollow/tools.py` (patch status, refund arithmetic, retries),
`hollow/agent.py` (the loop). See `DECISIONS.md`, `STACK.md`, `AI_WORKFLOW.md`.

## Stack

**Your choice of language.** Python, Node/TypeScript, Go — whatever you ship fastest in. The
baseline is Python; porting it is allowed but not rewarded.

Node.js/TypeScript, and NestJS in particular, are a **plus** — this is what the team builds on.

- LLM provider: your choice (Anthropic, OpenAI, Gemini, OpenRouter, local). Free tiers are fine.
- Vector store: your choice (pgvector, Qdrant, Chroma, FAISS, in-memory).
- If it needs a key, put it in `.env.example` and say which model you ran against.

**Docker:** ship a `Dockerfile` or `compose.yml` such that `docker compose up` runs the eval. This
is part of the grade.

## Out of scope

Auth, a UI, deployment, CI, full test coverage. Nobody is grading your frontend — there isn't one.

---

## Evaluation

| Area | Weight |
|---|---|
| Measured improvement over baseline (retrieval + accuracy, reproducible) | 25% |
| Engineering judgment in `DECISIONS.md` (incl. the thing that made it worse) | 20% |
| Agent robustness: tool calling, failure handling, refusal behaviour | 20% |
| Stack + code / no-code reasoning (`STACK.md`) | 10% |
| Sensitive-data handling | 10% |
| Use of AI coding tools (`AI_WORKFLOW.md`) | 10% |
| Containerization + reproducibility | 5% |

Two things that will sink an otherwise good submission:

- **Numbers you can't reproduce.** If we run your command and get something different, the 25%
  goes to zero.
- **A pipeline that got better on the golden set by reading the golden set.** Don't tune against
  the answers.

---

## How to submit

1. **Fork** this repo.
2. Create branch `submission/<your-name>`.
3. Implement.
4. Open a **Pull Request** to `main` of this repo.
5. In the PR include: time spent, how to run, your before/after numbers, trade-offs made.

Expect to defend these numbers live.
