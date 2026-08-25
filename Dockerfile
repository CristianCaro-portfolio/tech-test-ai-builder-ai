# Baseline image. Replace or extend it -- `docker compose up` must run your eval.
FROM python:3.12-slim
WORKDIR /app
COPY . .
CMD ["python3", "eval/run_eval.py", "--pipeline", "baseline"]
