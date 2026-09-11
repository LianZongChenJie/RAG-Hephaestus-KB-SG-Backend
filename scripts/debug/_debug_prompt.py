"""debug: 看 qa_matcher 拼的完整 prompt"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.qa_matcher import get_qa_matcher

m = get_qa_matcher()
prompt = m._build_prompt()

print(f"[完整 prompt 长度] {len(prompt)} 字符 (~{len(prompt)//4} tokens)")
print(f"[清单序列化长度] {len(m._serialized)} 字符")
print()
print("=" * 80)
print("前 2000 字符:")
print("=" * 80)
print(prompt[:2000])
print()
print("=" * 80)
print("后 1000 字符:")
print("=" * 80)
print(prompt[-1000:])
