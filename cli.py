#!/usr/bin/env python3
"""
商汤自动注册工具 - CLI 入口

用法:
  python cli.py              # 单次注册
  python cli.py --count 5    # 批量注册 5 个
  python cli.py --search 商汤 # 搜索项目
  python cli.py --list       # 列出已有账号
  python cli.py --export     # 导出所有账号
"""

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from sensenova.core.orchestrator import RegistrationOrchestrator
from sensenova.core.sms_client import SMSClient
from sensenova.utils.log import setup as setup_log, proxy as log
from sensenova.config import config


DATA_DIR = PROJECT_ROOT / "data"


def _load_accounts() -> list[dict]:
    """从 data/ 目录扫描所有 shangtang-*.json"""
    if not DATA_DIR.exists():
        return []
    accounts = []
    for f in sorted(DATA_DIR.glob("shangtang-*.json")):
        try:
            accounts.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return accounts


def cmd_search(keyword: str):
    """搜索接码平台项目"""
    import requests
    setup_log()
    s = requests.Session()
    s.headers.update({"fcToken": config.SMS_TOKEN, "User-Agent": "Mozilla/5.0"})
    params = {"page": 1, "pagesize": 50}
    if len(keyword) >= 3:
        params["project_name"] = keyword
    try:
        r = s.get(
            f"{config.SMS_BASE_URL}/api/user/projects",
            params=params, proxies=config.proxies or None, timeout=15,
        )
        data = r.json()
        if data.get("code") == 1:
            projects = data.get("data", [])
            print(f'\n搜索 "{keyword}" - 找到 {len(projects)} 个项目:\n')
            print(f'  {"ID":>8}  {"项目名":<28} {"价格":>6}')
            print(f'  {"-"*8}  {"-"*28} {"-"*6}')
            for p in projects:
                pname = p["project_name"][:28]
                print(f'  {p["id"]:>8}  {pname:<28} {p.get("money","?"):>6}')
        else:
            print(f'搜索失败: {data.get("msg")}')
    except Exception as e:
        print(f"搜索异常: {e}")


def cmd_list():
    """列出已有账号"""
    data = _load_accounts()
    if not data:
        print("暂无账号记录")
        return
    print(f"\n共 {len(data)} 个账号:\n")
    print(f'  {"用户名":<16} {"密码":<18} {"API Key":<40} {"时间":<20}')
    print(f'  {"-"*16} {"-"*18} {"-"*40} {"-"*20}')
    for a in data:
        key = a.get("api_key", "")[:38]
        uname = a.get("username", "")[:16]
        pw = a.get("password", "")[:18]
        t = a.get("create_time", "")[:20]
        print(f"  {uname:<16} {pw:<18} {key:<40} {t:<20}")


def cmd_export():
    """导出所有账号的 API Key (每行一个)"""
    data = _load_accounts()
    if not data:
        print("暂无账号记录")
        return
    keys = [a["api_key"] for a in data if a.get("api_key")]
    print("\n".join(keys))


def cmd_register(count: int):
    """执行注册"""
    setup_log()

    # 验证配置
    errors = []
    if not config.SMS_BASE_URL:
        errors.append("SMS_BASE_URL 未设置")
    if not config.SMS_TOKEN:
        errors.append("SMS_TOKEN 未设置")
    if not config.SMS_PROJECT_ID:
        errors.append("SMS_PROJECT_ID 未设置")
    if errors:
        print("配置缺失:")
        for e in errors:
            print(f"  - {e}")
        print("\n请编辑 .env 文件或通过 GUI 配置")
        return 1

    log.info("="*50)
    log.info("  商汤自动注册工具 - CLI")
    log.info("="*50)
    log.info(f"  API:     {config.SMS_BASE_URL}")
    log.info(f"  项目:    {config.SMS_PROJECT_ID}")
    log.info(f"  卡号:    {config.SMS_ASCRIPTION or '不限'}")
    log.info(f"  号段:    {config.SMS_PARAGRAPH or '不限'}")
    log.info(f"  数量:    {count}")
    log.info(f"  代理:    HTTP={config.HTTP_PROXY or '无'} HTTPS={config.HTTPS_PROXY or '无'}")

    sms = SMSClient(
        base_url=config.SMS_BASE_URL,
        token=config.SMS_TOKEN,
        project_id=config.SMS_PROJECT_ID,
        ascription=config.SMS_ASCRIPTION,
        paragraph=config.SMS_PARAGRAPH,
        proxies=config.proxies or None,
    )

    orch = RegistrationOrchestrator(sms)
    ok = 0

    for i in range(count):
        if i > 0:
            log.info(f"\n等待 3 秒后进行第 {i+1} 次注册...")
            time.sleep(3)
        r = orch.run()
        if r:
            ok += 1
        elif count > 1:
            time.sleep(5)

    log.info(f"\n{'='*50}")
    log.info(f"  完成: 成功 {ok}/{count}")
    log.info(f"{'='*50}")

    if orch.results and config.REGISTER_OUTPUT:
        orch.export(config.REGISTER_OUTPUT)

    return 0 if ok > 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="商汤 SenseNova 自动注册工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cli.py                      # 单次注册
  python cli.py --count 5            # 批量注册 5 个
  python cli.py --search 商汤         # 搜索接码平台项目
  python cli.py --list               # 列出已有账号
  python cli.py --export             # 导出所有 API Key (每行一个)
        """,
    )
    parser.add_argument("--count", type=int, default=None, help="注册数量 (覆盖 .env)")
    parser.add_argument("--search", metavar="KEYWORD", help="搜索接码平台项目")
    parser.add_argument("--list", action="store_true", help="列出已有账号")
    parser.add_argument("--export", action="store_true", dest="export_keys", help="导出所有 API Key")
    args = parser.parse_args()

    if args.search:
        cmd_search(args.search)
        return 0
    if args.list:
        cmd_list()
        return 0
    if args.export_keys:
        cmd_export()
        return 0

    count = args.count or config.REGISTER_COUNT
    return cmd_register(count)


if __name__ == "__main__":
    sys.exit(main())
