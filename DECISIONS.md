# Decisions

Everything below was measured with `python3 eval/run_eval.py --pipeline hollow` in offline mode
(no provider key). Same command inside `docker compose up`. The pipeline is deterministic, so the
numbers are stable run to run.

## Baseline

```
retrieval hit-rate   65.0%    answer accuracy 36.4%    correct refusals 0%
restricted leaks     0        tokens ~148 / query      latency ~0 ms
```

The baseline leaks nothing only because the golden set never lands on the two worked-example
chunks. Retrieval alone would have sent player emails and a minor's birth date to a provider.

## Changes

| Change | Why | Metric before -> after |
|---|---|---|
| Section chunking (split on `##`, heading prefixed) instead of fixed 400-char windows | 400-char slices cut the 30-day / 90-day facts in q09 into different chunks and split every table. Sections keep the rule and its exception together. | with the baseline scorer and k=1: retrieval 65% -> 85%, accuracy 36.4% -> 50%. With BM25 at k=5: accuracy 77.3% (fixed windows) -> 95.5% (sections) |
| Table rows exploded into one chunk each, prefixed with the header cells | A 7-row table is one long chunk; BM25 length normalisation buries the one row the question is about (Crown Tokens, Email change). | accuracy 95.5% -> 100% (q03 and q12 recover) |
| BM25 (IDF + length norm + light stemming + stopwords) instead of raw term-frequency cosine | In the baseline "the" weighs as much as "chargeback". | retrieval 65% -> 100% (together with chunking) |
| top_k 1 -> 5 with at most 2 chunks per document | Multi-hop questions need two documents; k=1 cannot represent them. The per-doc cap stops four refund sections from crowding out the patch note. | retrieval 80% -> 100%, accuracy 77.3% -> 100% (k=1 vs k=5) |
| Relevance gate: refuse when IDF-weighted query coverage < 0.4 | Unknown terms ("concurrent", "August") get the top IDF and are never covered, so a question the corpus cannot answer scores low even when it shares "Hollow Crown" with every chunk. | correct refusals 0% -> 100%, no loss elsewhere |
| Tool calling with retries (`get_patch_status`, `refund_days_left`) | q20 needs live patch status and date arithmetic. Arithmetic is code, never the model. The deployment API can fail (`TOOL_FAILURE_RATE`); the caller retries 3x with backoff and reports "cannot confirm" instead of guessing. | q20 0 -> 1; tests cover the give-up path |
| Redaction at ingest + output guard + deterministic PII-request refusal | Policy says Restricted data must not leave the studio. Redacting before indexing means no code path can send it; the output guard catches a model that reconstructs it; a request for a player's email / DOB is refused before any model call. | leaks 0 -> 0, but now provably (tests assert the index contains none of the 10 restricted values) |
| Restricted worked examples ranked at 0.5x | They are training material, not policy. Policy sections should answer policy questions. | no metric change at k=5; keeps redacted PII chunks out of most prompts |

## One thing that made it worse

Removing the stopword list (indexing every token) dropped accuracy from 100% to 90.9%. "How",
"long", "player" and "support" appear in every section, and with BM25 they still add enough noise
to push the Appeals and Two-factor sections below neighbouring ones. IDF alone does not fix it on a
48-chunk index because the document frequencies are too small to separate common from useless.

Two smaller ones: a coverage gate of 0.6 refused q04 ("who receives the money", where "money" is
not in the corpus) and cost 5 points; k=4 with the per-doc cap lost the refund exception section
on q17 (95.5%), k=5 fixed it.

## LLM mode

Same pipeline with `ANTHROPIC_API_KEY` set and `MODEL=claude-haiku-4-5` (Anthropic's
OpenAI-compatible endpoint, temperature 0, function calling for the tools):

```
retrieval hit-rate   100.0%    answer accuracy 100.0%    correct refusals 100%
restricted leaks     0         tokens ~1,640 in / ~80 out per query
latency p50 / p95    1.2 s / 2.0 s
```

Three runs in a row gave identical accuracy; token counts vary by a few units. With
`TOOL_FAILURE_RATE=0.6` the deployment API fails on more than half of the calls and accuracy stays
at 100% because the retry loop absorbs it.

Two prompt iterations were needed, both measured:

- First run scored 86.4%. q07 and q11 were semantically right ("redirect to PlayStation's support
  team", "billing must be frozen") but paraphrased the policy terms the eval looks for. Asking the
  model to quote key phrases verbatim, so agents can find them in the source, fixed both. This is
  a metric artefact worth knowing about: substring matching punishes good paraphrase.
- q16 was a real reasoning miss: the model saw "tier claimed, forfeited" and stopped, ignoring the
  outage exception sitting in the same context. The fix was a general rule (check every exception
  and run date arithmetic through a tool before saying no), not a hint about outages. 95.5% -> 100%.

## Cost and latency per query

| | Baseline | Mine, offline | Mine, LLM mode (claude-haiku-4-5) |
|---|---|---|---|
| Tokens per query | ~148 | ~592 (context handed to the answer) | ~1,640 in / ~80 out |
| Cost per query | 0 | 0 | ~0.002 USD (1 / 5 USD per M tokens) |
| Latency p50 | < 1 ms | ~1 ms | 1.2 s, one to three provider round trips |

The offline mode is what `docker compose up` runs with no key and is byte-for-byte deterministic.
LLM mode uses the same retrieval, tools, redaction and refusal logic; the model only drives
synthesis and function-call selection, which is why the two modes agree on retrieval, refusal and
leaks and differ only in how the answer is written.

## Next 3 hours

1. **An LLM-judged accuracy metric.** `must_contain` substring matching rewards extractive answers
   and cannot tell a correct sentence from a chunk dump. This is the single biggest gap between
   the metric and what support agents experience, so it comes first.
2. **A held-out question set written by a support agent**, not by me, to check the gate threshold
   and the stopword list are not overfit to 22 questions.
3. **Hybrid retrieval (BM25 + embeddings, reciprocal rank fusion)** only after the corpus grows.
   At 4 documents and 48 chunks there is nothing left to gain on this metric, and an embedding
   dependency adds a key, a network hop and non-determinism to the eval.

Not next: a reranker or a vector database. Both solve scale problems this corpus does not have.
