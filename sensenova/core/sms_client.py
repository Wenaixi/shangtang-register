"""
接码平台 API 客户端
支持官方引擎 (getPhone) 和卡商引擎 (getCardEnginePhone)
"""

from typing import Optional

import requests

from sensenova.utils.log import proxy as log


class SMSClient:
    """接码平台 API 客户端"""

    def __init__(
        self,
        base_url: str,
        token: str,
        project_id: str,
        card_engine: bool = False,
        code_id: Optional[str] = None,
        ascription: str = "",
        paragraph: str = "",
        proxies: Optional[dict] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project_id = project_id
        self.card_engine = card_engine
        self.code_id = code_id
        self.ascription = ascription
        self.paragraph = paragraph
        self.current_phone: Optional[str] = None
        self.proxies = proxies

        self.session = requests.Session()
        self.session.headers.update({
            "fcToken": token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        })

    # ---------- 通用请求 ----------

    def _get(self, path: str, params: dict = None) -> dict:
        resp = self.session.get(
            f"{self.base_url}{path}", params=params, proxies=self.proxies, timeout=15
        )
        return resp.json()

    def _post(self, path: str, data: dict = None) -> dict:
        resp = self.session.post(
            f"{self.base_url}{path}", data=data, proxies=self.proxies, timeout=15
        )
        return resp.json()

    # ---------- 项目查询 ----------

    def get_projects(self, name: str = "", page: int = 1) -> list:
        """获取项目列表，支持按名称搜索"""
        params = {"page": page, "pagesize": 100}
        if len(name) >= 3:
            params["project_name"] = name
        data = self._get("/api/user/projects", params)
        if data.get("code") == 1:
            return data.get("data", [])
        raise RuntimeError(f"获取项目列表失败: {data.get('msg')}")

    # ---------- 取号 ----------

    def get_phone(self) -> str:
        """获取手机号，自动判断官方/卡商引擎"""
        if self.card_engine:
            return self._get_phone_card_engine()
        return self._get_phone_official()

    def _get_phone_official(self) -> str:
        payload = {"project_id": self.project_id}
        if self.ascription:
            try:
                payload["ascription"] = int(self.ascription)
            except (ValueError, TypeError):
                pass  # 非数字(如占位符文本)则忽略
        if self.paragraph:
            payload["paragraph"] = self.paragraph

        data = self._post("/api/user/getPhone", payload)
        if data.get("code") == 1:
            result = data["data"]
            self.current_phone = result["phone"]
            sid = result.get("sid", "")
            sp = result.get("sp", "")
            log.info(f"[取号] {self.current_phone} (运营商={sp} sid={sid})")
            return self.current_phone
        raise RuntimeError(f"取号失败: {data.get('msg')}")

    def _get_phone_card_engine(self) -> str:
        if not self.code_id:
            stores = self._get_code_stores()
            if not stores:
                raise RuntimeError("没有可用的卡商对接码")
            self.code_id = stores[0]["code_id"]
            log.info(f"自动选择卡商 code_id={self.code_id}")

        data = self._post("/api/user/getCardEnginePhone", {
            "project_id": self.project_id, "code_id": self.code_id,
        })
        if data.get("code") == 1:
            self.current_phone = data["data"]["phone"]
            log.info(f"[取号-卡商] {self.current_phone}")
            return self.current_phone
        raise RuntimeError(f"卡商取号失败: {data.get('msg')}")

    def _get_code_stores(self) -> list:
        data = self._get("/api/index/getCodeStoreByProjectId", {
            "project_id": self.project_id, "page": 1, "limit": 50,
        })
        if data.get("code") in (1, 200):
            return data.get("data", {}).get("list", [])
        raise RuntimeError(f"获取对接码列表失败: {data.get('msg')}")

    # ---------- 验证码 ----------

    def get_verify_code(
        self, phone: str, max_retries: int = 15, interval: int = 5
    ) -> str:
        """轮询获取短信验证码"""
        for i in range(max_retries):
            if i > 0:
                import time
                time.sleep(interval)

            data = self._post("/api/user/getVerifyCode", {
                "project_id": self.project_id, "phone": phone,
            })
            if data.get("code") == 1:
                code = data.get("msg", "")
                log.info(f"[验证码] 第{i+1}次查询 -> {code}")
                return code

            msg = data.get("msg", "")
            if "频繁" in msg or "5秒" in msg:
                log.info(f"[验证码] 频率限制 ({i+1}/{max_retries})")
            else:
                log.info(f"[验证码] 等待中 ({i+1}/{max_retries}): {msg}")

        raise TimeoutError(f"验证码获取超时 ({max_retries * interval}秒)")

    # ---------- 释放 ----------

    def release_phone(self, phone: Optional[str] = None) -> bool:
        """释放手机号"""
        phone = phone or self.current_phone
        if not phone:
            return False
        data = self._post("/api/user/releasePhone", {
            "project_id": self.project_id, "phone": phone,
        })
        ok = data.get("code") == 1
        status = "OK" if ok else data.get("msg", "?")
        log.info(f"[释放] {phone} -> {status}")
        return ok
