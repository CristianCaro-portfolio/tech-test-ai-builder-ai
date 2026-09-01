FROM python:3.12-slim
WORKDIR /app
# Standard library only: no requirements to install.
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "python3 -m unittest discover -s tests -q && python3 eval/run_eval.py --pipeline baseline && python3 eval/run_eval.py --pipeline hollow"]
