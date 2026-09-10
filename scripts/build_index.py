"""
FWBZ 知识库离线建索引脚本
============================

读取 config/ 下的 4 个文档:
    - FWBZ问题清单.md
    - FWBZ问题分类速查.md
    - FWBZ问答手册.md
    - FWBZ_strut.sql

切 chunk, 调用 Ollama 嵌入, 写入 PostgreSQL (pgvector)。

运行:
    python scripts/build_index.py
    python scripts/build_index.py --rebuild     # 先清空再建
    python scripts/build_index.py --model nomic-embed-text
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

# 让脚本可直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.embedder import OllamaEmbedder
from app.core.vector_store import PgVectorStore, RagChunk

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("build_index")


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


# ---------------------------------------------------------------------------
# 切 chunk: 问题清单
# ---------------------------------------------------------------------------
QUESTION_TOPIC_MAP = {
    # Q 编号 (来自 FWBZ问题清单.md 的二级章节) -> 主题
    "1": "AI报告与日志",
    "2": "报警与异常",
    "3": "设备与采集",
    "4": "空间位置",
    "5": "能耗与计费",
    "6": "照明",
    "7": "联动与场景",
    "8": "楼宇自控",
    "9": "视频监控",
    "10": "门禁与人员",
    "11": "消防",
    "12": "停车场",
    "13": "客流",
    "14": "投诉",
    "15": "活动会议",
    "16": "冷源与接口",
    "17": "权限与配置",
    "18": "综合分析",
}

# 主题分类速查 -> 主题(中文简短,用于 metadata)
TOPIC_KEYWORDS = {
    "能耗与计费": "能耗",
    "报警与异常": "报警",
    "设备与采集": "设备",
    "视频监控": "视频",
    "门禁 / 人员识别 / 客流": "门禁",
    "门禁 / 人员识别": "门禁",
    "停车场": "停车",
    "照明与联动": "照明",
    "照明与联动(联动)": "联动",
    "消防": "消防",
    "投诉 / 活动": "综合",
    "运维 / 系统": "运维",
}


def chunk_questions(path: Path) -> list[RagChunk]:
    """从 FWBZ问题清单.md 提取每条问题, 生成 chunk"""
    text = path.read_text(encoding="utf-8")
    chunks: list[RagChunk] = []
    current_section = ""

    # 章节切换: "## N. 主题"
    section_re = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
    # 编号列表项: "1. 今日总能耗是多少?"
    item_re = re.compile(r"^(\d+)\.\s+(.+?)\s*$", re.MULTILINE)

    for line in text.splitlines():
        m = section_re.match(line)
        if m:
            current_section = m.group(2).strip()
            continue
        m = item_re.match(line)
        if m and current_section and "问题" not in line:
            # 过滤掉目录、附录标题等
            q_text = m.group(2).strip()
            if not q_text or q_text.startswith("---") or q_text.startswith("**"):
                continue
            chunks.append(RagChunk(
                chunk_id=f"Q_{current_section[:4]}_{m.group(1)}",
                type="question",
                topic=current_section,
                title=q_text[:60],
                content=q_text,
                metadata={"section": current_section},
            ))
    return chunks


# ---------------------------------------------------------------------------
# 切 chunk: 问答手册(SQL 范式)
# ---------------------------------------------------------------------------
def chunk_qa_book(path: Path) -> list[RagChunk]:
    """
    从 FWBZ问答手册.md 提取每个 Qx.y 的"问题 + SQL 范式"作为 chunk。
    块结构: ## 章节 -> ### 可回答的问题 -> ### SQL 范式 -> **Q1.1 ...** -> ```sql```
    """
    text = path.read_text(encoding="utf-8")
    chunks: list[RagChunk] = []
    current_section = ""
    current_section_num = ""

    # 章节
    section_re = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
    # Q 编号
    q_re = re.compile(r"^\*\*Q(\d+)\.(\d+)\.\s+(.+?)\*\*", re.MULTILINE)
    # SQL 块
    sql_re = re.compile(r"```sql\n(.*?)```", re.DOTALL)

    # 整体按 "**Qx.y.**" 切片
    parts = re.split(r"(?=\*\*Q\d+\.\d+\.\s)", text)
    for part in parts:
        m = q_re.match(part)
        if not m:
            continue
        q_id = f"Q{m.group(1)}.{m.group(2)}"
        q_title = m.group(3).strip()

        # 取第一个 SQL 块作为代表
        sql_match = sql_re.search(part)
        sql_text = sql_match.group(1).strip() if sql_match else ""

        # 章节名
        sec_match = section_re.search(part[:200])
        topic = sec_match.group(2).strip() if sec_match else "其他"

        content = f"问题: {q_title}\nSQL 范式:\n{sql_text}"
        chunks.append(RagChunk(
            chunk_id=f"SQL_{q_id.replace('.', '_')}",
            type="sql_template",
            topic=topic,
            title=f"{q_id} {q_title[:50]}",
            content=content,
            metadata={"q_id": q_id, "section": topic, "has_sql": bool(sql_text)},
        ))
    return chunks


# ---------------------------------------------------------------------------
# 切 chunk: DDL
# ---------------------------------------------------------------------------
def chunk_schema(path: Path) -> list[RagChunk]:
    """从 FWBZ_strut.sql 提取每张表的 CREATE TABLE 段"""
    text = path.read_text(encoding="utf-8")
    chunks: list[RagChunk] = []
    # 简单切: CREATE TABLE "FWBZ"."xxx" ( ... );
    pattern = re.compile(
        r'CREATE TABLE "FWBZ"\."(\w+)"\s*\((.*?)\)\s*;',
        re.DOTALL
    )
    for m in pattern.finditer(text):
        table_name = m.group(1)
        cols = m.group(2).strip()
        # 找表注释
        comment_m = re.search(
            rf'COMMENT ON TABLE "FWBZ"\."{re.escape(table_name)}" IS \'([^\']+)\'',
            text[m.end(): m.end() + 500]
        )
        table_comment = comment_m.group(1) if comment_m else ""

        # 压缩: 只保留列名 + 类型 + 注释
        col_lines = []
        for line in cols.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            col_lines.append(line)
        ddl_short = "CREATE TABLE FWBZ." + table_name + " (\n  " + ",\n  ".join(col_lines) + "\n);"
        content = f"表名: {table_name}\n注释: {table_comment}\n\n{ddl_short}"

        chunks.append(RagChunk(
            chunk_id=f"TBL_{table_name}",
            type="schema",
            topic=None,
            title=f"FWBZ.{table_name}",
            content=content,
            metadata={"table": table_name, "comment": table_comment},
        ))
    return chunks


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="FWBZ 知识库离线建索引")
    ap.add_argument("--rebuild", action="store_true", help="清空后重建")
    ap.add_argument("--model", default="bge-m3", help="Embedding 模型 (默认 bge-m3)")
    ap.add_argument("--batch", type=int, default=20, help="每批 embedding 数量")
    args = ap.parse_args()

    # 1. 准备
    embedder = OllamaEmbedder(model=args.model)
    dim = embedder.dim_of(args.model)
    store = PgVectorStore(embedding_dim=dim)
    logger.info(f"使用模型: {args.model}, dim={dim}")

    if args.rebuild:
        logger.warning("清空旧索引...")
        store.clear()

    # 2. 切 chunk
    all_chunks: list[RagChunk] = []
    q_path = CONFIG_DIR / "FWBZ问题清单.md"
    book_path = CONFIG_DIR / "FWBZ问答手册.md"
    sql_path = CONFIG_DIR / "FWBZ_strut.sql"

    for label, p in [("问题清单", q_path), ("问答手册", book_path), ("DDL", sql_path)]:
        if not p.exists():
            logger.warning(f"跳过(不存在): {p}")
            continue
        if "问题清单" in label:
            cs = chunk_questions(p)
        elif "问答手册" in label:
            cs = chunk_qa_book(p)
        else:
            cs = chunk_schema(p)
        logger.info(f"{label}: 切出 {len(cs)} chunks")
        all_chunks.extend(cs)

    logger.info(f"总 chunks: {len(all_chunks)}")

    # 3. 嵌入
    logger.info("开始 embedding...")
    texts = [c.content for c in all_chunks]
    vecs = embedder.embed_batch(texts, show_progress=True)
    ok = 0
    for c, v in zip(all_chunks, vecs):
        if v is not None:
            c.embedding = v
            ok += 1
    logger.info(f"嵌入成功: {ok}/{len(all_chunks)}")

    # 4. 写入(分批, 避免单事务过大)
    BATCH = args.batch
    written = 0
    for i in range(0, len(all_chunks), BATCH):
        batch = [c for c in all_chunks[i:i + BATCH] if c.embedding is not None]
        if not batch:
            continue
        try:
            store.upsert(batch)
            written += len(batch)
            logger.info(f"  写入 {i + len(batch)}/{len(all_chunks)}")
        except Exception as e:
            logger.error(f"  写入失败: {e}")
    logger.info(f"完成: 共写入 {written} chunks; 总数 {store.count()}")


if __name__ == "__main__":
    main()
