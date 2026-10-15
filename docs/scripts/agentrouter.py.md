# AgentRouter签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/agentrouter.py`
- 青龙命令：`python3 scripts/agentrouter.py`
- 建议 Cron：`20 9 * * *`
- 发布哈希：`a22e06bb7c32b2ce57c1dbbea73b86dac505381bde53a818ec84254669f4c888`
- 许可证：`MIT`

## 脚本功能

- 通过 GitHub OAuth 重新登录触发每日签到，以服务端 checked_in 严格确认为成功。
- 查询并展示官方账号身份、当前余额美元换算及已用额度。
- 保留站点公开客户端配置、已知客户端编号和额度换算比例兜底。
- 支持每行一个账号、原 JSON 配置格式、账号站点与用户编号配置、代理与可信 CA 证书。
- 支持显式启用首次 GitHub OAuth 授权；默认要求浏览器手动授权。
- 每天 09:20 运行，多账号间隔五秒。
- 完全断网预演、分阶段日志、账号与子任务统计、单行 TASK_SUMMARY 汇总及青龙脱敏通知。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `AGENTROUTER_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：先在浏览器登录 GitHub 并手动完成 AgentRouter 的 GitHub 授权；在开发者工具的 Application/Cookies/github.com 中复制 user_session 值。每行一个账号，也可用 JSON 对象组合该账号配置。
- 填写格式：每个非空行一个 user_session 值或 JSON 对象；对象必填 github_session，可填 account_name、base_url、user_id、proxy、verify；不使用 & 或 @ 分隔账号。

### 可选参数

### `AGENTROUTER_CONFIG`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容输入：显式指定原配置文件路径；AGENTROUTER_ACCOUNTS 非空时优先使用账号变量。文件内容无需另一仓库。
- 填写格式：本地 JSON 文件路径，结构为 agentrouter.accounts 数组；账号字段与账号变量的 JSON 对象相同。user_id 可从站点用户信息取得，正常登录自动获取；verify 只允许 true 或可信 CA 文件路径，不接受 false。

### `AGENTROUTER_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：默认使用上游备用站点；需要时从本人使用的 AgentRouter 站点确认根地址。
- 填写格式：HTTPS 根地址，默认 https://ps.air-outer.com；账号 base_url 优先。

### `AGENTROUTER_PROXY`

- 必填：否
- 敏感：是
- 获取或设置：可选，从自己的代理服务取得；账号 proxy 优先。
- 填写格式：HTTP 或 HTTPS 代理地址，可含代理认证；仅用于请求，不输出。

### `HTTPS_PROXY`

- 必填：否
- 敏感：是
- 获取或设置：可选，从自己的代理服务取得；无显式代理时由 requests 使用系统代理环境。
- 填写格式：HTTP 或 HTTPS 代理地址；支持标准小写变量及 NO_PROXY。

### `HTTP_PROXY`

- 必填：否
- 敏感：是
- 获取或设置：可选，从自己的代理服务取得；保留标准 requests 代理环境兼容。
- 填写格式：HTTP 或 HTTPS 代理地址。

### `NO_PROXY`

- 必填：否
- 敏感：否
- 获取或设置：可选，按代理服务要求填写无需代理的主机；沿用 requests 标准行为。
- 填写格式：逗号分隔的主机名或域名规则。

### `AGENTROUTER_CA_BUNDLE`

- 必填：否
- 敏感：否
- 获取或设置：可选，从可信证书管理员获取 PEM CA 文件；默认使用 requests 受信任证书，并在 Windows 合并系统根证书。
- 填写格式：本地 CA 文件路径；账号 verify 路径优先，始终开启 TLS 校验。

### `AGENTROUTER_ALLOW_AUTHORIZE`

- 必填：否
- 敏感：否
- 获取或设置：仅在理解 GitHub 应用授权权限后自行启用；默认要求先在浏览器手动授权。
- 填写格式：默认 0；设为 1 允许首次授权表单提交，会授予应用权限。

### `AGENTROUTER_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：验证配置时设为 1；也支持 --dry-run。
- 填写格式：1 为完全断网预演，不登录、不查询、不发送通知。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：使用青龙自带通知配置，默认开启；不需要填写通知凭据到本脚本。
- 填写格式：默认 1；0、false、no、off 关闭；预演只展示通知摘要。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，指定青龙 notify.py 或 sendNotify.js 所在目录；默认自动查找标准青龙目录。
- 填写格式：本地目录路径，通知失败或不可用不影响业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；每行可为独立 GitHub user_session 值或包含 github_session 的 JSON 对象，配套账号配置在同一对象中；账号独立处理，任一失败整体非零退出。

## 验证与兼容性

SHA-256 `a22e06bb7c32b2ce57c1dbbea73b86dac505381bde53a818ec84254669f4c888`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/81684dd327c48211`。

## 副作用与风险

- 重新登录 AgentRouter，创建登录会话并可能发放当日签到额度。
- 仅显式启用 AGENTROUTER_ALLOW_AUTHORIZE 后可提交 GitHub 首次应用授权。
- 正式运行按 QINGLONG_NOTIFY 设置发送青龙通知。

## 许可证与来源

上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/agentrouter/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
