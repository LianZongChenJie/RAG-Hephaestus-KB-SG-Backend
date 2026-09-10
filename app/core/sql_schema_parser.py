"""
SQL schema 解析器：从 config/FWBZ_strut.sql 提取表结构供程序使用。

这是项目中所有"读取 FWBZ_strut.sql"的统一入口。早期代码在
`app/core/dameng.py`、`app/services/chat_service.py`、
`app/services/sql_service.py` 三处各自维护一份相同的解析逻辑，
统一收敛到本模块。

## 缓存策略说明

本模块**不**做进程内缓存：每次调用都重新读取并解析文件。
缓存策略由各调用方按业务需要自行决定：
- `dameng.py`         —— 进程内单次缓存（_schema_loaded 标志）
- `chat_service.py`   —— 启动期一次性（模块级 _SCHEMA_TEXT）
- `sql_service.py`    —— 不缓存，每次请求都重读

## 容错

- 文件不存在 → 记录 warning，返回空结果
- 读取/解析失败 → 记录 warning，返回空结果
- 调用方必须自行处理空结果
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# 项目根目录的 config/FWBZ_strut.sql
# __file__ = app/core/sql_schema_parser.py → 向上 3 级到项目根
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
SCHEMA_FILE: Path = PROJECT_ROOT / "config" / "FWBZ_strut.sql"

# 匹配 Navicat 导出的建表语句：CREATE TABLE "FWBZ"."table_name" ( ... );
_TABLE_RE = re.compile(
    r'CREATE\s+TABLE\s+"FWBZ"\."(\w+)"\s*\((.*?)\)\s*;',
    re.IGNORECASE | re.DOTALL,
)

# 整行以这些关键字开头的行视为约束/索引，不当列名提取
_CONSTRAINT_LINE_RE = re.compile(
    r'^(PRIMARY|UNIQUE|CHECK|CONSTRAINT|INDEX|FOREIGN)',
    re.IGNORECASE,
)

# 提取双引号内的标识符
_QUOTED_IDENT_RE = re.compile(r'"(\w+)"')


def get_schema_file_path() -> Path:
    """返回 schema 文件绝对路径（用于诊断日志）。"""
    return SCHEMA_FILE


def parse_schema_from_file() -> Dict[str, Set[str]]:
    """
    解析 FWBZ_strut.sql，返回 表名(小写) -> {列名(小写)} 的映射。

    用于 SQL 安全校验（如 dameng.validate_sql_columns），要求稳定的字典比较。
    """
    if not SCHEMA_FILE.exists():
        logger.warning(f"Schema 文件不存在: {SCHEMA_FILE}")
        return {}

    try:
        content = SCHEMA_FILE.read_text(encoding='utf-8')
    except OSError as exc:
        logger.warning(f"读取 Schema 文件失败: {exc}")
        return {}

    schema: Dict[str, Set[str]] = {}
    try:
        for match in _TABLE_RE.finditer(content):
            table_name = match.group(1).lower()
            block = match.group(2)
            cols: Set[str] = set()
            for line in block.splitlines():
                stripped = line.strip()
                if _CONSTRAINT_LINE_RE.match(stripped):
                    continue
                for col_match in _QUOTED_IDENT_RE.finditer(stripped):
                    cols.add(col_match.group(1).lower())
            if cols:
                schema[table_name] = cols
    except Exception as exc:  # 正则/解析逻辑本身不应该抛，这里兜底
        logger.warning(f"Schema 解析失败: {exc}")
        return {}

    return schema


def parse_schema_with_case() -> List[Tuple[str, List[str]]]:
    """
    解析 FWBZ_strut.sql，**保留原始大小写**，返回 [(表名, [列名...])...]。

    用于生成给 LLM 看的可读 schema 文本——保留原始大小写方便人/模型理解。
    """
    if not SCHEMA_FILE.exists():
        logger.warning(f"Schema 文件不存在: {SCHEMA_FILE}")
        return []

    try:
        content = SCHEMA_FILE.read_text(encoding='utf-8')
    except OSError as exc:
        logger.warning(f"读取 Schema 文件失败: {exc}")
        return []

    tables: List[Tuple[str, List[str]]] = []
    try:
        for match in _TABLE_RE.finditer(content):
            tname = match.group(1)
            block = match.group(2)
            cols: List[str] = []
            for line in block.splitlines():
                stripped = line.strip()
                if _CONSTRAINT_LINE_RE.match(stripped):
                    continue
                for cm in _QUOTED_IDENT_RE.finditer(stripped):
                    cols.append(cm.group(1))
            if cols:
                tables.append((tname, cols))
    except Exception as exc:
        logger.warning(f"Schema 解析失败: {exc}")
        return []

    return tables


def build_schema_text() -> str:
    """
    生成供 LLM 使用的 schema 描述文本。

    格式：
        ## 数据库真实表结构（来源：config/FWBZ_strut.sql）

        ### table_name
          列: "col1", "col2", ...
    """
    tables = parse_schema_with_case()
    lines = ["## 数据库真实表结构（来源：config/FWBZ_strut.sql）", ""]
    for tname, cols in tables:
        col_str = ", ".join(f'"{c}"' for c in cols)
        lines.append(f"### {tname}")
        lines.append(f"  列: {col_str}")
        lines.append("")
    return "\n".join(lines)
