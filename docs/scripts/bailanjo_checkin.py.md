# Bailanjo 自动签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/bailanjo_checkin.py`
- 青龙命令：`python3 scripts/bailanjo_checkin.py`
- 建议 Cron：`31 2 * * *`
- 发布哈希：`e218734d85c1f2eff92fdc16fa00073124135bbbc43c0a9362ac5b411702e00c`
- 许可证：`MIT`

## 脚本功能

- 通过 Bailanjo 用户页查询账号状态并保持站点会话。
- 执行每日签到，并严格区分签到成功、今日已签到与无法验证的响应。
- 展示官方返回的公开 UID、余额、累计钻石和本次余额增量。
- 支持每行一个账号的多账号独立处理，并在任一账号失败时返回非零退出码。
- 支持完全断网的多账号预演，不调用业务站点或任何通知服务。
- 保留 Telegram、Server酱、PushPlus、Bark、Discord、飞书、钉钉和企业微信推送，并支持青龙统一通知。
- 输出带时间戳的分阶段日志、逐账号统计和单行 TASK_SUMMARY JSON 汇总。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `BAILANJO_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 Bailanjo 用户页使用的账号和密码；每个账号单独占一行填写。
- 填写格式：每个非空行均为 账号|密码，只在第一个竖线处分割；不要用 & 或 @ 分隔多个账号。

### 可选参数

### `BAILANJO_ACCOUNT`

- 必填：否
- 敏感：是
- 获取或设置：旧版单账号兼容变量；仅在未设置 BAILANJO_ACCOUNTS 时与 BAILANJO_PASSWORD 配套使用。
- 填写格式：单个 Bailanjo 账号。

### `BAILANJO_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：旧版单账号兼容变量；填写对应账号的登录密码。
- 填写格式：单个 Bailanjo 密码。

### `BAILANJO_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置单次 HTTPS 请求超时；留空使用 15 秒。
- 填写格式：3 至 60 之间的秒数。

### `BAILANJO_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要验证配置和执行路径但禁止联网时启用；预演也会跳过所有推送。
- 填写格式：设为 1、true、yes 或 on 时启用完全断网预演。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：用于只给指定脚本发送青龙通知；可选择目录标识、脚本名或通配符。
- 填写格式：使用逗号、分号、空白或换行分隔选择器；* 表示全部；显式空值表示全部关闭。

### `TELEGRAM_BOT_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从 Telegram BotFather 创建机器人后取得；需要与 TELEGRAM_CHAT_ID 同时配置。
- 填写格式：Telegram 机器人令牌。

### `TELEGRAM_CHAT_ID`

- 必填：否
- 敏感：是
- 获取或设置：向机器人发送消息后，从 Telegram 更新信息中取得接收会话标识。
- 填写格式：Telegram 会话标识。

### `SERVERCHAN_SENDKEY`

- 必填：否
- 敏感：是
- 获取或设置：登录 Server酱 后在发送消息页面取得 SendKey。
- 填写格式：Server酱 SendKey。

### `PUSHPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：登录 PushPlus 后在一对一推送页面取得令牌。
- 填写格式：PushPlus 令牌。

### `BARK_URL`

- 必填：否
- 敏感：是
- 获取或设置：从 Bark 客户端复制包含设备密钥的 HTTPS 推送地址。
- 填写格式：以 https:// 开头且末尾包含 Bark 设备密钥的基础地址。

### `DISCORD_WEBHOOK_URL`

- 必填：否
- 敏感：是
- 获取或设置：在 Discord 频道的集成设置中创建 Webhook 后复制地址。
- 填写格式：Discord HTTPS Webhook 地址。

### `FEISHU_WEBHOOK_URL`

- 必填：否
- 敏感：是
- 获取或设置：在飞书群中添加自定义机器人后复制 Webhook 地址。
- 填写格式：飞书 HTTPS Webhook 地址。

### `DINGTALK_WEBHOOK_URL`

- 必填：否
- 敏感：是
- 获取或设置：在钉钉群中添加自定义机器人后复制 Webhook 地址。
- 填写格式：钉钉 HTTPS Webhook 地址。

### `WECHAT_WORK_WEBHOOK_URL`

- 必填：否
- 敏感：是
- 获取或设置：在企业微信群中添加群机器人后复制 Webhook 地址。
- 填写格式：企业微信 HTTPS Webhook 地址。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

BAILANJO_ACCOUNTS 中每个非空行代表一个账号，格式为账号|密码；脚本逐个独立处理，任何账号失败都会使进程非零退出。

## 验证与兼容性

SHA-256 `e218734d85c1f2eff92fdc16fa00073124135bbbc43c0a9362ac5b411702e00c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e052c233e8ebcd95`。

## 副作用与风险

- 在 Bailanjo 账号上执行每日签到并可能增加账号余额。
- 正式运行时可向已配置的推送渠道和青龙通知组件发送脱敏任务总结。

## 许可证与来源

上游 `LinVireo/bailanjo-auto-check-in` / `bailanjo_checkin.py` / `70053c89bd7da7152ee7a00838e35e77f4fab5bb`。
