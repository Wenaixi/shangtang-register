# SenseNova Auto Register

全自动商汤科技账号注册 + API Key 获取工具。基于 HAR 逆向分析 OAuth2 PKCE 流程，对接接码平台实现全自动注册。

## 功能

- 自动获取 login_challenge (PKCE)、取号、短信验证、注册、OAuth2 Token、API Key
- 失败自动释放手机号并重试 (最多 2 次)
- 支持指定卡号类型 (ascription: 1=移动 2=联通) 和号段 (paragraph: 170 等)
- **GUI**: tkinter 纯黑白极简界面，搜索项目、实时日志、结果管理 (单行复制/一键全部/删除/导出)
- **CLI**: `--search` `--list` `--export` `--count` 子命令
- 每个账号独立存储: `data/shangtang-{username}.json`
- 支持通过环境变量或 `.env` 文件配置 (含代理)

## 快速开始

### 环境要求

- Python 3.12+
- `pip install requests`

### 配置

```bash
cp .env.example .env
# 编辑 .env 填入接码平台的 token 和项目 ID
```

或者直接启动 GUI 在界面里配置和搜索项目:

```bash
python sensenova_gui.py
```

### CLI

```bash
python cli.py                    # 单次注册
python cli.py --count 5          # 批量注册 5 个
python cli.py --search 商汤      # 搜索接码平台项目
python cli.py --list             # 列出已有账号
python cli.py --export           # 导出所有 API Key (每行一个)
```

### GUI

```bash
python sensenova_gui.py
```

## 项目结构

```
st/
  sensenova/                # 核心包
    __init__.py
    config.py               # 配置管理: .env 读写, 代理
    core/
      sms_client.py         # 接码平台 API: 取号/验证码/释放
      sensenova_client.py   # 商汤 OAuth2 PKCE 客户端
      orchestrator.py       # 注册编排器: 8步/重试/持久化
    utils/
      crypto.py             # PKCE / 密码 / JWT
      log.py                # 日志 + 事件回调
  sensenova_gui.py          # tkinter 纯黑白 GUI
  cli.py                    # CLI 入口
  .env.example              # 配置模板
  api_documentation.md      # 接码平台 API 文档
```

## 注册流程

| 步骤 | 操作 | API |
|------|------|-----|
| 1 | PKCE + login_challenge | OAuth2 Auth Page |
| 2 | 接码平台取号 | /api/user/getPhone |
| 3 | 发送短信验证码 | IAM sendSmsCode |
| 4 | 轮询验证码 (5sx15) | /api/user/getVerifyCode |
| 5 | 短信校验 | IAM smsLogin |
| 6 | 注册账号 | IAM register |
| 7 | OAuth2 授权码 -> Token | oauth2/token |
| 8 | API Key | /metered/api-keys |
| + | 释放手机号 | /api/user/releasePhone |

## 配置项

| 变量 | 说明 | 示例 |
|------|------|------|
| SMS_BASE_URL | 接码平台地址 | https://www.jichisms.com |
| SMS_TOKEN | fcToken | 68ede747... |
| SMS_PROJECT_ID | 项目 ID | 49041 |
| HTTP_PROXY | HTTP 代理 | http://127.0.0.1:10801 |
| HTTPS_PROXY | HTTPS 代理 | http://127.0.0.1:10801 |
| SMS_ASCRIPTION | 卡号类型 | 1=移动 2=联通 |
| SMS_PARAGRAPH | 号段 | 170 |
| REGISTER_COUNT | 注册数量 | 1 |

## 作为库使用

```python
from sensenova import SMSClient, RegistrationOrchestrator, config

sms = SMSClient(
    base_url=config.SMS_BASE_URL,
    token=config.SMS_TOKEN,
    project_id=config.SMS_PROJECT_ID,
    proxies=config.proxies,
)
orch = RegistrationOrchestrator(sms)
result = orch.run()  # {"username": "...", "api_key": "...", ...}
```

## License

MIT
