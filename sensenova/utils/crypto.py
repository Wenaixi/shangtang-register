"""
商汤自动注册工具 - 工具函数模块
PKCE 密钥交换 / 密码生成 / JWT 解码 / 随机字符串
"""

import base64
import hashlib
import json
import secrets
import string
from typing import Optional


def random_str(length: int = 12, chars: str = string.ascii_lowercase + string.digits) -> str:
    """生成指定长度的安全随机字符串"""
    return "".join(secrets.choice(chars) for _ in range(length))


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
    """生成满足复杂度要求的安全随机密码"""
    safe_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    password += [secrets.choice(safe_chars) for _ in range(length - 4)]
    # 洗牌
    for i in range(len(password) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password[i], password[j] = password[j], password[i]
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
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return None
