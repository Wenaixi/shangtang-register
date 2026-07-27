"""
配置管理模块
从 .env 文件加载，支持环境变量覆盖
"""

import os
from pathlib import Path

ENV_PATH = Path(__file__).parent.parent / ".env"


def _load_dotenv(path: Path) -> None:
    """加载 .env 文件"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    """应用配置单例"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._loaded = True
        _load_dotenv(ENV_PATH)
        self.reload()

    def reload(self):
        """重新读取配置（GUI 修改 .env 后调用）"""
        self.SMS_BASE_URL = os.environ.get("SMS_BASE_URL", "")
        self.SMS_TOKEN = os.environ.get("SMS_TOKEN", "")
        self.HTTP_PROXY = os.environ.get("HTTP_PROXY", "") or os.environ.get("http_proxy", "")
        self.HTTPS_PROXY = os.environ.get("HTTPS_PROXY", "") or os.environ.get("https_proxy", "")
        self.SMS_PROJECT_ID = os.environ.get("SMS_PROJECT_ID", "")
        self.SMS_ISP = os.environ.get("SMS_ISP", "")
        self.SMS_ASCRIPTION = os.environ.get("SMS_ASCRIPTION", "")
        self.SMS_PARAGRAPH = os.environ.get("SMS_PARAGRAPH", "")
        self.SMS_CARD_ENGINE = os.environ.get("SMS_CARD_ENGINE", "false").lower() == "true"
        self.SMS_CODE_ID = os.environ.get("SMS_CODE_ID", "")
        self.REGISTER_COUNT = int(os.environ.get("REGISTER_COUNT", "1"))
        self.REGISTER_OUTPUT = os.environ.get("REGISTER_OUTPUT", "data/export.json")

    @property
    def proxies(self) -> dict:
        p = {}
        if self.HTTP_PROXY:
            p["http"] = self.HTTP_PROXY
        if self.HTTPS_PROXY:
            p["https"] = self.HTTPS_PROXY
        return p

    def save_to_file(self) -> None:
        """将当前配置写回 .env 文件"""
        lines = []
        lines.append(f"SMS_BASE_URL={self.SMS_BASE_URL}\n")
        lines.append(f"SMS_TOKEN={self.SMS_TOKEN}\n")
        lines.append(f"HTTP_PROXY={self.HTTP_PROXY}\n")
        lines.append(f"HTTPS_PROXY={self.HTTPS_PROXY}\n")
        lines.append(f"SMS_PROJECT_ID={self.SMS_PROJECT_ID}\n")
        lines.append(f"SMS_ASCRIPTION={self.SMS_ASCRIPTION}\n")
        lines.append(f"SMS_PARAGRAPH={self.SMS_PARAGRAPH}\n")
        lines.append(f"SMS_CARD_ENGINE={'true' if self.SMS_CARD_ENGINE else 'false'}\n")
        lines.append(f"SMS_CODE_ID={self.SMS_CODE_ID}\n")
        lines.append(f"REGISTER_COUNT={self.REGISTER_COUNT}\n")
        lines.append(f"REGISTER_OUTPUT={self.REGISTER_OUTPUT}\n")
        ENV_PATH.write_text("".join(lines), encoding="utf-8")


config = Config()
