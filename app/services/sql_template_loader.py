"""
问答手册 SQL 范式索引
=====================

把 config/FWBZ问答手册.md 按 Q-ID 切块, 建 dict 索引, 一次性加载, 进程内缓存.

Q-ID 格式: "1.1" / "5.3" / "17.2"  (业务域.子序号)
chunk 切片规则:
    1. 优先匹配 "**Q1.1 ..."  /  "### Q1.1"  /  "**Qx.y**" 这类模式
    2. 兜底: 按 "## 业务域" + 序号列表的相邻顺序推断

用法:
    loader = get_template_loader()
    sql_template = loader.get("5.1")  # 拿 5.1 的 SQL 范式块
    if sql_template:
        ...

降级: 文件不存在时, 加载返回空 dict, 调用方走兜底
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


# 匹配 "**Q1.1 标题**" 或 "### Q1.1 标题"  或  "Q1.1 " 等多种格式
_QID_PATTERN = re.compile(
    r"""
    (?:^|\n)\s*               # 行首
    (?:\#{1,4}\s+|\*\*)?      # 可选的 markdown 标题/加粗前缀
    Q\s*                      # 字母 Q
    (\d+)\s*\.\s*(\d+)        # 业务域.子序号
    \b                        # 词边界
    [^\n]*                    # 同行余下文字 (标题)
    """,
    re.IGNORECASE | re.VERBOSE,
)


class QATemplateLoader:
    """Q-ID → 文本块 索引"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._templates: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        self._loaded = False
        self._lock = Lock()

    def load(self) -> None:
        """加载并切块 (线程安全, 幂等)"""
        with self._lock:
            if self._loaded:
                return
            if not self.file_path.exists():
                logger.warning(f"问答手册不存在: {self.file_path}, 索引为空")
                self._loaded = True
                return

            try:
                text = self.file_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"读取问答手册失败: {e}")
                self._loaded = True
                return

            # 找所有 Q-ID 起点
            matches = list(_QID_PATTERN.finditer(text))
            for i, m in enumerate(matches):
                q_id = f"{m.group(1)}.{m.group(2)}"
                # chunk 范围: 从本 Q 标题行到下一个 Q 标题行 (或文末)
                start = m.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                chunk = text[start:end].strip()
                self._templates[q_id] = chunk

                # 抽取标题: "Q1.1 标题..."
                title_part = m.group(0).strip()
                # 去掉 markdown 前缀
                title_part = re.sub(r"^[\#\*\s]+", "", title_part)
                title_part = re.sub(r"^Q\s*\d+\.\d+\s*", "", title_part, flags=re.IGNORECASE)
                # 去掉行尾的 **
                title_part = title_part.strip().strip("*").strip()
                if title_part:
                    self._titles[q_id] = title_part[:80]

            logger.info(
                f"问答手册 Q-ID 索引构建完成: {len(self._templates)} 条 "
                f"(文件: {self.file_path.name})"
            )
            self._loaded = True

    def get(self, q_id: str) -> Optional[str]:
        """
        拿指定 Q-ID 的完整 chunk 文本 (含标题/SQL范式/示例)
        未加载则自动 load
        """
        if not self._loaded:
            self.load()
        return self._templates.get(q_id)

    def get_title(self, q_id: str) -> Optional[str]:
        """拿 Q-ID 对应的标题 (纯文本)"""
        if not self._loaded:
            self.load()
        return self._titles.get(q_id)

    def all_qids(self) -> list[str]:
        """全部 Q-ID 列表 (用于调试)"""
        if not self._loaded:
            self.load()
        return sorted(self._templates.keys(), key=_qid_sort_key)

    def has(self, q_id: str) -> bool:
        if not self._loaded:
            self.load()
        return q_id in self._templates


def _qid_sort_key(qid: str) -> tuple[int, int]:
    """Q-ID 自然排序: 1.2 < 1.10 < 2.1"""
    a, b = qid.split(".")
    return int(a), int(b)


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
_singleton: Optional[QATemplateLoader] = None
_singleton_lock = Lock()


def get_template_loader() -> QATemplateLoader:
    """拿 Q-ID 索引单例 (按 config 目录找)"""
    global _singleton
    if _singleton is not None:
        return _singleton
    with _singleton_lock:
        if _singleton is not None:
            return _singleton
        # 项目根 = app/core/sql_template_loader.py 往上 3 级
        root = Path(__file__).resolve().parent.parent.parent
        qa_path = root / "config" / "FWBZ问答手册.md"
        _singleton = QATemplateLoader(qa_path)
        _singleton.load()
        return _singleton
