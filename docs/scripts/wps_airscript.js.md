# AI打卡机四平台签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/wps_airscript.js`
- 青龙命令：`node scripts/wps_airscript.js`
- 建议 Cron：`31 10 * * *`
- 发布哈希：`8c707d371cd86550687952d057f8485cb0d2eb7c16490d312c5a502d58c6df60`
- 许可证：`MIT`

## 脚本功能

- ima（腾讯 AI 工作台）使用 refresh_token 刷新登录后执行每日签到，并在可领时顺带领取满签奖励。
- WorkBuddy / CodeBuddy CN 使用 Bearer token 提交每日签到，识别已签到幂等结果。
- Qoder CN 个人版按设备头查询活动并领取 Credits；支持 access/refresh 续期；可选账号文件写回新 token。
- TraeWork 国内个人版查询签到状态并领取 Credits，服务端繁忙码 9074 自动重试。
- 支持每行一个账号的多平台混排；兼容「platform|{json}」与整行 JSON。
- 按青龙全局开关与脚本名单发送脱敏通知；账号 JSON 内可选 Server酱 / PushPlus / 企业微信 Webhook 兼容推送。
- 完全断网预演：校验平台与必填字段、模拟阶段与通知摘要，不发起业务或通知网络请求。
- 提供中文时间轴日志、编号阶段、耗时、逐账号与全局统计，以及唯一单行 TASK_SUMMARY JSON。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `AIDAKA_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：规范账号变量。每个非空行填写一个平台账号。字段与上游金山文档 B 列 JSON 一致：ima 需 ima_uid、ima_guid、refresh_token（及可选 uid_type、name）；workbuddy 需 token（及可选 uid、name）；qoder 需 accessToken 或 refreshToken，且 device.machineToken 等 Cosy 设备头来自本人已登录 Qoder 客户端请求头；traework 需 token 与 device_id。platform 写在 JSON 的 platform 字段，或使用「platform|{json}」行首平台名。勿将令牌写入公开仓库或日志。相关 build.py 仅为部署页生成器，不作为凭据来源。
- 填写格式：每个非空行一个账号；推荐整行 JSON 且含 platform（ima/workbuddy/qoder/traework）。也支持 platform|{json}，只在首个竖线处拆分。以 # 开头的行忽略。不使用 & 或 @ 分隔账号。可选 serverchan/pushplus/qywx 对应原表格推送列。

### 可选参数

### `WPS_AIRSCRIPT_ACCOUNTS`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当未设置 AIDAKA_ACCOUNTS 且未使用账号文件时读取；获取方式与 AIDAKA_ACCOUNTS 相同。
- 填写格式：与 AIDAKA_ACCOUNTS 相同。

### `AIDAKA_CHECKIN_ACCOUNTS`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当 AIDAKA_ACCOUNTS 与 WPS_AIRSCRIPT_ACCOUNTS 皆为空且未使用账号文件时读取。
- 填写格式：与 AIDAKA_ACCOUNTS 相同。

### `AIDAKA_ACCOUNTS_FILE`

- 必填：否
- 敏感：是
- 获取或设置：可选私有 JSONL 账号文件绝对路径；设置后优先于环境变量。适合 Qoder 刷新后需要写回 accessToken/refreshToken 的场景；文件权限建议 0600。
- 填写格式：本地私有文件路径；每行一个账号 JSON（含 platform）或 platform|{json}。

### `AIDAKA_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要断网验证配置时手动设置；正式执行时删除或设为 0。
- 填写格式：1、true、yes、on 表示完全断网预演；其他值或未设置表示正式执行。预演不访问业务接口、不写回账号文件、不投递真实通知。

### `AIDAKA_TIMEOUT_MS`

- 必填：否
- 敏感：否
- 获取或设置：需要调整单次 HTTP 超时时间时手动设置。
- 填写格式：1000 至 120000 的整数毫秒；缺省或非法值使用 30000。

### `AIDAKA_ACCOUNT_GAP_MS`

- 必填：否
- 敏感：否
- 获取或设置：需要调整账号间间隔时手动设置；对应上游账号间隔以降低风控。
- 填写格式：0 至 60000 的整数毫秒；缺省 1500。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙通知名单中填入 ea3ec6764f1fef21、实际脚本文件名或 scripts 相对路径；未设置时默认对本任务发送通知。
- 填写格式：逗号、分号、空白或换行分隔的选择器；支持 * 与 ? 通配；* 表示全部；显式空值关闭全部青龙通知。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知工具不在默认目录时，填写本机 sendNotify.js 或 notify.py 所在目录。
- 填写格式：本地目录路径。依次尝试指定目录与 /ql/data/scripts、/ql/scripts 下的 sendNotify.js，再尝试 notify.py；通知失败只记录脱敏状态。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

AIDAKA_ACCOUNTS（或兼容别名 / AIDAKA_ACCOUNTS_FILE）每个非空行一个账号；同一账号的平台凭据合并在一行 JSON 内。账号逐个独立签到，任一账号失败则整体非零退出，其余账号继续执行。

## 验证与兼容性

SHA-256 `8c707d371cd86550687952d057f8485cb0d2eb7c16490d312c5a502d58c6df60`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/ea3ec6764f1fef21`。

## 副作用与风险

- 正式运行时向 ima.qq.com 提交每日签到与满签奖励领取，可能更新积分或签到状态。
- 正式运行时向 www.codebuddy.cn 提交 WorkBuddy 每日签到。
- 正式运行时向 openapi.qoder.com.cn 领取活动 Credits，并可能刷新 accessToken/refreshToken。
- 正式运行时向 api.trae.cn 提交 TraeWork 签到积分领取。
- 启用通知且非预演时，通过青龙 notify 及可选兼容推送渠道发送脱敏账号统计。

## 许可证与来源

上游 `a1007479270/aidaka` / `wps-airscript/checkin.js` / `7bf15f9330e7ce7114aa519880b4bc71b11c4275`。
