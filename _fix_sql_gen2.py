import re

path = r'E:\纵联宸捷\首钢项目\会展小镇项目\RAG-Hephaestus-KB-SG-Backend\app\api\sql_gen.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update function signatures (add Request param)
for func in ['generate_sql_by_device', 'generate_report_sql', 'generate_suggestions', 'execute_sql', 'generate_full_report']:
    content = re.sub(
        rf'(async def {func})\(body:',
        rf'\1(request: Request, body:',
        content
    )

# 2. Add _wrap_resp helper before router definition
content = re.sub(
    r'(router = APIRouter\(prefix="/api", tags=\["SQL 生成"\]\))',
    r'def _wrap_resp(request, resp):\n    try:\n        inject_response(request, resp.model_dump())\n    except Exception:\n        pass\n    return resp\n\n\1',
    content
)

# 3. Multi-line return patterns
replacements = [
    # generate_sql_by_device
    ('''        return GenerateSQLByDeviceResponse(
            device_id=body.device_id,
            question=body.question,
            sql=sql,
            explanation=explanation,
        )''',
     '''        return _wrap_resp(request, GenerateSQLByDeviceResponse(
            device_id=body.device_id,
            question=body.question,
            sql=sql,
            explanation=explanation,
        ))'''),
    # generate_report_sql
    ('''        return GenerateReportSQLResponse(
            report_type=body.report_type.value,
            target_id=resolved_target_id,
            target_name=body.target_name,
            metrics=metrics,
        )''',
     '''        return _wrap_resp(request, GenerateReportSQLResponse(
            report_type=body.report_type.value,
            target_id=resolved_target_id,
            target_name=body.target_name,
            metrics=metrics,
        ))'''),
    # generate_suggestions
    ('''        return GenerateSuggestionsResponse(
            report_type=body.report_type.value,
            target_id=body.target_id,
            suggestions=suggestions,
        )''',
     '''        return _wrap_resp(request, GenerateSuggestionsResponse(
            report_type=body.report_type.value,
            target_id=body.target_id,
            suggestions=suggestions,
        ))'''),
    # execute_sql
    ('''        return ExecuteSQLResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time=round(execution_time, 3),
        )''',
     '''        return _wrap_resp(request, ExecuteSQLResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time=round(execution_time, 3),
        ))'''),
    # generate_full_report
    ('''        return GenerateFullReportResponse(
            report_type=body.report_type.value,
            target_id=target_id,
            target_name=body.target_name,
            sql_results=sql_results,
            suggestions=suggestions,
        )''',
     '''        return _wrap_resp(request, GenerateFullReportResponse(
            report_type=body.report_type.value,
            target_id=target_id,
            target_name=body.target_name,
            sql_results=sql_results,
            suggestions=suggestions,
        ))'''),
]

for old, new in replacements:
    content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done, replacements:', len(replacements))
