# Telegram每日Bot签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/telegram_daily_checkin.py`
- 青龙命令：`python3 scripts/telegram_daily_checkin.py`
- 建议 Cron：`33 8 * * *`
- 发布哈希：`6618e772e6e7cdcd6b3642f655d348ffe28486785ff919799588f499929dc40f`
- 许可证：`MIT`

## 脚本功能

- 使用本人 Telegram MTProto 账号会话，向配置的多个 Bot 执行每日签到类动作
- 支持 send_command、send_message、click_button；manual_ui_required 明确失败而不假装成功
- 显示官方返回的用户名、显示名称或公开 UID，方便核对账号
- 每行一个账号，Bot 失败隔离；可选 SOCKS5 与显式随机间隔
- 完全断网预演、时间轴日志、账号与任务统计、单行 TASK_SUMMARY
- 青龙脱敏通知及全局开关，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `TELEGRAM_DAILY_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 https://my.telegram.org/apps 登录本人 Telegram 账号创建应用，取得 api_id 与 api_hash；再在可信本机用 Telethon 一次性登录并导出 StringSession。将同一账号的标签、api_id、api_hash、StringSession 与机器人动作写在同一行。不要把会话发给他人，也不要填入示例占位值用于正式运行。
- 填写格式：每个非空行一个账号。推荐：账号标签|api_id|api_hash|string_session|机器人配置。仅按前四个竖线拆分，机器人配置保留原文。机器人简写为 @BotA:/checkin;@BotB:Daily（以 / 开头视为 send_command，否则 send_message）；复杂动作可用 JSON 数组，例如 [{"username":"@BotA","actions":[{"type":"send_command","value":"/start"},{"type":"click_button","value":"Daily","wait_seconds":5}]}] 。也支持 api_id|api_hash|session|bots，或在已设置 TELEGRAM_API_ID/TELEGRAM_API_HASH 时使用 账号标签|session|bots。不使用 &、@ 分隔多账号。

### 可选参数

### `TELEGRAM_API_ID`

- 必填：否
- 敏感：是
- 获取或设置：与 TELEGRAM_DAILY_ACCOUNTS 相同，来自 https://my.telegram.org/apps；作为各账号行可省略的全局 api_id。
- 填写格式：正整数。

### `TELEGRAM_API_HASH`

- 必填：否
- 敏感：是
- 获取或设置：与 TELEGRAM_API_ID 配套，来自 https://my.telegram.org/apps。
- 填写格式：Telegram 应用 api_hash 字符串。

### `TELEGRAM_DAILY_BOTS`

- 必填：否
- 敏感：否
- 获取或设置：当账号行未写机器人配置时使用的默认 Bot 动作列表；按需填写。
- 填写格式：与账号行机器人配置相同：简写 @Bot:/command 或多个用分号分隔，或 JSON 动作数组。

### `TELEGRAM_DAILY_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：手动设为 1 开启完全断网配置预演。
- 填写格式：1、true、yes、on 开启；默认关闭。

### `TELEGRAM_DAILY_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按需设置 Telethon 请求超时秒数。
- 填写格式：正整数秒，默认 30。

### `TELEGRAM_DAILY_INITIAL_DELAY_MIN_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按需设置正式运行初始随机延迟下限；默认 0，预演不等待。
- 填写格式：非负整数秒。

### `TELEGRAM_DAILY_INITIAL_DELAY_MAX_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按需设置正式运行初始随机延迟上限；默认 0。
- 填写格式：非负整数秒，且不小于最小值。

### `TELEGRAM_DAILY_BETWEEN_BOT_MIN_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按需设置同一账号内 Bot 间隔下限；默认 0。
- 填写格式：非负整数秒。

### `TELEGRAM_DAILY_BETWEEN_BOT_MAX_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按需设置同一账号内 Bot 间隔上限；默认 0。
- 填写格式：非负整数秒。

### `TELEGRAM_DAILY_BETWEEN_ACCOUNT_MIN_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按需设置账号间隔下限；默认 0。
- 填写格式：非负整数秒。

### `TELEGRAM_DAILY_BETWEEN_ACCOUNT_MAX_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按需设置账号间隔上限；默认 0。
- 填写格式：非负整数秒。

### `TELEGRAM_DAILY_PROXY_ENABLED`

- 必填：否
- 敏感：否
- 获取或设置：需要经 SOCKS5 访问 Telegram 时显式开启；默认关闭。兼容 PROXY_ENABLED。
- 填写格式：1、true、yes、on 开启。

### `TELEGRAM_DAILY_PROXY_HOST`

- 必填：否
- 敏感：否
- 获取或设置：启用代理后填写 SOCKS5 主机；兼容 PROXY_HOST。
- 填写格式：主机名或 IP，不含凭据。

### `TELEGRAM_DAILY_PROXY_PORT`

- 必填：否
- 敏感：否
- 获取或设置：启用代理后填写端口；兼容 PROXY_PORT。
- 填写格式：正整数，默认 1080。

### `TELEGRAM_DAILY_PROXY_USERNAME`

- 必填：否
- 敏感：是
- 获取或设置：代理需要认证时填写；兼容 PROXY_USERNAME。
- 填写格式：代理用户名。

### `TELEGRAM_DAILY_PROXY_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：代理需要认证时填写；兼容 PROXY_PASSWORD。
- 填写格式：代理密码。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：设置后仅当选择器匹配本脚本目录 ID、路径或文件名时发送通知；空值禁用全部。
- 填写格式：逗号、分号、空白或换行分隔；支持 * 通配。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选填写青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：本地目录路径；业务不依赖此文件。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；同一账号的 api_id、api_hash、StringSession 与机器人配置写在同一行并用竖线连接；账号独立执行，任一账号失败则进程非零退出。

## 验证与兼容性

SHA-256 `6618e772e6e7cdcd6b3642f655d348ffe28486785ff919799588f499929dc40f`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/2422813024d0fddc`。

## 副作用与风险

- 正式运行时向目标 Bot 发送命令或消息，并可能点击聊天内按钮，从而触发该 Bot 的签到或任务状态变化
- 正式运行且通知开启、青龙组件可用时发送脱敏任务汇总

## 许可证与来源

上游 `redwan-cse/telegram-daily-checkin` / `telegram_daily_checkin.py` / `67be15b79b34cdd112208e33cfe7524d90df7e45`。
