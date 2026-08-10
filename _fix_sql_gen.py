import re

path = r'E:\纵联宸捷\首钢项目\会展小镇项目\RAG-Hephaestus-KB-SG-Backend\app\api\sql_gen.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
if 'from app.middlewares.access_log import inject_response' not in content:
    content = re.sub(
        r'from fastapi import APIRouter, HTTPException',
        r'from fastapi import APIRouter, HTTPException, Request\nfrom app.middlewares.access_log import inject_response',
        content
    )

# Add helper function after the docstring
helper = "\n\ndef _inject(request, resp):\n    try:\n        inject_response(request, resp.model_dump())\n    except Exception:\n        pass\n    return resp\n"

content = re.sub(
    r'("""SQL 生成接口"""\n)',
    r'\1' + helper,
    content
)

# Update function signatures
funcs = [
    'generate_sql', 'generate_sql_by_device', 'generate_report_sql',
    'generate_suggestions', 'execute_sql', 'generate_full_report'
]
for func in funcs:
    content = re.sub(
        rf'(async def {func})\(body:',
        rf'\1(request: Request, body:',
        content
    )

# Update return statements - wrap in _inject
# Pattern: return GenerateSQLResponse(sql=sql, explanation=explanation)
content = re.sub(
    r'return GenerateSQLResponse\(\s*sql=sql,\s*explanation=explanation,\s*\)',
    r'return _inject(request, GenerateSQLResponse(sql=sql, explanation=explanation))',
    content
)

content = re.sub(
    r'return GenerateSQLByDeviceResponse\(',
    r'return _inject(request, GenerateSQLByDeviceResponse(',
    content
)

content = re.sub(
    r'return GenerateReportSQLResponse\(',
    r'return _inject(request, GenerateReportSQLResponse(',
    content
)

content = re.sub(
    r'return GenerateSuggestionsResponse\(',
    r'return _inject(request, GenerateSuggestionsResponse(',
    content
)

content = re.sub(
    r'return ExecuteSQLResponse\(',
    r'return _inject(request, ExecuteSQLResponse(',
    content
)

content = re.sub(
    r'return GenerateFullReportResponse\(',
    r'return _inject(request, GenerateFullReportResponse(',
    content
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
