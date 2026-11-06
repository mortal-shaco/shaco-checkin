# PT站点每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_874a3b5f.py`
- 青龙命令：`python3 scripts/task_874a3b5f.py`
- 建议 Cron：`35 9 * * *`
- 发布哈希：`e6a02c5d8ee0ffbb9a9c26a42d3e56572559d22acf83e121ec3b725f5d33b3d7`
- 许可证：`MIT`

## 脚本功能

- 使用 NexusPHP 风格 Cookie 访问用户配置的签到页
- 识别「已连续签到」并提取连续天数
- 兼容常见「今日已签到」等已完成文案
- 公开用户名或 UID 展示以便核对账号
- 多账号逐行独立处理与失败汇总
- 完全断网预演、时间轴日志与单行 TASK_SUMMARY
- 青龙脱敏通知及全局通知开关

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `PT_ATTENDANCE_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录目标 NexusPHP 风格 PT 站点后，打开开发者工具网络面板，访问签到页（通常为 attendance.php），复制完整 Cookie（须含 c_secure_uid、c_secure_pass 等），并记下签到页完整 URL。在青龙环境变量中配置，切勿写入公开仓库或日志。
- 填写格式：每个非空行一个账号，格式为 attendance_url|Cookie完整值；仅按第一个 | 分割，Cookie 中后续 | 原样保留；支持空行与 # 开头注释；不要用 & 或 @ 分隔账号

### 可选参数

### `attendance_url`

- 必填：否
- 敏感：否
- 获取或设置：兼容上游单账号别名；仅当 PT_ATTENDANCE_ACCOUNTS 为空时与 c_secure_uid、c_secure_pass 成对使用
- 填写格式：HTTPS 签到页完整地址，不得内嵌用户名或密码

### `c_secure_uid`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游单账号别名；仅当 PT_ATTENDANCE_ACCOUNTS 为空时使用，从浏览器 Cookie 复制同名字段
- 填写格式：NexusPHP Cookie 字段 c_secure_uid 的值

### `c_secure_pass`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游单账号别名；仅当 PT_ATTENDANCE_ACCOUNTS 为空时使用，从浏览器 Cookie 复制同名字段
- 填写格式：NexusPHP Cookie 字段 c_secure_pass 的值

### `c_secure_ssl`

- 必填：否
- 敏感：是
- 获取或设置：可选上游别名；单账号兼容模式下若站点 Cookie 含该字段则一并填写
- 填写格式：NexusPHP Cookie 字段 c_secure_ssl 的值

### `c_secure_tracker_ssl`

- 必填：否
- 敏感：是
- 获取或设置：可选上游别名；单账号兼容模式下若站点 Cookie 含该字段则一并填写
- 填写格式：NexusPHP Cookie 字段 c_secure_tracker_ssl 的值

### `c_secure_login`

- 必填：否
- 敏感：是
- 获取或设置：可选上游别名；单账号兼容模式下若站点 Cookie 含该字段则一并填写
- 填写格式：NexusPHP Cookie 字段 c_secure_login 的值

### `domain`

- 必填：否
- 敏感：否
- 获取或设置：上游遗留字段；维护版从签到 URL 推导主机名，通常无需填写
- 填写格式：站点主机名，不含协议与路径

### `PT_ATTENDANCE_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：自定义单次 HTTPS 请求超时秒数
- 填写格式：5 到 60 的数字秒，默认 20

### `PT_ATTENDANCE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要完全断网预演、只校验配置时手动设置为 1
- 填写格式：1/true/yes/on 启用预演；默认实际执行

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要按脚本白名单启用通知时设置；空值表示全部禁用
- 填写格式：catalog-id、脚本路径、文件名或 glob，可用逗号/分号/空白/换行分隔；* 表示全部

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：仅当青龙通知脚本不在默认路径时，设为 notify.py 或 sendNotify.js 所在目录
- 填写格式：本地目录绝对路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

PT_ATTENDANCE_ACCOUNTS 中每个非空行是一个独立账号，格式 attendance_url|Cookie；仅按第一个 | 分割；逐账号访问签到页，任一账号失败时进程整体非零退出

## 验证与兼容性

SHA-256 `e6a02c5d8ee0ffbb9a9c26a42d3e56572559d22acf83e121ec3b725f5d33b3d7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/874a3b5f0c910fff`。

## 副作用与风险

- 实际执行时向用户配置的签到页发起带 Cookie 的 GET，可能改变当日签到状态并获得站点奖励
- 启用青龙通知时会向已配置渠道发送脱敏任务汇总

## 许可证与来源

上游 `JasonL111/PT_attendance` / `main.py` / `4aeb5915a1de1a1ef9dc94444e8394336d69ea5d`。
