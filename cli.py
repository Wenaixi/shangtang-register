#!/usr/bin/env python3
"""
商汤自动注册工具 - CLI 入口
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sensenova.core.orchestrator import RegistrationOrchestrator
from sensenova.core.sms_client import SMSClient
from sensenova.utils.log import setup as setup_log, proxy as log
from sensenova.config import config


def main():
    setup_log()

    log.info("当前配置:")
    for attr in ["SMS_BASE_URL", "SMS_PROJECT_ID", "SMS_ASCRIPTION", "REGISTER_COUNT"]:
        val = getattr(config, attr, "")
        if "TOKEN" in attr.upper():
            val = val[:8] + "..." if val else ""
        log.info(f"  {attr}={val}")

    sms = SMSClient(
        base_url=config.SMS_BASE_URL,
        token=config.SMS_TOKEN,
        project_id=config.SMS_PROJECT_ID,
        ascription=config.SMS_ASCRIPTION,
        proxies=config.proxies or None,
    )

    orch = RegistrationOrchestrator(sms)
    total = config.REGISTER_COUNT
    ok = 0

    for i in range(total):
        if i > 0:
            log.info(f"\n等待 3 秒后进行第 {i+1} 次...")
            time.sleep(3)
        r = orch.run()
        if r:
            ok += 1
        elif total > 1:
            time.sleep(5)

    log.info(f"\n完成: 成功 {ok}/{total}")

    if orch.results and config.REGISTER_OUTPUT:
        orch.export(config.REGISTER_OUTPUT)

    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
