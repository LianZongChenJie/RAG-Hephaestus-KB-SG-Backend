"""debug: 直接调 Ollama, 看返回结构"""
import json
import httpx

# 1. 简单 prompt
simple_prompt = '你是一个测试。请用 JSON 回答: {"answer": "hi"} 不要任何其他内容。'
payload = {
    "model": "qwen3.5:9b",
    "messages": [{"role": "user", "content": simple_prompt}],
    "stream": False,
    "options": {"temperature": 0.1, "num_ctx": 20480, "num_predict": 256},
}
r = httpx.post("http://localhost:11434/api/chat", json=payload, timeout=30)
data = r.json()
print("=" * 60)
print("[简单 prompt] 所有 keys:", list(data.keys()))
msg = data.get("message", {})
print("  message keys:", list(msg.keys()))
print("  content:", repr(msg.get("content", ""))[:300])
print("  thinking:", repr(msg.get("thinking", ""))[:300])
print("  reasoning_content:", repr(msg.get("reasoning_content", ""))[:300])
print("  done_reason:", data.get("done_reason"))
print("  eval_count:", data.get("eval_count"))
print("  total_duration (ns):", data.get("total_duration"))


# 2. 拿 qa_matcher 的 prompt
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.services.qa_matcher import get_qa_matcher
m = get_qa_matcher()
big_prompt = m._build_prompt()
big_prompt += "\n\n## 用户问题\n今日总能耗多少?"

print()
print("=" * 60)
print(f"[大 prompt 长度] {len(big_prompt)} 字符")
payload2 = {
    "model": "qwen3.5:9b",
    "messages": [{"role": "user", "content": big_prompt}],
    "stream": False,
    "options": {"temperature": 0.1, "num_ctx": 20480, "num_predict": 512},
}
r2 = httpx.post("http://localhost:11434/api/chat", json=payload2, timeout=60)
data2 = r2.json()
msg2 = data2.get("message", {})
print("  content (前 500):", repr(msg2.get("content", ""))[:500])
print("  thinking (前 500):", repr(msg2.get("thinking", ""))[:500])
print("  done_reason:", data2.get("done_reason"))
print("  eval_count:", data2.get("eval_count"))
print("  total_duration (ns):", data2.get("total_duration"))
print("  prompt_eval_count:", data2.get("prompt_eval_count"))
