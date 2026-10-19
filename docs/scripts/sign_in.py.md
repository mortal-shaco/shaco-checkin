# 看雪论坛签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/sign_in.py`
- 青龙命令：`python3 scripts/sign_in.py`
- 建议 Cron：`11 1 1 1 1`
- 发布哈希：`95a7949e0634c9d1a62cd3cb92552eff8bb5e1c0fb31e05237b508d63e15f463`
- 许可证：`MIT`

## 脚本功能

- 多账号看雪论坛签到，支持同账号 Cookie、CSRF token 和可选 User-Agent
- 兼容显式指定的旧配置文件及嵌套账号结构
- 使用独立标准库 HTTP 请求，固定原签到端点，限制超时及响应大小并核验业务码 0
- 显示官方返回的非敏感昵称、用户名、显示名称或公开 UID，并展示纯数字奖励积分
- 完全离线参数预演、按阶段脱敏日志及单行结构化任务汇总
- 青龙通知及全局通知开关，通知不可用不改变业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `KANXUE_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录 https://bbs.kanxue.com，在浏览器开发者工具网络面板查看 user-signin.htm 签到请求，取得同一账号的 Cookie 请求头和 csrf_token 表单值。可选复制 User-Agent；抓取请求可能已完成当天签到。凭据过期后重新登录获取，不要公开。旧配置兼容入口为 KANXUE_CONFIG。
- 填写格式：每个非空行一个 JSON 对象，必填 cookie、csrf_token 字符串，可选 user_agent、account_name；JSON 内保留完整凭据，不用任何分隔符拆分账号。

### 可选参数

### `KANXUE_CONFIG`

- 必填：否
- 敏感：是
- 获取或设置：仅用于迁移已有 token.json，指定自己保管的文件路径；无需原仓库。KANXUE_ACCOUNTS 非空时优先使用账号变量。
- 填写格式：本地文件路径；文件含 kanxue.accounts 或 kanxue.kanxue.accounts 数组，每个对象包含 cookie、csrf_token，可选 user_agent、account_name。

### `KANXUE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置为 1 开启完全离线预演；正式执行设置为 0。
- 填写格式：1 开启，0、false、no、off 或空值关闭。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：若 notify.py 无法直接导入且不在青龙标准脚本目录，可指定自己信任的通知模块目录。无需安装其他仓库；通知不可用不影响业务退出码。
- 填写格式：包含 notify.py 的本地目录路径。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认上架列表，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、scripts/相对路径、文件名或文件名通配符；* 表示全部，空值表示全部关闭。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON 对象，同一对象组合 Cookie 与 CSRF token；逐个独立执行，任一失败时整体非零退出。旧配置使用账号数组。

## 验证与兼容性

SHA-256 `95a7949e0634c9d1a62cd3cb92552eff8bb5e1c0fb31e05237b508d63e15f463`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/01041a1995eb1f55`。

## 副作用与风险

- 正式执行时向看雪论坛提交签到，可能增加账号积分
- 正式执行且通知开启时通过青龙发送脱敏任务总结

## 许可证与来源

上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/kanxue/sign_in.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
