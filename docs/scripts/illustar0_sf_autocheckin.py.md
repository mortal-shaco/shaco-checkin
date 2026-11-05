# SF轻小说签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/illustar0_sf_autocheckin.py`
- 青龙命令：`python3 scripts/illustar0_sf_autocheckin.py`
- 建议 Cron：`16 9 * * *`
- 发布哈希：`7e61f1fc578e14ec632bc669e6a1c83023bf56a6a88f21ac008cb8cc58aaf76d`
- 许可证：`MIT`

## 脚本功能

- 校验 SFACG Cookie 会话并显示昵称、火券余额与 VIP 等级
- 每日签到（newSignInfo；今日已签视为成功）
- 上报听书/阅读时长并领取、完成日常任务 4/5/17
- 多账号换行配置与完全断网预演
- 时间轴日志、TASK_SUMMARY 与青龙脱敏通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `SFACG_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：登录 SF轻小说（菠萝包）App，抓包访问 api.sfacg.com 的请求，复制完整 Cookie（至少包含 session_APP 与 .SFCommunity）。多账号时每行一个账号；同一账号若需单独 sfsecurity，写成 Cookie值|sfsecurity完整值（仅按第一个 | 分割）。
- 填写格式：每行一个账号 Cookie；可选 Cookie|sfsecurity

### 可选参数

### `SFACG_AUTHORIZATION`

- 必填：否
- 敏感：是
- 获取或设置：可选。来自 App 客户端请求头 authorization（Basic …）。未配置时使用上游公开客户端默认值。
- 填写格式：Basic <base64> 或纯 base64（脚本会自动补 Basic 前缀）

### `SFACG_SFSECURITY`

- 必填：否
- 敏感：是
- 获取或设置：可选。全局 sfsecurity 请求头；账号行未附带时使用。均未配置时按上游固定 nonce/device/sign 并刷新 timestamp。
- 填写格式：nonce=...&timestamp=...&devicetoken=...&sign=...

### `SFACG_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：设为 1/true/yes/on 开启完全断网预演，不发起任何业务网络请求。
- 填写格式：1/true/yes/on 或 0/false/no/off

### `SFACG_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选。单次 HTTP 请求超时秒数，默认 20。
- 填写格式：5 到 60 的整数

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选。限定参与通知的脚本选择器（catalog-id、路径、文件名或通配）。空值表示全部禁用。
- 填写格式：逗号/分号/空白/换行分隔；* 表示全部

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选。自定义 notify.py / sendNotify.js 所在目录。
- 填写格式：绝对或相对目录路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

SFACG_COOKIE 每个非空行一个账号；同一账号配套 Cookie 与可选 sfsecurity 写在同一行，仅按第一个 | 分割，后续文本保留。

## 验证与兼容性

SHA-256 `7e61f1fc578e14ec632bc669e6a1c83023bf56a6a88f21ac008cb8cc58aaf76d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/11d080ed77bec3d2`。

## 副作用与风险

- 写入每日签到状态
- 上报阅读/听书时长
- 领取并完成日常任务（任务 4/5/17）

## 许可证与来源

上游 `Illustar0/SF_AutoCheckIn` / `CheckIn.py` / `0a4af5015e664060003f7ce6f332c884221b9e14`。
