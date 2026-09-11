"""debug: 单条 QA 匹配, 用 format=json + 从 thinking 提取"""
import json
import re
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import get_settings
from app.services.qa_matcher import get_qa_matcher

m = get_qa_matcher()
prompt = m._build_prompt()
prompt += "\n\n## 用户问题\n今日总能耗多少?"

s = get_settings()
payload = {
    "model": s.ollama.model,
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
    "format": "json",
    "options": {
        "temperature": 0.1,
        "num_ctx": 8192,
        "num_predict": 1024,  # 适中, 给 thinking ~600 token, 留 ~400 给 JSON
    },
}

print("[*] Sending request to Ollama...")
import time
t0 = time.time()
with httpx.Client(timeout=60) as client:
    resp = client.post(s.ollama.chat_url, json=payload)
    data = resp.json()
t1 = time.time()
print(f"[*] Elapsed: {(t1-t0)*1000:.0f}ms")

msg = data.get("message") or {}
content = msg.get("content", "")
thinking = msg.get("thinking", "")
print(f"[*] content length: {len(content)}")
print(f"[*] thinking length: {len(thinking)}")
print(f"[*] done_reason: {data.get('done_reason')}")
print(f"[*] eval_count: {data.get('eval_count')}")
print()
print("=== content (前 800) ===")
print(content[:800])
print()
print("=== thinking 末尾 (后 800) ===")
print(thinking[-800:])

# 尝试从 thinking 末尾找 JSON
combined = thinking + "\n" + content
json_match = re.search(r"\{[\s\S]*?\}", combined)
if json_match:
    print()
    print("=== 从 thinking+content 提取的 JSON 候选 ===")
    print(json_match.group(0)[:500])
