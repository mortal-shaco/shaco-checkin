# OfficeAce 果办每日奖励

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/officeace_daily.py`
- 青龙命令：`python3 scripts/officeace_daily.py`
- 建议 Cron：`0 9 * * *`
- 发布哈希：`24733f11f9b386cbd668978df42e4c7a7140f8ef4480651d0aa73abe3d2ebb22`
- 许可证：`MIT`

## 脚本功能

- 默认领取每日签到奖励和一次性新人礼，保留 V11-HMAC-SHA256 签名接口
- --query 只读查询奖励额度积分
- --only 指定账号，支持换行多账号和兼容单账号参数
- 配套凭据及 HTTPS 地址检查和凭据获取说明
- 业务码、奖励列表与积分读数校验；任一账号失败非零退出
- 完全离线预演配置、签名及执行计划
- 阶段时间轴日志、官方非敏感身份、账号统计和 TASK_SUMMARY 汇总
- 青龙脱敏结果通知与企业微信、PushPlus 兼容推送，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `OFFICEACE_TOKENS`

- 必填：是
- 敏感：是
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。
- 填写格式：每个非空行一个账号：AK|SK|security_token|project_id|base_url，兼容前置备注。全部配套字段非空，地址为 HTTPS 根地址或 /v2；不使用 & 或 @ 分隔账号。

### 可选参数

### `OFFICEACE_AK`

- 必填：否
- 敏感：是
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：临时 AK

### `OFFICEACE_SK`

- 必填：否
- 敏感：是
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：临时 SK

### `OFFICEACE_STS`

- 必填：否
- 敏感：是
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：临时 security_token

### `OFFICEACE_PROJECT_ID`

- 必填：否
- 敏感：是
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：项目 ID

### `OFFICEACE_BASE_URL`

- 必填：否
- 敏感：是
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：网关地址

### `OFFICEACE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：开启完全离线预演，不调用业务和通知组件。
- 填写格式：1、true、yes、on 开启，默认关闭

### `OFFICEACE_RETRIES`

- 必填：否
- 敏感：否
- 获取或设置：设置幂等奖励请求的额外重试次数。
- 填写格式：0 到 5 的整数，默认 2

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：使用青龙已有通知配置，默认开启。
- 填写格式：0、false、no、off 关闭，默认 1

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 所在目录，默认使用标准青龙位置或 notify 模块。
- 填写格式：目录路径

### `NO_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：旧版兼容通知关闭开关。
- 填写格式：1、true、yes、on 关闭全部推送

### `QYWX_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从自己的企业微信群机器人配置获取推送密钥。
- 填写格式：机器人密钥或 webhook 地址，优先于 WECHAT_WEBHOOK

### `WECHAT_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：从自己的企业微信群机器人配置获取 webhook，兼容 QYWX_TOKEN。
- 填写格式：机器人密钥或 webhook 地址

### `PLUSPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从自己的 PushPlus 管理页面获取推送令牌。
- 填写格式：推送令牌，通过 HTTPS 投递

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，同行包含全部配套凭据。兼容前置备注但不打印。独立处理账号，任一账号失败整体非零退出；--only 序号可选择账号。

## 验证与兼容性

SHA-256 `24733f11f9b386cbd668978df42e4c7a7140f8ef4480651d0aa73abe3d2ebb22`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/61204ec3f68839fd`。

## 副作用与风险

- 默认领取每日签到奖励和新人礼，可能增加积分；查询和预演不领取
- 实时模式通知开启且组件或兼容推送已配置时发送脱敏任务通知

## 许可证与来源

上游 `L0NE-6/OfficeAce-Daily` / `officeace_daily.py` / `a6759a929b20a64fa44914f5115a1d3fc230ce54`。
