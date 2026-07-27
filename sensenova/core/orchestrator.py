"""
注册编排器
管理完整的自动注册流程、重试、号码释放和结果持久化
"""

import json
import time
from pathlib import Path
from typing import Callable, Optional

from sensenova.core.sms_client import SMSClient
from sensenova.core.sensenova_client import SensenovaClient
from sensenova.utils.crypto import gen_username, gen_password
from sensenova.utils.log import proxy as log


class RegistrationOrchestrator:
    """自动注册编排器"""

    MAX_RETRIES = 2

    def __init__(
        self,
        sms: SMSClient,
        data_dir: str = "data",
        platform_name: str = "商汤科技",
    ):
        self.sms = sms
        self.platform = platform_name
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[dict] = []
        self.on_event: Optional[Callable[[str, str], None]] = None

    def run(self) -> Optional[dict]:
        """执行一次注册，含重试"""
        for attempt in range(1, self.MAX_RETRIES + 2):
            log.info(f"\n{'='*40}\n注册尝试 #{attempt}\n{'='*40}")
            try:
                return self._execute()
            except Exception as e:
                log.error(f"[失败-#{attempt}] {e}")
                self._cleanup_phone()
                if attempt <= self.MAX_RETRIES:
                    time.sleep(3 * attempt)
                else:
                    log.error("达到最大重试次数")
                    return None

    def _execute(self) -> dict:
        """单次注册流程"""
        ss = SensenovaClient(proxies=self.sms.proxies)
        self._emit("step", "1/8 获取 login_challenge")

        # 1. Challenge
        ss.fetch_login_challenge()
        if not ss.check_challenge():
            raise RuntimeError("challenge 无效, 请重试")

        # 2. 取号
        self._emit("step", "2/8 获取手机号")
        phone = self.sms.get_phone()

        try:
            # 3. 发送验证码
            self._emit("step", "3/8 发送短信验证码")
            ss.send_sms(phone)

            # 4. 轮询验证码
            self._emit("step", "4/8 等待验证码")
            code = self.sms.get_verify_code(phone)

            # 5. 校验
            self._emit("step", "5/8 校验验证码")
            verify_resp = ss.verify_sms(code)
            if verify_resp.get("code") != 1 and "access_token" not in str(verify_resp):
                raise RuntimeError(f"验证码校验失败: {verify_resp.get('msg', 'unknown')}")

            # 6. 注册
            self._emit("step", "6/8 注册账号")
            username = gen_username()
            password = gen_password()
            log.info(f"[注册] 用户名={username}")
            redirect = ss.register(username, password)

            # 释放
            self._emit("step", "7/8 释放号码 & 获取 Token")
            self.sms.release_phone()

            # 7. Token
            ss.exchange_code_for_token(redirect)

            # 8. API Key
            self._emit("step", "8/8 获取 API Key")
            keys = ss.get_api_keys()
            if not keys:
                keys = [ss.create_api_key()]

            api_key = keys[0].get("api_key", "")
            user_info = ss.get_user_info()

        except Exception:
            self._cleanup_phone()
            raise

        result = {
            "platform": self.platform,
            "username": username,
            "password": password,
            "tenant_code": user_info.get("tenant_code", username),
            "user_id": ss.user_id or "",
            "phone": phone,
            "access_token": ss.access_token or "",
            "refresh_token": ss.refresh_token or "",
            "api_key": api_key,
            "api_key_name": keys[0].get("displayname", ""),
            "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.results.append(result)
        self._persist(result)
        self._emit("done", f"注册成功: {username}")
        return result

    def _cleanup_phone(self):
        if self.sms.current_phone:
            try:
                self.sms.release_phone()
            except Exception:
                pass

    def _persist(self, result: dict):
        """每条结果存为独立 JSON: data/shangtang-{username}.json"""
        name = result.get("username", "unknown")
        p = self.data_dir / f"shangtang-{name}.json"
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"[保存] {p.name}")

    def _emit(self, event: str, msg: str):
        log.info(f"[{event}] {msg}")
        if self.on_event:
            self.on_event(event, msg)

    def export(self, path: str):
        """导出所有结果为单一 JSON 文件（需要显式指定路径）"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.results, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"[导出] {p}")
