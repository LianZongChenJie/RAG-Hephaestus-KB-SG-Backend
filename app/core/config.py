"""配置加载模块"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


class ModelDefaultsConfig:
    """模型默认参数"""
    num_ctx: int
    temperature: float

    def __init__(self, num_ctx: int = 2048, temperature: float = 0.6,
                 num_predict: int = 2048, num_predict_report: int = 8192):
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.num_predict = num_predict
        self.num_predict_report = num_predict_report


class OllamaConfig:
    """Ollama 配置"""
    chat_url: str
    tags_url: str
    model: str
    timeout: float
    num_gpu: int
    keep_alive: str
    think: bool

    def __init__(
        self,
        chat_url: str = "http://127.0.0.1:11434/api/chat",
        tags_url: str = "http://127.0.0.1:11434/api/tags",
        model: str = "qwen3.5:9b",
        timeout: float = 300.0,
        num_gpu: int = 99,
        keep_alive: str = "24h",
        think: bool = False,
    ):
        self.chat_url = chat_url
        self.tags_url = tags_url
        self.model = model
        self.timeout = timeout
        self.num_gpu = num_gpu
        self.keep_alive = keep_alive
        self.think = think


class DatabaseConfig:
    """数据库配置"""
    host: str
    port: int
    user: str
    password: str
    name: str
    min_size: int
    max_size: int

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        name: str = "hephaestus",
        min_size: int = 1,
        max_size: int = 5,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.name = name
        self.min_size = min_size
        self.max_size = max_size


class DamengConfig:
    """达梦数据库配置"""
    host: str
    port: int
    user: str
    password: str
    schema: str
    charset: str

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5236,
        user: str = "SYSDBA",
        password: str = "Dameng123",
        schema: str = "FWBZ",
        charset: str = "UTF-8",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.schema = schema
        self.charset = charset

    @property
    def dsn(self) -> str:
        """构建达梦连接字符串"""
        return f"{self.host}:{self.port}/{self.schema}"


class AppConfig:
    """应用配置"""
    host: str
    port: int
    title: str
    cors_origins: List[str]

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        title: str = "Hephaestus Chat Proxy",
        cors_origins: Optional[List[str]] = None,
    ):
        self.host = host
        self.port = port
        self.title = title
        self.cors_origins = cors_origins or ["*"]


class LoggingConfig:
    """日志配置"""
    level: str

    def __init__(self, level: str = "INFO"):
        self.level = level


class Settings:
    """全局配置对象"""
    database: DatabaseConfig
    dameng: DamengConfig
    ollama: OllamaConfig
    model_defaults: ModelDefaultsConfig
    app: AppConfig
    logging: LoggingConfig
    query_config: Dict[str, Any]  # query.json 内容

    def __init__(self):
        self._load_main_config()
        self._load_query_config()

    def _load_main_config(self) -> None:
        """加载主配置文件 config.yaml"""
        config_path = PROJECT_ROOT / "config" / "config.yaml"
        if not config_path.exists():
            logger.warning("配置文件不存在: %s，使用默认配置", config_path)
            self._use_defaults()
            return

        with open(config_path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = yaml.safe_load(f)

        self.database = DatabaseConfig(**data.get("database", {}))
        self.dameng = DamengConfig(**data.get("dameng", {}))
        self.ollama = OllamaConfig(**data.get("ollama", {}))
        self.model_defaults = ModelDefaultsConfig(**data.get("model_defaults", {}))
        self.app = AppConfig(**data.get("app", {}))
        self.logging = LoggingConfig(**data.get("logging", {}))

    def _load_query_config(self) -> None:
        """加载 query.json 表结构配置"""
        config_path = PROJECT_ROOT / "config" / "query.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self.query_config = json.load(f)
        else:
            self.query_config = {}
            logger.warning("query.json 不存在，表结构信息将不可用")

    def _use_defaults(self) -> None:
        """使用硬编码默认值（兼容旧代码）"""
        self.database = DatabaseConfig()
        self.dameng = DamengConfig()
        self.ollama = OllamaConfig()
        self.model_defaults = ModelDefaultsConfig()
        self.app = AppConfig()
        self.logging = LoggingConfig()
        self.query_config = {}


# 全局单例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
