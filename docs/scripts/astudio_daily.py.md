# AStudio 每日登录积分观测

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/astudio_daily.py`
- 青龙命令：`python3 scripts/astudio_daily.py`
- 建议 Cron：`17 9 * * *`
- 发布哈希：`7881d22db73defc11bcb28b81a9d53e035c523aea193fdc7c0eceb7999d6d1b2`
- 许可证：`MIT`

## 脚本功能

- 使用网页会话 Cookie 触发 AStudio 当天会话活跃并观测每日登录积分是否到账
- 读取 membership/plan-config 判断每日登录活动是否启用
- 签到前后回读 points/balance 的 totalBalance，仅在余额真实增加时报告观察到增长
- 支持仅查询模式（不调用 membership/me 与 points/summary）
- 支持多账号分行配置、断网预演、脱敏时间轴日志、TASK_SUMMARY 与青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ASTUDIO_COOKIES`

- 必填：是
- 敏感：是
- 获取或设置：在本人浏览器登录 https://agent.xfyun.cn/xingchen-studio/ ，打开开发者工具 → 应用/存储 → Cookie，复制同一账号下的 token、account_id，以及可选的 ssoSessionId。不要把 Cookie 发给他人或提交到公开仓库。
- 填写格式：每个非空行一个账号。支持完整 Cookie（token=...; account_id=...; ssoSessionId=...）、管道格式「备注|token|account_id|sso_session_id」（无 sso 时可省略末段；仅按前三个竖线拆分）、或整段 JSON 数组。不使用 & 或 @ 分隔账号。

### 可选参数

### `ASTUDIO_ACCOUNT_FILE`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容输入。显式指向本地账号文件时读取；未设置时不会自动扫描脚本同目录默认文件。文件内容格式与 ASTUDIO_COOKIES 相同。
- 填写格式：本地文件路径；每行一个账号或 JSON 数组。

### `ASTUDIO_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：验证配置时设为 1，不发起任何网络请求。
- 填写格式：1/true/yes/on 开启断网预演；0/false/no/off 真实执行。默认 0。

### `ASTUDIO_TASK`

- 必填：否
- 敏感：否
- 获取或设置：设为 query 时仅查询活动配置与余额，不调用活跃触发接口；也可用命令行 --query。
- 填写格式：query 或留空（默认每日登录积分观测）。

### `ASTUDIO_WAIT_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：活跃触发后等待再回读余额；网络较慢时可适当增大。
- 填写格式：非负秒数，默认 2.5。

### `ASTUDIO_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：单次 HTTP 超时；网络较慢时可适当增大。
- 填写格式：正整数秒，默认 20。

### `ASTUDIO_PROXY`

- 必填：否
- 敏感：是
- 获取或设置：可选 HTTP(S) 代理；一般无需设置。
- 填写格式：代理 URL，例如 http://127.0.0.1:7890。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：QINGLONG_NOTIFY=auto 时，用目录 ID、文件名或通配符选择需要通知的脚本；空值表示全部关闭。
- 填写格式：逗号/分号/空白/换行分隔；* 表示全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：自定义 notify.py / sendNotify.js 所在目录；默认搜索 /ql/data/scripts 与 /ql/scripts。
- 填写格式：本地目录路径。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；同一账号的 token、account_id、可选 ssoSessionId 写在同一行。Cookie、管道或 JSON 均可；管道格式仅按前三个竖线拆分。不使用 & 或 @ 分隔账号。

## 验证与兼容性

SHA-256 `7881d22db73defc11bcb28b81a9d53e035c523aea193fdc7c0eceb7999d6d1b2`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/56e1597cff520f65`。

## 副作用与风险

- 请求 membership/me 与 points/summary 触发网页会话活跃，可能促使服务端发放当日登录积分

## 许可证与来源

上游 `L0NE-6/AStudio-Daily` / `astudio_daily.py` / `5b64498f363d224e4b836f95434ef8345e5615a9`。
