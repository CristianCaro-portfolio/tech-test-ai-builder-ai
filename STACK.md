# Stack

## 1. What I would ship

- **Language / framework:** TypeScript on NestJS. The team builds on it, and the pieces that matter
  here (tool schemas, retries, redaction, an eval harness) are typed contracts, which is where
  TypeScript pays for itself. The Python in this repo exists because the evaluator is Python and
  three hours do not buy a port. What changes: the pipeline becomes a Nest module with three
  providers (retriever, tools, guard), the eval becomes a Jest suite against the same module.
- **Retrieval:** Postgres with pgvector plus its built-in full-text search, hybrid scoring with
  reciprocal rank fusion. One database the studio already runs, no new operational surface.
  Section-level chunking with table rows exploded, exactly as here; that decision is corpus
  shaped, not tool shaped.
- **Models:** a small fast model (Haiku class or gpt-4o-mini class) for synthesis, function calling
  enabled, temperature 0. Embeddings from the same provider to keep one vendor contract. No fine
  tuning; the corpus changes every patch.
- **Hosting:** one container on the studio's existing platform (ECS, Cloud Run, whatever runs the
  rest of support), behind the ticketing tool, not player facing. Provider keys in the secret
  manager, never in the container image.
- **Observability:** every answer logged with the chunk ids, tool calls, gate score and model
  version, so a wrong answer can be replayed. This is the piece that turns "support stopped
  trusting it" into a ticket with a cause.

## 2. The code / no-code line

The deciding property is **whether a mistake is silent**. If a step failing produces an obvious
error a human sees immediately, it can live in a workflow tool. If it can fail quietly and still
look like a valid output, it must be code with tests.

- **Workflow tooling (n8n, Make, Zapier):** ticket intake from the help desk, routing the question
  to the assistant's HTTP endpoint, posting the draft answer back as an internal note, nightly
  re-index trigger when a corpus document changes, Slack alert when the eval score drops. These are
  glue with visible failure modes and they change often; a support lead can edit them.
- **Code:** chunking, retrieval, the relevance gate, redaction, tool execution with retries, the
  refund arithmetic, the eval harness. Each of these can be wrong while producing plausible
  output. They need unit tests, version control and a reproducible score.

## 3. One thing kept no-code, one thing refused

- **Keep no-code:** the ticket-to-assistant-to-ticket loop and the alerting. I could write it in an
  afternoon, but then every change to the help desk's webhook format becomes a deploy, and the
  people who know the help desk best cannot touch it.
- **Refuse to leave in no-code:** redaction. A canvas node that "removes emails with a regex" looks
  finished, silently misses the account ID format the next runbook version introduces, and the
  first sign is a minor's birth date in a vendor's logs. Redaction needs tests that fail the build
  when the corpus gains a new identifier pattern.

## 4. Where an LLM should not be involved

- Refund-window arithmetic (days left, inside or outside the window). Done in `tools.py`.
- Whether a purchase falls within 72 hours of an outage: date comparison, code.
- The Tier 2 threshold (amount > 250 USD) and the "minor case, always Tier 2" rule: a lookup.
- Whether a chargeback is open on a transaction: a billing-console query, never inferred from text.
- Deciding that a question is a personal-data request: a pattern check that runs before the model,
  because a model that is asked nicely may comply.
- The relevance gate itself: a score threshold, so "I don't know" does not depend on the model's
  mood that day.

The model is for turning retrieved policy text into a sentence a support agent can paste. That is
the whole job description.

## 5. Who maintains it in six months

A support operations lead with some scripting ability and a part-time backend engineer. That
assumption drives every choice above: standard library only, one database, one provider, no
vector-store vendor, workflow glue in a tool the ops lead already uses, and an eval that runs with
one command so a corpus edit can be checked before it ships. If the answer were "a dedicated ML
team", hybrid retrieval, a reranker and a fine-tuned judge would move up the list. It is not.
