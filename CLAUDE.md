# SenseNova 商汤自动注册工具

> 基于 HAR 逆向分析 + 接码平台 API 的全自动商汤账号注册与 API Key 获取工具。

## 项目结构

```
st/
  sensenova/                     # 核心 python 包
    __init__.py                  # 公开导出: SMSClient, SensenovaClient, RegistrationOrchestrator, config
    config.py                    # 配置管理(单例): 读/写 .env, 环境变量覆盖, proxies 属性
    core/
      __init__.py
      sms_client.py              # 接码平台 API 客户端: 取号/验证码/释放, 官方+卡商双引擎
      sensenova_client.py        # 商汤 OAuth2 PKCE 客户端: challenge/sms/register/token/api-key
      orchestrator.py            # 注册编排器: 8步流程控制/重试/持久化/事件回调
    utils/
      __init__.py
      crypto.py                  # PKCE生成/密码生成/用户名生成/JWT解码
      log.py                     # 统一日志: 文件+控制台+GUI事件回调(LogProxy)
  sensenova_gui.py               # tkinter 双栏GUI: 左侧配置面板, 右侧日志+结果表格
  cli.py                         # CLI 入口 (python cli.py)
  .env                           # 配置文件 (>|编辑 .env)
  data/
    accounts.json                # 注册结果持久化 (json 数组)
  api_documentation.md           # 接码平台 API 文档
  商汤注册.har                    # 浏览器 HAR 抓包 (注册流程参考)
```

## 依赖

- Python 3.12+
- `requests` (HTTP)
- `tkinter` (GUI, Python 自带)

## 注册流程 (8+1 步)

| 步骤 | 操作 | API |
|------|------|-----|
| 1 | 生成 PKCE + 获取 login_challenge | OAuth2 Auth Page |
| 2 | 接码平台取号 | /api/user/getPhone |
| 3 | 发送短信验证码 | IAM sendSmsCode |
| 4 | 轮询接码平台验证码 | /api/user/getVerifyCode (每5秒, 最多75秒) |
| 5 | 短信校验 | IAM smsLogin |
| 6 | 注册账号 | IAM register |
| 7 | 跟随重定向 -> 授权码 -> access_token | OAuth2 token |
| 8 | 获取/创建 API Key | /metered/api-keys |
| + | 注册后释放手机号 | /api/user/releasePhone |

## 关键决策记录

- 商汤注册使用 **OAuth2 PKCE** (`code_challenge_method=S256`), `client_id=nova`
- IAM API (`iam.sensecoreapi.cn`) 与 平台 API (`platform.sensenova.cn`) 分开, 需各自鉴权
- 注册流程中 smsLogin 返回的 `redirect` 指向 OAuth2 auth 端点, 跟随即可拿到 code
- 注册成功后 API Key 可能自动创建 (从 HAR 看 create_time 与注册时间一致)
- 所有 HTTP 请求必须通过代理 (默认 `127.0.0.1:10801`)
- 商汤科技项目 ID: `49041` (接码平台官方引擎), 卡商引擎项目 ID: `69454`
- ascription=1 移动取号经常无库存, 不指定运营商取号更稳定
- 用户名要求 >6 字符, 当前生成格式: `sn` + 12位随机字母数字 (共14字符)

## 使用方式

### CLI

```bash
python cli.py
```

### GUI

```bash
python sensenova_gui.py
```

### 作为库使用

```python
from sensenova import SMSClient, RegistrationOrchestrator, config

sms = SMSClient(
    base_url=config.SMS_BASE_URL,
    token=config.SMS_TOKEN,
    project_id=config.SMS_PROJECT_ID,
    proxies=config.proxies,
)
orch = RegistrationOrchestrator(sms)
result = orch.run()  # 返回 dict 或 None
```
