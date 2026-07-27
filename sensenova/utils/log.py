"""
统一日志模块
支持文件 + 控制台双输出，以及注册事件回调
"""

import logging
import sys
from typing import Callable, Optional

_logger: Optional[logging.Logger] = None
_event_callback: Optional[Callable[[str, str], None]] = None


def setup(level: int = logging.INFO, callback: Optional[Callable[[str, str], None]] = None) -> logging.Logger:
    """初始化日志系统

    Args:
        level: 日志级别
        callback: 可选的事件回调，参数为 (event_type, message)
                   用于 GUI 实时日志显示
    """
    global _logger, _event_callback
    _event_callback = callback

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    _logger = logging.getLogger("sensenova")
    _logger.setLevel(level)
    _logger.handlers.clear()

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    _logger.addHandler(console)

    return _logger


def get() -> logging.Logger:
    if _logger is None:
        return setup()
    return _logger


class LogProxy:
    """日志代理，在触发 logger 的同时也通知事件回调"""

    def _emit(self, level, msg):
        log = get()
        getattr(log, level)(msg)
        if _event_callback:
            _event_callback(level, msg)

    def info(self, msg):  self._emit("info", msg)
    def warning(self, msg): self._emit("warning", msg)
    def error(self, msg): self._emit("error", msg)
    def debug(self, msg): self._emit("debug", msg)


# 便捷全局实例
proxy = LogProxy()
