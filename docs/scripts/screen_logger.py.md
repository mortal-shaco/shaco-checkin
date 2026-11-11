# ActivityWatch 屏幕时长记录

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/screen_logger.py`
- 青龙命令：`python3 scripts/screen_logger.py`
- 建议 Cron：`49 * * * *`
- 发布哈希：`1497ba3801f2c6369c536ee17200332e2ee6d61e32030842e91af8e280b7afff`
- 许可证：`MIT`

## 脚本功能

- 按每小时计划读取 ActivityWatch HTTP 事件，不依赖工作流仓库、固定配置目录或外部应用可执行文件。
- 按指定本地时区计算当天 UTC 查询边界，保留夏令时日期边界。
- 统计电脑活跃小时数、达到阈值的休息次数与最长专注分钟数；短暂离开不重置专注段。
- 可选统计手机屏幕会话总时长、长间隔休息次数与最长专注段。
- 按真实表头定位指标列和日期列，按日期新增或更新 Google 表格，保留其他字段；无事件时跳过写入。
- 兼容单账号 SHEET_ID、显式密钥路径及既有时间、桶和工作表参数；新增每行一个账号的内联凭据配置。
- 独立处理多账号；手机失败仍保存可用电脑统计，同时返回失败；校验事件结构、表头、重复日期及写入确认。
- 断网预演验证配置、指标计算和新增更新计划，不认证、不读取密钥文件、不写表。
- 输出分阶段脱敏日志、每账号统计、整体统计及唯一 TASK_SUMMARY JSON；按青龙全局开关及选择器发送脱敏摘要，通知异常保留业务退出码。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `SCREEN_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 Google Cloud 启用 Sheets API，创建服务账号并下载 JSON 密钥，将目标表格共享给密钥中的 client_email 并授予编辑权限。表格链接 /d/ 后为 sheet_id；将密钥对象放入同一账号行的 service_account。ActivityWatch 端提供 HTTP 数据服务，从其桶列表获取 laptop_bucket 与 phone_bucket。青龙容器需通过 aw_server 访问数据源；无须本机调用应用可执行文件。
- 填写格式：每个非空行一个 JSON 对象，必填 sheet_id、service_account；可选 aw_server、laptop_bucket、phone_bucket、screen_time_tab、timezone、break_min_seconds。密钥中的换行使用 JSON 转义，不用 & 或 @ 分隔账号。

### 可选参数

### `SHEET_ID`

- 必填：否
- 敏感：否
- 获取或设置：兼容单账号：从 Google 表格 URL 的 /d/ 后提取；仅在未设置 SCREEN_ACCOUNTS 时使用。
- 填写格式：单个表格标识，需配套 GSA_KEY_JSON 或显式 GSA_KEY_PATH。

### `GSA_KEY_JSON`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号：Google Cloud 服务账号密钥 JSON；推荐改用 SCREEN_ACCOUNTS 将配套参数放在同一行。
- 填写格式：完整 JSON 对象，仅兼容 SHEET_ID。

### `GSA_KEY_PATH`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容路径：由使用者显式挂载自己的服务账号 JSON 文件；推荐内联 JSON，无固定私有路径依赖。
- 填写格式：文件路径；不再自动读取默认密钥或 .env；断网预演不读取文件。

### `AW_SERVER`

- 必填：否
- 敏感：否
- 获取或设置：设置可访问的 ActivityWatch HTTP 数据服务地址；容器内 localhost 不是电脑。
- 填写格式：默认 http://localhost:5600；允许 HTTP 或 HTTPS，不含用户名、密码、查询参数和片段。

### `LAPTOP_BUCKET`

- 必填：否
- 敏感：否
- 获取或设置：从 ActivityWatch 的桶列表选择电脑 AFK 数据桶。
- 填写格式：默认 aw-watcher-afk_<主机名>，每行 laptop_bucket 可覆盖。

### `PHONE_BUCKET`

- 必填：否
- 敏感：否
- 获取或设置：如需手机统计，从同一服务的桶列表选择 Android 屏幕会话数据桶。
- 填写格式：默认空，仅统计电脑；每行 phone_bucket 可覆盖。

### `SCREEN_TIME_TAB`

- 必填：否
- 敏感：否
- 获取或设置：在目标表格创建工作表，并设置 local_date、laptop_screen_hours、laptop_breaks_count、laptop_longest_focus_block_min 表头；手机启用时还需 phone_screen_hours、phone_breaks_count、phone_longest_focus_block_min。允许调整列顺序，不得重复日期或表头。
- 填写格式：默认 screen_time；每行 screen_time_tab 可覆盖。上游 SHEET_TAB 文档与实现不符，实际沿用 SCREEN_TIME_TAB。

### `TIMEZONE`

- 必填：否
- 敏感：否
- 获取或设置：按被统计设备的本地日期选择 IANA 时区。
- 填写格式：默认 America/New_York，例如 Asia/Shanghai；每行 timezone 可覆盖。

### `BREAK_MIN_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：自行设置判定长休息并重置专注段的阈值。
- 填写格式：正整数秒，默认 300；每行 break_min_seconds 可覆盖。

### `SCREEN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：验证时设置为 1；不会访问任何网络、读取密钥文件、通知或写表。
- 填写格式：1、true、yes、on 开启；允许占位密钥对象，仅验证配置和本地计算计划。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：填入需要通知的 catalogId、scripts 相对路径、文件名或文件名通配符。
- 填写格式：逗号、分号或空白分隔；* 表示全部；空值禁用自动通知。识别本文件名及 scripts/screen_logger.py、screen_logger.py、f5dda6d90f455cf3。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选设置青龙通知模块所在目录；未设置则尝试 import notify、/ql/data/scripts 和 /ql/scripts。
- 填写格式：目录路径；通知不可用或失败仅记录状态，不修改业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON 对象，表格标识、服务账号密钥与数据源配置在同一行。各账号独立处理；任一账号失败整体非零退出。

## 验证与兼容性

SHA-256 `1497ba3801f2c6369c536ee17200332e2ee6d61e32030842e91af8e280b7afff`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/f5dda6d90f455cf3`。

## 副作用与风险

- 正式运行且有可用事件时，在指定 Google 工作表中新增当天记录或更新当天的屏幕时长、休息和专注指标。
- 正式运行且通知启用并选中时，通过青龙通知模块投递脱敏任务摘要。

## 许可证与来源

上游 `michelledaviest/daily-checkin-bot` / `scripts/screen_logger.py` / `d86334d5924df2bd47084c7a55d4628c93ddbd0a`。
