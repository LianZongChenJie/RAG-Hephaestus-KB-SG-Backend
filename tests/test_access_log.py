"""访问日志：北京时间 access_time，以及 LLM token 统计。"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.common.database import BEIJING_TZ, _fmt_time, beijing_now
from app.common.ollama import OllamaClient, parse_llm_usage


def test_fmt_time_converts_utc_to_beijing():
    utc = datetime(2026, 9, 15, 1, 29, 0, tzinfo=timezone.utc)
    assert _fmt_time(utc) == "2026-09-15 09:29:00"


def test_fmt_time_keeps_beijing_wall_clock():
    beijing = datetime(2026, 9, 15, 9, 29, 0, tzinfo=BEIJING_TZ)
    assert _fmt_time(beijing) == "2026-09-15 09:29:00"


def test_fmt_time_naive_is_already_beijing():
    naive = datetime(2026, 9, 15, 9, 29, 0)
    assert _fmt_time(naive) == "2026-09-15 09:29:00"


def test_beijing_now_is_utc_plus_8():
    now = beijing_now()
    assert now.utcoffset() == timedelta(hours=8)


def test_parse_ollama_usage():
    prompt, completion = parse_llm_usage(
        {"done": True, "prompt_eval_count": 120, "eval_count": 40}
    )
    assert prompt == 120
    assert completion == 40


def test_parse_openai_usage():
    prompt, completion = parse_llm_usage(
        {"usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100}}
    )
    assert prompt == 80
    assert completion == 20


def test_parse_dashscope_input_output_tokens():
    prompt, completion = parse_llm_usage(
        {"usage": {"input_tokens": 15, "output_tokens": 7}}
    )
    assert prompt == 15
    assert completion == 7


def test_parse_total_only_keeps_token_count():
    prompt, completion = parse_llm_usage({"usage": {"total_tokens": 90}})
    assert prompt == 90
    assert completion == 0


def test_usage_accumulates_sql_and_summary_calls():
    client = OllamaClient.__new__(OllamaClient)
    client.reset_usage()
    client.add_usage(data={"usage": {"prompt_tokens": 100, "completion_tokens": 30}})
    client.add_usage(data={"prompt_eval_count": 50, "eval_count": 10})
    prompt, completion, total = client.usage_snapshot()
    assert prompt == 150
    assert completion == 40
    assert total == 190


def test_usage_snapshot_empty_is_none():
    client = OllamaClient.__new__(OllamaClient)
    client.reset_usage()
    assert client.usage_snapshot() == (None, None, None)


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print("OK", name)
        except Exception as exc:
            failed += 1
            print("FAIL", name, type(exc).__name__ + ":", exc)
    raise SystemExit(1 if failed else 0)
