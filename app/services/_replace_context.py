# -*- coding: utf-8 -*-
import re, os

file_path = r"E:\纵联宸捷\首钢项目\会展小镇项目\RAG-Hephaestus-KB-SG-Backend\app\services\chat_service.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_ctx_path = r"E:\纵联宸捷\首钢项目\会展小镇项目\RAG-Hephaestus-KB-SG-Backend\app\services\_new_context.py"
with open(new_ctx_path, 'r', encoding='utf-8') as f:
    new_context = f.read()

# Find start of DAMENG_SCHEMA_CONTEXT block
start_marker = 'DAMENG_SCHEMA_CONTEXT = """'
start_idx = content.find(start_marker)
if start_idx < 0:
    print("ERROR: DAMENG_SCHEMA_CONTEXT start not found")
    exit(1)

# Find the closing """
end_idx = content.find('"""', start_idx + len(start_marker))
if end_idx < 0:
    print("ERROR: DAMENG_SCHEMA_CONTEXT closing not found")
    exit(1)

# Replace
new_content = content[:start_idx] + new_context + content[end_idx+3:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("DONE: DAMENG_SCHEMA_CONTEXT replaced")
print(f"Old length: {len(content)}, New length: {len(new_content)}")

# Clean up temp files
for tmp in [new_ctx_path]:
    if os.path.exists(tmp):
        os.remove(tmp)
        print(f"Cleaned: {tmp}")
