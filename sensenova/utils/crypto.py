"""
商汤自动注册工具 - 工具函数模块
PKCE 密钥交换 / 密码生成 / JWT 解码 / 随机字符串
"""

import base64
import hashlib
import json
import random
import string
from typing import Optional


def random_str(length: int = 12, chars: str = string.ascii_lowercase + string.digits) -> str:
    """生成指定长度的随机字符串"""
    return "".join(random.choices(chars, k=length))


def generate_pkce() -> tuple[str, str]:
    """生成 PKCE code_verifier 和 code_challenge

    code_verifier: 随机 128 字符
    code_challenge: SHA256(code_verifier) 的 base64url 编码（无 padding）
    """
    code_verifier = random_str(128, string.ascii_letters + string.digits + "-._~")
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def gen_password(length: int = 16) -> str:
    """生成满足复杂度要求的随机密码

    包含大写字母、小写字母、数字、特殊字符各至少一个
    """
    safe_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    password = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%^&*"),
    ]
    password.extend(random.choices(safe_chars, k=length - 4))
    random.shuffle(password)
    return "".join(password)


def gen_username(prefix: str = "sn", length: int = 12) -> str:
    """生成随机用户名，格式: prefix + 随机字母数字"""
    return f"{prefix}{random_str(length)}"


def decode_jwt_payload(token: str) -> Optional[dict]:
    """解码 JWT payload 部分，不做签名验证

    用于从 access_token 中提取 user_id / tenant_id 等字段
    """
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return None
