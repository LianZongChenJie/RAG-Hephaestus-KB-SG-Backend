"""日志配置模块

功能：
- 支持 info 和 error 级别日志分离存储
- 按天轮转日志文件
- 自动清理30天前的日志
- 超过30天的日志文件自动压缩为 .gz
"""
import gzip
import logging
import os
import shutil
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from threading import Thread
from typing import Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"

# 日志配置
LOG_LEVEL = logging.INFO
RETENTION_DAYS = 30  # 日志保留天数
COMPRESS_AFTER_DAYS = 30  # 压缩超过此天数的日志
CLEANUP_INTERVAL_HOURS = 6  # 清理检查间隔（小时）


def setup_logs_directory():
    """确保日志目录存在"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in ["info", "error"]:
        (LOGS_DIR / subdir).mkdir(parents=True, exist_ok=True)


def get_log_file_path(log_type: str) -> Path:
    """获取日志文件路径"""
    return LOGS_DIR / log_type / f"{log_type}.log"


def create_formatter() -> logging.Formatter:
    """创建日志格式化器"""
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def setup_logger(
    name: str = "app",
    log_file: Optional[Path] = None,
    level: int = LOG_LEVEL
) -> logging.Logger:
    """配置并返回 logger 实例"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    formatter = create_formatter()

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when="midnight",
            interval=1,
            backupCount=0,  # 我们自己管理备份
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.suffix = "%Y-%m-%d"
        logger.addHandler(file_handler)

    return logger


# 预配置的日志器
def get_info_logger() -> logging.Logger:
    """获取 info 级别日志记录器"""
    return setup_logger("app.info", get_log_file_path("info"))


def get_error_logger() -> logging.Logger:
    """获取 error 级别日志记录器"""
    return setup_logger("app.error", get_log_file_path("error"))


class InfoErrorLogger:
    """同时记录 info 和 error 日志的日志记录器"""

    def __init__(self, name: str = "app"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(LOG_LEVEL)
        
        # 避免重复添加 handler
        if not self.logger.handlers:
            formatter = create_formatter()
            
            # 控制台
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            # Info 文件
            info_handler = TimedRotatingFileHandler(
                filename=str(get_log_file_path("info")),
                when="midnight",
                interval=1,
                backupCount=0,
                encoding="utf-8"
            )
            info_handler.setFormatter(formatter)
            info_handler.suffix = "%Y-%m-%d"
            info_handler.setLevel(logging.INFO)
            self.logger.addHandler(info_handler)
            
            # Error 文件
            error_handler = TimedRotatingFileHandler(
                filename=str(get_log_file_path("error")),
                when="midnight",
                interval=1,
                backupCount=0,
                encoding="utf-8"
            )
            error_handler.setFormatter(formatter)
            error_handler.suffix = "%Y-%m-%d"
            error_handler.setLevel(logging.ERROR)
            self.logger.addHandler(error_handler)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs)


def compress_old_logs():
    """压缩超过30天的日志文件为 .gz"""
    now = datetime.now()
    
    for log_type in ["info", "error"]:
        log_dir = LOGS_DIR / log_type
        if not log_dir.exists():
            continue
        
        for log_file in log_dir.glob("*.log"):
            # 跳过当前正在使用的日志文件（今天的）
            today = datetime.now().strftime("%Y-%m-%d")
            if log_file.stem == f"{log_type}" and log_file.name.endswith(f"{today}.log"):
                continue
            
            # 检查文件修改时间
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if now - mtime > timedelta(days=COMPRESS_AFTER_DAYS):
                gz_file = log_file.with_suffix(".log.gz")
                if not gz_file.exists():
                    try:
                        with open(log_file, 'rb') as f_in:
                            with gzip.open(gz_file, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        log_file.unlink()
                        logging.info(f"已压缩日志文件: {gz_file.name}")
                    except Exception as e:
                        logging.error(f"压缩日志文件失败 {log_file}: {e}")


def cleanup_old_logs():
    """清理超过保留天数的日志文件（包括压缩包）"""
    now = datetime.now()
    cleaned_count = 0
    
    for log_type in ["info", "error"]:
        log_dir = LOGS_DIR / log_type
        if not log_dir.exists():
            continue
        
        # 清理 .log 文件
        for log_file in log_dir.glob("*.log"):
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if now - mtime > timedelta(days=RETENTION_DAYS):
                # 跳过今天的日志
                today = datetime.now().strftime("%Y-%m-%d")
                if log_file.name.endswith(f"{today}.log"):
                    continue
                try:
                    log_file.unlink()
                    cleaned_count += 1
                    logging.info(f"已删除过期日志: {log_file.name}")
                except Exception as e:
                    logging.error(f"删除日志文件失败 {log_file}: {e}")
        
        # 清理 .log.gz 压缩包
        for gz_file in log_dir.glob("*.log.gz"):
            mtime = datetime.fromtimestamp(gz_file.stat().st_mtime)
            if now - mtime > timedelta(days=RETENTION_DAYS):
                try:
                    gz_file.unlink()
                    cleaned_count += 1
                    logging.info(f"已删除过期压缩日志: {gz_file.name}")
                except Exception as e:
                    logging.error(f"删除压缩日志失败 {gz_file}: {e}")
    
    if cleaned_count > 0:
        logging.info(f"日志清理完成，共清理 {cleaned_count} 个文件")


def rotate_and_cleanup():
    """执行日志轮转、压缩和清理"""
    try:
        # 先压缩旧日志
        compress_old_logs()
        # 再清理过期日志
        cleanup_old_logs()
    except Exception as e:
        print(f"日志清理任务执行失败: {e}")


class LogCleanupScheduler:
    """日志清理调度器（后台定时执行）"""

    def __init__(self, interval_hours: int = CLEANUP_INTERVAL_HOURS):
        self.interval_hours = interval_hours
        self._stop = False

    def start(self):
        """启动调度器"""
        def run():
            while not self._stop:
                rotate_and_cleanup()
                import time
                time.sleep(self.interval_hours * 3600)
        
        thread = Thread(target=run, daemon=True)
        thread.start()
        logging.info(f"日志清理调度器已启动，每 {self.interval_hours} 小时执行一次")

    def stop(self):
        """停止调度器"""
        self._stop = True


# 全局日志清理调度器实例
_log_cleanup_scheduler: Optional[LogCleanupScheduler] = None


def start_log_cleanup_scheduler():
    """启动日志清理调度器"""
    global _log_cleanup_scheduler
    if _log_cleanup_scheduler is None:
        _log_cleanup_scheduler = LogCleanupScheduler()
        _log_cleanup_scheduler.start()


def init_logging():
    """初始化日志系统"""
    setup_logs_directory()
    rotate_and_cleanup()  # 启动时先执行一次清理
    start_log_cleanup_scheduler()
    
    # 配置根日志器
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logging.info("日志系统初始化完成")
    logging.info(f"日志目录: {LOGS_DIR}")
    logging.info(f"日志保留天数: {RETENTION_DAYS}")


# 便捷函数
def get_logger(name: str = "app") -> InfoErrorLogger:
    """获取日志记录器实例"""
    return InfoErrorLogger(name)


if __name__ == "__main__":
    # 测试日志功能
    init_logging()
    logger = get_logger("test")
    logger.info("这是一条 info 日志")
    logger.error("这是一条 error 日志")
    logger.warning("这是一条 warning 日志")
