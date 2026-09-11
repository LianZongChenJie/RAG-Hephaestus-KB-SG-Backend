"""macOS 达梦连接：复用 DBeaver 的 JDBC 驱动。

dmPython 不提供 macOS wheel，本机 DBeaver 已能连达梦，因此用同一份
DmJdbcDriver jar + JayDeBeApi，对外仍提供 DB-API 风格的 connect/cursor。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from app.core.config import PROJECT_ROOT
from app.core.logger import get_logger

logger = get_logger("dameng_jdbc")

_DRIVER_CLASS = "dm.jdbc.driver.DmDriver"


def _ensure_java_home() -> None:
    if os.environ.get("JAVA_HOME"):
        return
    try:
        home = subprocess.check_output(
            ["/usr/libexec/java_home"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if home:
            os.environ["JAVA_HOME"] = home
            logger.info("已设置 JAVA_HOME=%s", home)
    except (OSError, subprocess.CalledProcessError):
        pass


def find_jdbc_jar() -> Path:
    """查找达梦 JDBC jar：环境变量 > 项目 drivers/ > DBeaver 缓存。"""
    env_path = os.environ.get("DM_JDBC_JAR")
    if env_path:
        p = Path(env_path).expanduser()
        if p.is_file():
            return p

    local_dir = PROJECT_ROOT / "drivers"
    if local_dir.is_dir():
        jars = [
            p for p in sorted(local_dir.glob("DmJdbc*.jar"))
            if not p.name.startswith("._")
        ] or [
            p for p in sorted(local_dir.glob("*.jar"))
            if not p.name.startswith("._")
        ]
        if jars:
            return jars[0]

    dbeaver = Path.home() / "Library/DBeaverData/drivers/maven/maven-central/com.dameng"
    if dbeaver.is_dir():
        jars = sorted(dbeaver.glob("DmJdbc*.jar"))
        if jars:
            return jars[0]

    raise FileNotFoundError(
        "未找到达梦 JDBC 驱动。请将 DBeaver 的 DmJdbcDriver*.jar 复制到项目 drivers/ 目录，"
        "或设置环境变量 DM_JDBC_JAR。"
    )


def _to_python(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    if hasattr(value, "doubleValue"):
        try:
            return float(value.doubleValue())
        except Exception:
            pass
    if hasattr(value, "longValue"):
        try:
            return int(value.longValue())
        except Exception:
            pass
    return str(value)


class JdbcCursor:
    def __init__(self, raw: Any):
        self._raw = raw
        self.description = None
        self.rowcount = -1

    def execute(self, sql: str, params: Optional[tuple] = None) -> None:
        if params:
            self._raw.execute(sql, params)
        else:
            self._raw.execute(sql)
        self.description = getattr(self._raw, "description", None)
        self.rowcount = getattr(self._raw, "rowcount", -1)

    def fetchall(self) -> list[tuple]:
        rows = self._raw.fetchall() or []
        return [tuple(_to_python(v) for v in row) for row in rows]

    def fetchone(self):
        row = self._raw.fetchone()
        if row is None:
            return None
        return tuple(_to_python(v) for v in row)

    def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass


class JdbcConnection:
    def __init__(self, raw: Any):
        self._raw = raw

    def cursor(self) -> JdbcCursor:
        return JdbcCursor(self._raw.cursor())

    def commit(self) -> None:
        try:
            self._raw.commit()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass


def connect(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    schema: str = "",
) -> JdbcConnection:
    """通过 JDBC 连接达梦，返回 DB-API 风格连接。"""
    import jaydebeapi

    _ensure_java_home()
    jar = find_jdbc_jar()
    url = f"jdbc:dm://{host}:{port}"
    if schema:
        url = f"{url}?schema={schema}"

    logger.info("使用 JDBC 连接达梦: %s (jar=%s)", url, jar)
    raw = jaydebeapi.connect(
        _DRIVER_CLASS,
        url,
        [user, password],
        str(jar),
    )
    conn = JdbcConnection(raw)
    if schema:
        cur = conn.cursor()
        try:
            cur.execute(f'SET SCHEMA "{schema}"')
        except Exception as exc:
            logger.warning("SET SCHEMA %s 失败（可忽略）: %s", schema, exc)
        finally:
            cur.close()
    return conn
