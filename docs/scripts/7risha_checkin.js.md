# 七日杀中文网每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/7risha_checkin.js`
- 青龙命令：`node scripts/7risha_checkin.js`
- 建议 Cron：`* * * * *`
- 发布哈希：`ae65221af5a7a8671f24fe7217fcf996ca4e0e9c2ff3f8a07bd09217fb98b7ec`
- 许可证：`MIT`

## 脚本功能

- 使用 WordPress Cookie 执行七日杀中文网每日签到。
- 识别签到成功、今日已签到和累计签到天数，分别提示绑定手机号、绑定邮箱及登录态异常。
- 保留本地时间默认 08:30、固定与每日随机时间、60 分钟执行窗口、当日完成记录和手动运行开关。
- 支持换行多账号、旧版参数别名、独立账号错误处理与整体失败退出。
- 显示官方返回的非敏感昵称、用户名或公开编号。
- 提供断网预演、阶段日志、账号统计、单行结构化汇总和可配置青龙通知。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `RISHA_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录 https://www.7risha.com 后打开 /sign，在开发者工具网络面板找到本站已登录请求，复制请求头 Cookie，应包含 wordpress_logged_in_ 开头的登录字段。失效后重新获取。
- 填写格式：每个非空行一个完整 Cookie，保留字段值中的等号和分号，不用 & 或 @ 分隔账号。

### 可选参数

### `risha_cookie`

- 必填：否
- 敏感：是
- 获取或设置：旧版兼容输入，获取方式同 RISHA_COOKIE，优先使用 RISHA_COOKIE。
- 填写格式：每个非空行一个完整 Cookie。

### `RISHA_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要完全断网预演时设置。
- 填写格式：1 或 true 开启，不发起签到或通知网络请求，不读写状态文件。

### `RISHA_TIME_ENABLED`

- 必填：否
- 敏感：否
- 获取或设置：需要自定义时间时设置，兼容 risha_time_enabled。
- 填写格式：true 或 1 开启；默认关闭并使用本地时间 08:30。

### `RISHA_TIME_MODE`

- 必填：否
- 敏感：否
- 获取或设置：选择自定义时间模式，兼容 risha_time_mode。
- 填写格式：fixed 固定时间，random 每日区间随机。

### `RISHA_TIME`

- 必填：否
- 敏感：否
- 获取或设置：固定模式下设置，兼容 risha_time。
- 填写格式：HH:MM，非法值回落到 08:30。

### `RISHA_TIME_RANGE`

- 必填：否
- 敏感：否
- 获取或设置：随机模式下设置，兼容 risha_time_range。
- 填写格式：HH:MM-HH:MM，同日结束时间晚于开始时间，包含两端点；非法值回落到 08:30。

### `RISHA_MANUAL_RUN`

- 必填：否
- 敏感：否
- 获取或设置：立即运行时开启，运行后自行关闭。兼容 risha_manual_run 和 manualRun。
- 填写格式：true 或 1 开启，默认关闭；忽略时间窗口和本地当日记录。

### `RISHA_STATE_FILE`

- 必填：否
- 敏感：否
- 获取或设置：按需指定青龙可写文件绝对路径，父目录必须存在。
- 填写格式：默认脚本同目录 .7risha-state.json，仅保存 Cookie 的 SHA-256 摘要和成功日期。异常退出遗留 .lock 目录时，确认任务停止后删除该目录。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：自动模式下指定通知范围，默认未列入。
- 填写格式：逗号、分号、空白或换行分隔，支持 33127dbe2f8bdda2、candidate.js、7risha_checkin.js、checkin/7risha_checkin.js 和星号通配；空值关闭全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：按需指定现有通知模块目录，默认查找 /ql/data/scripts、/ql/scripts。
- 填写格式：包含 sendNotify.js 的目录路径。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

RISHA_COOKIE 每个非空行一个账号，完整保留 Cookie 字段与字段值。逐个处理，任一账号失败则整体非零退出。

## 验证与兼容性

SHA-256 `ae65221af5a7a8671f24fe7217fcf996ca4e0e9c2ff3f8a07bd09217fb98b7ec`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/33127dbe2f8bdda2`。

## 副作用与风险

- 向七日杀中文网提交每日签到，可能获得站点签到奖励。
- 正式运行创建本地状态锁，成功后写入账号摘要和完成日期。
- 正式运行在通知策略启用时发送脱敏任务摘要。

## 许可证与来源

上游 `Crack22/loon-plugins` / `loon-7risha/7risha_checkin.js` / `ad773e4ef9ca80a70546b9f99668f8430b90e16c`。
