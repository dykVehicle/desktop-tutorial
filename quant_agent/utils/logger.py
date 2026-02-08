"""
日志管理模块

提供统一的日志配置和获取接口。
所有日志时间戳统一使用北京时间 (UTC+8)。
"""

import logging
import os
from datetime import timezone, timedelta
from typing import Optional


_loggers: dict[str, logging.Logger] = {}

# 北京时间时区 (UTC+8)
_BEIJING_TZ = timezone(timedelta(hours=8))


class _BeijingFormatter(logging.Formatter):
    """使用北京时间的日志格式化器。"""

    converter = None  # 不使用 time.localtime

    def formatTime(self, record, datefmt=None):
        from datetime import datetime
        dt = datetime.fromtimestamp(record.created, tz=_BEIJING_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def setup_logger(
    name: str = "quant_agent",
    level: str = "INFO",
    log_file: Optional[str] = None,
    console: bool = True,
) -> logging.Logger:
    """
    设置并返回一个日志记录器。
    时间戳统一使用北京时间 (UTC+8)。

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，如果为None则不写入文件
        console: 是否输出到控制台

    Returns:
        配置好的日志记录器
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False  # 防止日志向父logger传播导致重复输出

    formatter = _BeijingFormatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def get_logger(name: str = "quant_agent") -> logging.Logger:
    """
    获取已有的日志记录器，如果不存在则创建一个默认的。

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器
    """
    if name not in _loggers:
        return setup_logger(name)
    return _loggers[name]
