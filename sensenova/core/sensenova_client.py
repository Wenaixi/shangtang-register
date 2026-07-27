"""
商汤 SenseNova 平台注册客户端
封装完整 OAuth2 PKCE 注册流程
"""

import re
import time
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests

from sensenova.utils.crypto import generate_pkce, random_str, decode_jwt_payload
from sensenova.utils.log import proxy as log


class SensenovaClient:
    """商汤 SenseNova API 客户端

    处理: OAuth2 PKCE -> 短信验证 -> 注册 -> Token 交换 -> API Key
    """

    AUTH_URL = "https://platform.sensenova.cn/oauth2/auth"
    TOKEN_URL = "https://platform.sensenova.cn/oauth2/token"
    API_BASE = "https://platform.sensenova.cn/lite/console/v1"
    IAM_BASE = "https://iam.sensecoreapi.cn/iam/authn/v1"
    IAM_IDP = "https://iam.sensecoreapi.cn/iam/idp/v1"

    def __init__(self, proxies: Optional[dict] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN",
            "Origin": "https://platform.sensenova.cn",
        })
        self.proxies = proxies

        # 状态
        self.code_verifier: Optional[str] = None
        self.code_challenge: Optional[str] = None
        self.state: Optional[str] = None
        self.login_challenge: Optional[str] = None
        self.token_code: Optional[str] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.tenant_id: Optional[str] = None

    # -------- OAuth2 / PKCE --------

    def init_oauth(self):
        """初始化 PKCE 参数"""
        self.code_verifier, self.code_challenge = generate_pkce()
        self.state = random_str(20)

    def fetch_login_challenge(self) -> str:
        """访问 OAuth2 授权页获取 login_challenge"""
        self.init_oauth()
        params = {
            "response_type": "code",
            "client_id": "nova",
            "code_challenge_method": "S256",
            "code_challenge": self.code_challenge,
            "redirect_uri": "https://platform.sensenova.cn",
            "scope": "openid offline offline_access",
            "state": self.state,
            "lang": "zh-CN",
        }

        for attempt in range(3):
            resp = self.session.get(
                self.AUTH_URL, params=params, allow_redirects=True,
                proxies=self.proxies, timeout=15,
            )
            qs = parse_qs(urlparse(resp.url).query)
            challenge = qs.get("login_challenge", [None])[0]
            if challenge:
                self.login_challenge = challenge
                log.info(f"[Challenge] {challenge}")
                return challenge

            # fallback: 正则匹配
            m = re.search(r'login_challenge["\']?\s*[:=]\s*["\']?([a-f0-9]+)', resp.text)
            if m:
                self.login_challenge = m.group(1)
                log.info(f"[Challenge] from body: {self.login_challenge}")
                return self.login_challenge

            log.warning(f"未找到 challenge (attempt {attempt+1}/3)")
            time.sleep(1)

        raise RuntimeError(f"无法获取 login_challenge, URL: {resp.url}")

    def check_challenge(self) -> bool:
        """验证 challenge 是否有效"""
        resp = self.session.get(
            f"{self.IAM_BASE}/auth/checkChallenge",
            params={"challenge": self.login_challenge},
            proxies=self.proxies, timeout=10,
        )
        valid = resp.json().get("is_valid", False)
        log.info(f"[CheckChallenge] valid={valid}")
        return valid

    # -------- 短信验证 --------

    def send_sms(self, phone: str, region_code: str = "86") -> str:
        """发送短信验证码，返回 token_code"""
        resp = self.session.post(
            f"{self.IAM_BASE}/auth/nova/sendSmsCode",
            json={"phone": phone, "region_code": region_code},
            proxies=self.proxies, timeout=15,
        )
        data = resp.json()
        self.token_code = data.get("token_code", "")
        if not self.token_code:
            raise RuntimeError(f"发送验证码失败: {data}")
        log.info(f"[SMS] 已发送 -> {phone}")
        return self.token_code

    def verify_sms(self, code: str) -> dict:
        """校验短信验证码"""
        resp = self.session.post(
            f"{self.IAM_BASE}/auth/nova/smsLogin",
            json={
                "token_code": self.token_code,
                "verify_code": code,
                "challenge": self.login_challenge,
            },
            proxies=self.proxies, timeout=15,
        )
        return resp.json()

    # -------- 注册 --------

    def register(self, username: str, password: str) -> str:
        """注册账号，返回 redirect URL"""
        resp = self.session.post(
            f"{self.IAM_BASE}/auth/nova/register",
            json={
                "token_code": self.token_code,
                "user_name": username,
                "password": password,
                "challenge": self.login_challenge,
            },
            proxies=self.proxies, timeout=15,
        )
        data = resp.json()
        redirect = data.get("redirect") or data.get("redirect_to") or data.get("redirect_uri") or ""
        if not redirect:
            raise RuntimeError(f"注册失败: {data}")
        log.info(f"[Register] 完成 -> {redirect[:60]}...")
        return redirect

    # -------- Token 交换 --------

    def exchange_code_for_token(self, redirect_url: str) -> dict:
        """跟随 OAuth2 重定向，提取 authorization_code 并交换 token"""
        log.info("[Token] 获取授权码...")
        resp = self.session.get(
            redirect_url, allow_redirects=True, proxies=self.proxies, timeout=15,
        )
        final = resp.url
        qs = parse_qs(urlparse(final).query)

        if "code" in qs:
            return self._do_exchange(qs["code"][0])

        # 回到登录页带 login_verifier 的情况
        challenge = qs.get("login_challenge", [None])[0]
        if challenge and qs.get("login_verifier", [None]):
            data = self.session.post(
                f"{self.IAM_BASE}/auth/nova/smsLogin",
                json={"token_code": self.token_code, "challenge": challenge},
                proxies=self.proxies, timeout=15,
            ).json()
            redirect2 = data.get("redirect") or data.get("redirect_to") or data.get("redirect_uri") or ""
            if redirect2:
                return self.exchange_code_for_token(redirect2)

        raise RuntimeError(f"无法获取授权码: {final[:200]}")

    def _do_exchange(self, code: str) -> dict:
        """code -> access_token"""
        resp = self.session.post(
            self.TOKEN_URL,
            data={
                "code": code,
                "redirect_uri": "https://platform.sensenova.cn",
                "code_verifier": self.code_verifier,
                "state": self.state,
                "client_id": "nova",
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            proxies=self.proxies, timeout=15,
        )
        data = resp.json()
        self.access_token = data.get("access_token", "")
        self.refresh_token = data.get("refresh_token", "")
        if not self.access_token:
            raise RuntimeError(f"Token 交换失败: {data}")

        log.info(f"[Token] access={self.access_token[:30]}...")
        payload = decode_jwt_payload(self.access_token)
        if payload:
            ext = payload.get("ext", {})
            self.user_id = ext.get("user_id", "")
            self.tenant_id = ext.get("tenant_id", "")
        return data

    # -------- API Key --------

    def get_api_keys(self) -> list:
        """获取已存在的 API Key 列表"""
        resp = self.session.get(
            f"{self.API_BASE}/metered/api-keys",
            params={"key_type": "API_KEY_TYPE_TOKEN_PLAN", "page_size": 10},
            headers={"Authorization": f"Bearer {self.access_token}"},
            proxies=self.proxies, timeout=10,
        )
        keys = resp.json().get("api_keys", [])
        log.info(f"[API Keys] {len(keys)} 个 key")
        return keys

    def create_api_key(self, name: Optional[str] = None) -> dict:
        """创建 API Key（fallback 逻辑）"""
        if not name:
            name = f"apikey-{time.strftime('%Y%m%d%H%M%S')}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        for method, url in [("post", ""), ("put", "")]:
            try:
                fn = getattr(self.session, method)
                resp = fn(
                    f"{self.API_BASE}/metered/api-keys",
                    json={"displayname": name, "key_type": "API_KEY_TYPE_TOKEN_PLAN"},
                    headers=headers, proxies=self.proxies, timeout=15,
                )
                if resp.status_code == 200 and resp.json().get("api_key"):
                    return resp.json()
            except Exception:
                continue
        raise RuntimeError("无法创建 API Key")

    def get_user_info(self) -> dict:
        """获取用户详细信息"""
        if not self.user_id:
            return {}
        try:
            return self.session.get(
                f"{self.IAM_IDP}/users/{self.user_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                proxies=self.proxies, timeout=10,
            ).json()
        except Exception:
            return {}

    def refresh_access_token(self) -> bool:
        """用 refresh_token 刷新"""
        if not self.refresh_token:
            return False
        try:
            data = self.session.post(
                self.TOKEN_URL,
                data={
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                    "client_id": "nova",
                    "scope": "openid offline offline_access",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                proxies=self.proxies, timeout=15,
            ).json()
            if data.get("access_token"):
                self.access_token = data["access_token"]
                return True
        except Exception:
            pass
        return False
