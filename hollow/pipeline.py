"""Public contract used by eval/run_eval.py: answer(question) -> dict."""
from .agent import run_question


def answer(question: str) -> dict:
    return run_question(question)
