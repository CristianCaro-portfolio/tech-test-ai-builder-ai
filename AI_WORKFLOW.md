# AI workflow

## 1. Tools

An agentic coding assistant (terminal based, with file editing and shell access) as the main
driver, plus the eval script as the judge of every change. I chose an agent over autocomplete
because the loop here is "change one thing, rerun the eval, read the failures", and an agent can run
that loop itself while I read the corpus and write the docs. No IDE plugins, no separate chat
window: one session, the repo as shared state.

## 2. Prompts and outcomes

1. *"Run the baseline eval and explain each failure in terms of the chunk that was retrieved."*
   Outcome: the agent grouped the 14 failures into three causes (chunks cut mid-sentence, tables
   split, no IDF) before any code was written. That grouping became the change table in
   DECISIONS.md.
2. *"Replace the chunker with section-level chunks keyed on `##` headings, keep tables intact,
   prefix the heading. Do not touch the scorer yet."* Outcome: retrieval went from 65% to 85% and
   accuracy from 36% to 50% with the baseline scorer and k=1 still in place, which isolated
   chunking as the first lever and left the scorer as the next one.
3. *"Add a relevance gate so the pipeline refuses on q21 without reading golden.json. Use a
   property of the query, not a keyword."* Outcome: the first attempt computed coverage only over
   terms present in the corpus, which made every question look fully covered (see section 3).
   The fix, unknown terms get maximum IDF, came from asking it to print the score per question.
4. *"Write tests that prove no restricted value can reach a provider, without listing the values
   in the pipeline code."* Outcome: pattern-based redaction at ingest and a test that asserts the
   whole index is clean against the eval's own restricted list.
5. *"Run these ablations and give me the numbers: fixed chunks, k=1, no per-doc cap, no restricted
   penalty, gate at 0.6, no stopwords."* Outcome: the "made it worse" section, and the discovery
   that the per-doc cap only matters at k=4.

## 3. Where it was wrong and how I caught it

The first coverage metric filtered query terms to those already in the index, so "concurrent" and
"August" were simply dropped and q21 scored coverage 1.0, identical to real questions. The eval
still showed 0% refusals, which is what flagged it; printing coverage per question showed no
separation at all between q21 and the rest. The fix was to treat unknown terms as the most
informative ones rather than ignoring them. Lesson: a gate that ignores exactly the signal it is
supposed to detect will look fine on every metric except the one it exists for.

The runtime model got one wrong too: on the first LLM-mode run it answered the Season Pass
question with a flat "not eligible" while the outage exception sat in its context. The eval caught
it; the fix was a general rule in the system prompt (check every exception and use a tool for date
arithmetic before saying no), verified across three identical runs.

A second, smaller one: the first PII-request regex matched "change the email on an account" (q12)
as a data request and refused a legitimate policy question. Caught by the accuracy drop on the very
next eval run; the pattern now requires an asking verb before the identifier.

## 4. Parallelism

None. The whole loop is a two-second eval, so there was nothing to parallelise; a second agent
would have spent its time merging. Where I would use worktrees: the LLM-mode eval against two
providers at once, because that loop is minutes, not seconds.
