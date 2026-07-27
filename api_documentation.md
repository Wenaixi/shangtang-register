# API 对接使用指南

本文档详细说明如何通过本系统的用户 API 完成项目查询、取号（官方引擎与卡商引擎）、验证码获取及号码释放。

---

## 一、 基础说明

### 1. 鉴权机制
所有接口均需在 HTTP Header 中提供 `fcToken` 进行身份验证。请在平台的**“我的Token”**页面生成并获取您的 Token。

### 2. 调用频率与风控规则
* **频率限制**：建议整体接口调用频率**不超过 60 次/分钟**。
* **特定接口限制**：获取验证码接口同一手机号**每 5 秒最多查询 1 次**。
* **违规惩罚**：超出频率将触发限流，多次触发会被临时封禁 30 分钟；极端高频请求（恶刷/高并发攻击）将导致**清空账户余额并永久封号**。

### 3. 统一返回格式
接口返回数据结构统一遵循以下格式：
```json
{
  "code": 1,      // 状态码：1 表示成功，0 表示失败（部分列表接口可能返回 200 表示成功）
  "msg": "提示信息", // 响应消息或错误原因
  "data": {}      // 成功时返回的具体数据（可选）
}
```

---

## 二、 接口列表

### 1. 获取项目列表
查询系统支持的项目列表，支持按项目名称进行模糊搜索与过滤。

* **请求方式**：`GET`
* **接口路径**：`/api/user/projects`

#### 请求参数
| 参数名 | 参数位置 | 必填 | 数据类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **fcToken** | Header | **是** | String | 用户鉴权 Token | `abcdef123456...` |
| **project_name** | Query | 否 | String | 按项目名称搜索/过滤 | `抖音` |
| **page** | Query | 否 | Integer | 页码，默认 `1` | `1` |
| **pagesize** | Query | 否 | Integer | 每页数量，默认 `100`，最大 `200` | `100` |

#### cURL 请求示例
```bash
curl -X GET "https://domain.com/api/user/projects?project_name=抖音&page=1&pagesize=100"   -H "fcToken: your_token_here"
```

#### 返回示例
```json
{
  "code": 1,
  "data": [
    {
      "id": 123,
      "project_name": "抖音",
      "money": "0.99"
    }
  ]
}
```

---

### 2. 获取手机号（官方引擎）
通过官方引擎获取指定项目的手机号。取号成功后系统将自动扣费。

* **请求方式**：`POST`
* **接口路径**：`/api/user/getPhone`

#### 请求参数
| 参数名 | 参数位置 | 必填 | 数据类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **fcToken** | Header | **是** | String | 用户鉴权 Token | `abcdef123456...` |
| **project_id** | Body | **是** | Integer/String | 项目 ID | `123` |
| **phone** | Body | 否 | String | 指定手机号（用于二次接码） | `13800138000` |
| **isp** | Body | 否 | String | 运营商筛选（如：移动、联通、电信） | `移动` |
| **province** | Body | 否 | String | 省份筛选 | `广东` |
| **paragraph** | Body | 否 | String | 号段筛选（前3位） | `138` |
| **ascription** | Body | 否 | Integer | 卡号类型：`1` = 移动，`2` = 联通 | `1` |

#### cURL 请求示例
```bash
curl -X POST "https://domain.com/api/user/getPhone"   -H "fcToken: your_token_here"   -d "project_id=123"
```

#### 返回示例
**成功响应：**
```json
{
  "code": 1,
  "msg": "成功",
  "data": {
    "sid": "91771",
    "shop_name": "91771",
    "country_name": "中国大陆",
    "country_code": "cn",
    "country_qu": "+86",
    "uid": null,
    "phone": "18924007364",
    "sp": "电信",
    "phone_gsd": "广东 广州"
  }
}
```

**失败响应：**
```json
{
  "code": 0,
  "msg": "余额不足 / 暂时无号"
}
```

---

### 3. 获取验证码
读取已获取号码收到的短信验证码。获取成功后系统自动扣费。

> ⚠️ **重要提示与频率限制**：
> 1. `phone` 参数必须是通过「获取手机号」接口成功拿到的号码，**不支持自行指定任意手机号查码**。
> 2. 同一手机号**每 5 秒最多查询一次**。请在您的客户端/脚本中加入 `sleep(5)` 或类似延时逻辑，否则将返回错误提示。

* **请求方式**：`POST`
* **接口路径**：`/api/user/getVerifyCode`

#### 请求参数
| 参数名 | 参数位置 | 必填 | 数据类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **fcToken** | Header | **是** | String | 用户鉴权 Token | `abcdef123456...` |
| **project_id** | Body | **是** | Integer/String | 项目 ID | `123` |
| **phone** | Body | **是** | String | 通过取号接口获取到的手机号 | `13800138000` |

#### cURL 请求示例
```bash
curl -X POST "https://domain.com/api/user/getVerifyCode"   -H "fcToken: your_token_here"   -d "project_id=123&phone=13800138000"
```

#### 返回示例
**成功响应：**
```json
{
  "code": 1,
  "msg": "123456",
  "data": null
}
```

**频率超限响应：**
```json
{
  "code": 0,
  "msg": "请求过于频繁，请5秒后再试"
}
```

---

### 4. 释放号码（官方引擎 / 卡商引擎）
主动释放已获取的手机号。支持官方引擎和卡商引擎项目。

* **请求方式**：`POST`
* **接口路径**：`/api/user/releasePhone`

#### 请求参数
| 参数名 | 参数位置 | 必填 | 数据类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **fcToken** | Header | **是** | String | 用户鉴权 Token | `abcdef123456...` |
| **project_id** | Body | **是** | Integer/String | 项目 ID | `123` |
| **phone** | Body | **是** | String | 需要释放的手机号 | `13800138000` |

#### cURL 请求示例
```bash
curl -X POST "https://domain.com/api/user/releasePhone"   -H "fcToken: your_token_here"   -d "project_id=123&phone=13800138000"
```

#### 返回示例
```json
{
  "code": 1,
  "msg": "释放成功"
}
```

---

### 5. 查询对接码列表（卡商引擎）
在调用卡商引擎取号前，需先查询指定项目下的可用对接码列表，以获取 `code_id`。

* **请求方式**：`GET`
* **接口路径**：`/api/index/getCodeStoreByProjectId`

#### 请求参数
| 参数名 | 参数位置 | 必填 | 数据类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **fcToken** | Header | **是** | String | 用户鉴权 Token | `abcdef123456...` |
| **project_id** | Query | **是** | Integer/String | 卡商引擎项目 ID | `456` |
| **page** | Query | 否 | Integer | 页码，默认 `1` | `1` |
| **limit** | Query | 否 | Integer | 每页数量，默认 `20`，最大 `100` | `20` |

#### cURL 请求示例
```bash
curl -X GET "https://domain.com/api/index/getCodeStoreByProjectId?project_id=456"   -H "fcToken: your_token_here"
```

#### 返回示例
```json
{
  "code": 200,
  "data": {
    "list": [
      {
        "id": 562829,
        "code_id": 562829,
        "project_id": "456",
        "project_name": "示例项目",
        "price": "1.32",
        "zxky": "在线:210/可用:208",
        "online_number": 210,
        "available_number": 208
      }
    ],
    "total": 50
  }
}
```

---

### 6. 卡商引擎取号
使用从对接码列表获得的 `code_id` 获取手机号。取号成功后自动扣费。

> 💡 **建议**：若当前卡商取号失败，请更换其他卡商的 `code_id` 重试。

* **请求方式**：`POST`
* **接口路径**：`/api/user/getCardEnginePhone`

#### 请求参数
| 参数名 | 参数位置 | 必填 | 数据类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **fcToken** | Header | **是** | String | 用户鉴权 Token | `abcdef123456...` |
| **project_id** | Body | **是** | Integer/String | 卡商引擎项目 ID | `456` |
| **code_id** | Body | **是** | Integer/String | 对接码 ID（通过接口 5 获取） | `562829` |
| **phone** | Body | 否 | String | 指定手机号（11位数字） | `13800138000` |
| **hd** | Body | 否 | String | 指定号段（前3位数字） | `138` |
| **ascription** | Body | 否 | Integer | 卡号类型：`1` = 移动，`2` = 联通 | `1` |

#### cURL 请求示例
```bash
curl -X POST "https://domain.com/api/user/getCardEnginePhone"   -H "fcToken: your_token_here"   -d "project_id=456&code_id=562829"
```

#### 返回示例
**成功响应：**
```json
{
  "code": 1,
  "msg": "获取成功",
  "data": {
    "phone": "13800138000"
  }
}
```

**失败响应：**
```json
{
  "code": 0,
  "msg": "该卡商已下线 请重新选择"
}
```

---

## 三、 注意事项与最佳实践

1. **Header 鉴权**：所有 API 请求必须在 HTTP Header 中正确传送 `fcToken: <your_token>`，缺失或错误会导致鉴权失败。
2. **引擎对应**：
   * **官方引擎**（`getPhone`）只能使用官方引擎的项目 ID。
   * **卡商引擎**（`getCardEnginePhone`）只能使用卡商引擎的项目 ID，且需配合 `code_id` 使用。
3. **余额检查**：取号操作前请确保账户余额充足，余额不足将导致取号失败。
4. **异常处理**：使用卡商引擎时，若提示“卡商已下线”或取号失败，请重新获取对接码列表并切换至其他可用卡商。
5. **频率防控**：获取验证码必须遵循 5 秒轮询间隔，严禁恶意并发轮询，以免引发账号限制或解约封号。
