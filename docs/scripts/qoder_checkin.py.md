# Qoder 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/qoder_checkin.py`
- 青龙命令：`python3 scripts/qoder_checkin.py`
- 建议 Cron：`6 11 * * *`
- 发布哈希：`eccca7ad12eb3303879936e402b47f957f4892f3a2123548c29407ee6943ab32`
- 许可证：`MIT`

## 脚本功能

- 查询 Qoder 活动并领取全部可领取的 CLAIM_BENEFIT 奖励，以 CLAIMED 明确确认成功
- 临期刷新令牌、刷新失败沿用未过期令牌、查询返回 401 后强制刷新重试
- 兼容令牌字段别名、ISO 时间与秒或毫秒过期时间
- 多个 HTTPS 端点在网络错误或 HTTP 404 时回退
- 逐行多账号、逐账号设备配置、旧版环境参数和配置文件兼容
- 可选安全令牌缓存、脱敏 JSON 行日志并保留原机器记录字段
- 兼容 silent、poll、silent-poll 调用，支持每日主跑与兜底任务
- 完全断网预演、青龙通知及可选兼容推送渠道、时间轴日志和结构化任务汇总
- 活动未下发时本轮重查，兼容 QODER_EMPTY_RETRY 和 QODER_EMPTY_WAIT，默认最多查询三次、间隔二十秒

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `QODER_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：从本人已授权的 Qoder 请求取得 Authorization 中 Bearer 后的访问令牌，从本人登录会话取得刷新令牌，同账号 Cosy-* 请求头填写 device；无需运行提取器或安装客户端。
- 填写格式：每个非空行一个 JSON 对象，accessToken 或 refreshToken 至少一个；可选 expiresAt（秒、毫秒或 ISO 时间）、device 对象。兼容 token、access_token、refresh_token、expires_at 别名及旧 JSON 数组或 accounts 包装对象。环境输入优先于文件。

### 可选参数

### `QODER_CONFIG_FILE`

- 必填：否
- 敏感：否
- 获取或设置：自行提供已有配置 JSON，也可仅使用环境变量。
- 填写格式：默认脚本目录 qoder_config.json，支持 device、baseUrls、refreshMarginH（非负整数，默认 72 小时）、notify。文件缺失可正常使用环境输入。

### `QODER_ACCOUNTS_FILE`

- 必填：否
- 敏感：否
- 获取或设置：自行提供本人旧版账号 JSON，无需运行提取器。
- 填写格式：默认脚本目录 qoder_accounts.json；仅未配置 QODER_ACCOUNTS 时读取；内容为账号数组或 accounts 包装对象。

### `QODER_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：默认使用上游接口，仅在确认服务官方 HTTPS 地址后覆盖。
- 填写格式：逗号分隔 HTTPS 基址，默认 https://openapi.qoder.com.cn；网络失败或 HTTP 404 回退；禁止用户信息、查询参数、片段及重定向。

### `QODER_CACHE_FILE`

- 必填：否
- 敏感：否
- 获取或设置：可选，指定青龙可写的私有文件路径，目录应仅自己可访问。
- 填写格式：默认关闭持久化；启用后以 0600 权限原子保存轮换令牌，并创建文件锁避免并发刷新；需要支持 fcntl 的系统，账号源文件保持只读。

### `QODER_LOG_FILE`

- 必填：否
- 敏感：否
- 获取或设置：可选，指定脱敏 JSON 行日志位置。
- 填写格式：默认脚本目录 qoder_checkin.log；预演不写文件。

### `QODER_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：验证时设置为 1。
- 填写格式：1、true、yes、on 开启完全断网预演，其他值实际运行。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：按需要选择通知任务，未设置时本任务默认入选。
- 填写格式：逗号、分号或空白分隔，支持目录标识 9cceef808f4e3500、scripts/qoder_checkin.py、文件名和文件名通配符；* 全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：指定青龙 notify.py 或 sendNotify.js 所在目录，也自动查找标准目录。
- 填写格式：目录路径；通知失败或缺失时保留业务退出码。

### `QYWX_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从本人企业微信机器人设置取得 webhook 的 key，兼容配置 notify.qywxToken。
- 填写格式：机器人 key 或含 key= 的完整地址；受全局通知开关控制。

### `PLUSPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从本人 PushPlus 取得推送令牌，兼容配置 notify.plusplusToken。
- 填写格式：推送令牌；受全局通知开关控制。

### `QODER_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：指定本人信任的 HTTPS 通知接收端，兼容配置 notify.webhook。
- 填写格式：HTTPS 地址，仅发送中文标题和脱敏统计；受全局通知开关控制。

### `QODER_COSY_CLIENT_TYPE`

- 必填：否
- 敏感：否
- 获取或设置：取自本人授权 Qoder 请求中的对应 Cosy-* 头；同账号字段建议放入 QODER_ACCOUNTS 的 device 对象。
- 填写格式：字符串，对应 device.clientType；逐账号 device 优先，其次环境变量，其次配置 device；clientType 默认 10，其余默认不发送。

### `QODER_COSY_MACHINE_OS`

- 必填：否
- 敏感：否
- 获取或设置：取自本人授权 Qoder 请求中的对应 Cosy-* 头；同账号字段建议放入 QODER_ACCOUNTS 的 device 对象。
- 填写格式：字符串，对应 device.machineOS；逐账号 device 优先，其次环境变量，其次配置 device；clientType 默认 10，其余默认不发送。

### `QODER_COSY_MACHINE_HOSTNAME`

- 必填：否
- 敏感：是
- 获取或设置：取自本人授权 Qoder 请求中的对应 Cosy-* 头；同账号字段建议放入 QODER_ACCOUNTS 的 device 对象。
- 填写格式：字符串，对应 device.machineHostname；逐账号 device 优先，其次环境变量，其次配置 device；clientType 默认 10，其余默认不发送。

### `QODER_COSY_MACHINE_ID`

- 必填：否
- 敏感：是
- 获取或设置：取自本人授权 Qoder 请求中的对应 Cosy-* 头；同账号字段建议放入 QODER_ACCOUNTS 的 device 对象。
- 填写格式：字符串，对应 device.machineId；逐账号 device 优先，其次环境变量，其次配置 device；clientType 默认 10，其余默认不发送。

### `QODER_COSY_MACHINE_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：取自本人授权 Qoder 请求中的对应 Cosy-* 头；同账号字段建议放入 QODER_ACCOUNTS 的 device 对象。
- 填写格式：字符串，对应 device.machineToken；逐账号 device 优先，其次环境变量，其次配置 device；clientType 默认 10，其余默认不发送。

### `QODER_COSY_MACHINE_CODE`

- 必填：否
- 敏感：是
- 获取或设置：取自本人授权 Qoder 请求中的对应 Cosy-* 头；同账号字段建议放入 QODER_ACCOUNTS 的 device 对象。
- 填写格式：字符串，对应 device.machineCode；逐账号 device 优先，其次环境变量，其次配置 device；clientType 默认 10，其余默认不发送。

### `QODER_COSY_MACHINE_TYPE`

- 必填：否
- 敏感：否
- 获取或设置：取自本人授权 Qoder 请求中的对应 Cosy-* 头；同账号字段建议放入 QODER_ACCOUNTS 的 device 对象。
- 填写格式：字符串，对应 device.machineType；逐账号 device 优先，其次环境变量，其次配置 device；clientType 默认 10，其余默认不发送。

### `QODER_COSY_VERSION`

- 必填：否
- 敏感：否
- 获取或设置：取自本人授权 Qoder 请求中的对应 Cosy-* 头；同账号字段建议放入 QODER_ACCOUNTS 的 device 对象。
- 填写格式：字符串，对应 device.version；逐账号 device 优先，其次环境变量，其次配置 device；clientType 默认 10，其余默认不发送。

### `QODER_EMPTY_RETRY`

- 必填：否
- 敏感：否
- 获取或设置：可选，自行设置活动未下发时本轮查询次数。
- 填写格式：整数，默认 3，最小 1；非法整数使用默认值。仅无 CLAIM_BENEFIT 时重查，预演不联网或等待。

### `QODER_EMPTY_WAIT`

- 必填：否
- 敏感：否
- 获取或设置：可选，自行设置空活动重查的等待秒数。
- 填写格式：整数秒，默认 20，最小 0；非法整数使用默认值。预演不等待。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON 对象，同账号令牌、刷新令牌、过期时间与设备字段合并；按顺序独立执行，任一账号失败或活动待下发时整体非零退出。兼容旧 JSON 数组与 accounts 包装对象。

## 验证与兼容性

SHA-256 `eccca7ad12eb3303879936e402b47f957f4892f3a2123548c29407ee6943ab32`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/9cceef808f4e3500`。

## 副作用与风险

- 领取活动 Credits 奖励
- 刷新登录令牌，可能轮换刷新令牌
- 显式启用缓存时创建文件锁并以私有文件保存轮换令牌
- 实际运行时追加脱敏 JSON 行日志
- 实际运行且通知启用时向青龙及显式配置的兼容通知渠道发送脱敏统计

## 许可证与来源

上游 `spirodelazz/ide-daily-checkin` / `scripts/qoder_checkin.py` / `8e2e1237a2107afec2cddd0089fca191c6083873`。
