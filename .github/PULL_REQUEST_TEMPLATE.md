# Submission

- **Name:**
- **Time spent:**
- **Language / stack:**
- **LLM provider + model:**

## Numbers

| Metric | Baseline | Mine |
|---|---|---|
| Retrieval hit-rate | | |
| Answer accuracy | | |
| Correct refusals | | |
| Restricted leaks | 0 | |
| Latency p50 | | |
| Cost per query | | |

Command that reproduces the "Mine" column:

```bash
```

## What I changed and why

## Trade-offs

## Checklist

- [ ] Eval reproducible with one command
- [ ] `DECISIONS.md` with before/after metrics
- [ ] `DECISIONS.md` includes the change that made things worse
- [ ] Tool calling implemented, with failure handling
- [ ] Refuses instead of inventing when retrieval finds nothing
- [ ] Restricted data never sent to the model provider
- [ ] `STACK.md` with the code / no-code line drawn explicitly
- [ ] `AI_WORKFLOW.md` included
- [ ] `docker compose up` runs the eval
