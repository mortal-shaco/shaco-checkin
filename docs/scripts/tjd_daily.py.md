# 塔吉多每日任务

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/tjd_daily.py`
- 青龙命令：`python3 scripts/tjd_daily.py`
- 建议 Cron：`24 2 * * *`
- 发布哈希：`6069885442fe7896dd513ec1c99510b74304d7fc6d3e315b3aa618c3b445d6d4`
- 许可证：`MIT`

## 脚本功能

- 社区每日签到并复核服务端任务进度
- 浏览推荐帖子，按服务端剩余次数执行和复核
- 显式启用帖子点赞，跳过已点赞帖子并复核进度
- 显式启用帖子分享回调，保留平台参数并复核进度
- 查询绑定游戏角色昵称、等级和服务器
- 绑定游戏每日签到，保留 H5 鉴权及已签到业务码 5052，执行后查询确认
- 查询任务进度、今日及累计金币、游戏签到状态
- 凭据失效时用可选账号密码自动重登一次，内置 AES 加密和签名，凭据仅在内存更新
- 支持 --only、--account、--config、--no-notify 和 --loop；预演只运行一轮
- 换行多账号及旧变量兼容、断网预演、阶段日志、青龙脱敏通知和单行机器汇总

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `TJD_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录塔吉多 App，通过本人授权抓包获取 bbs-api.tajiduo.com 请求头 Authorization 和 deviceid。可选 phone/password 是本人完美世界账号；openudid/vendorid 从同一设备登录请求获取。
- 填写格式：每个非空行一个 JSON 对象，必含 token、deviceid 字符串；可选 uid（默认 0）、name、phone、password、openudid、vendorid、account_uid。兼容旧 JSON 对象或数组，不以 & 或 @ 分账号。

### 可选参数

### `TJD_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：本人 App 请求头 Authorization；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。

### `TJD_DEVICEID`

- 必填：否
- 敏感：是
- 获取或设置：与 Authorization 相同请求的 deviceid 头，此变量在脚本中实际读取；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。

### `TJD_UID`

- 必填：否
- 敏感：否
- 获取或设置：同一请求的 uid 头，缺省为 0；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。

### `TJD_NAME`

- 必填：否
- 敏感：否
- 获取或设置：自行设置账号标签，仅用于 --account 过滤；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。

### `TJD_PHONE`

- 必填：否
- 敏感：是
- 获取或设置：本人完美世界账号手机号；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。

### `TJD_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：本人完美世界账号密码；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。

### `TJD_OPENUDID`

- 必填：否
- 敏感：是
- 获取或设置：同一设备登录请求 openudid；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。

### `TJD_VENDORID`

- 必填：否
- 敏感：是
- 获取或设置：同一设备登录请求 vendorid；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。

### `TJD_TASKS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置，点赞和分享必须明确选择。
- 填写格式：逗号分隔 signin、gamesign、browse、like、share、status；默认 signin,gamesign,browse；--only 优先。

### `TJD_SHARE_PLATFORM`

- 必填：否
- 敏感：否
- 获取或设置：自行选择分享回调平台。
- 填写格式：qq、wechat、timeline 或 wb；默认 qq，不发布文字。

### `TJD_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：设置为 1 进行完全断网预演。
- 填写格式：1 启用；0、false、no、off 关闭。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙全局通知开关。
- 填写格式：默认 1；0、false、no、off 禁用。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：填写青龙 notify.py 所在目录，也自动查找标准青龙目录。
- 填写格式：本地目录路径，通知失败保留业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON 对象，同账号凭据组合在一行。兼容旧 JSON 数组和换行对齐的旧变量。各账号独立执行，任一失败整体非零退出。

## 验证与兼容性

SHA-256 `6069885442fe7896dd513ec1c99510b74304d7fc6d3e315b3aa618c3b445d6d4`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e096ba77bcda7172`。

## 副作用与风险

- 社区签到增加金币和经验
- 浏览帖子增加阅读及任务进度
- 绑定游戏签到领取奖励
- 明确启用后给帖子点赞
- 明确启用后上报帖子分享回调
- 可选密码重登创建登录会话，可能使旧会话失效

## 许可证与来源

上游 `SkyBlue997/tjd-daily` / `tjd_daily.py` / `1df775d4c5eea379111edecf53a62b447b756770`。
