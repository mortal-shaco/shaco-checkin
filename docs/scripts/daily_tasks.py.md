# 二重螺旋皎皎角每日任务

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/daily_tasks.py`
- 青龙命令：`python3 scripts/daily_tasks.py`
- 建议 Cron：`3 8 * * *`
- 发布哈希：`a56f32a514141fb406f6881f762254bbc5a27d4c8fac9ff9b201642939bb77b9`
- 许可证：`MIT`

## 脚本功能

- 完成皎皎角社区每日浏览、点赞、分享、回复与社区签到
- 正式回复优先使用一言 HTTPS 随机文案并保留署名，失败或断网预演回退本地文案
- 支持 App 签名模式与设备码；access token 失效且配置了 refreshToken 时可自动续期
- 显示官方返回的昵称或公开 UID，方便核对账号
- 每行一个账号；完全断网预演、时间轴日志、账号与任务统计、单行 TASK_SUMMARY
- 青龙脱敏通知及全局开关，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `DNA_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 Android 模拟器安装并登录「皎皎角」App（勿用网页 token）。从 App 数据提取 token（user_data.xml 登录会话）与设备码 devCode（如 g_hu_sp.xml 的 dv_id），可选长期 refreshToken（login_data.refreshToken）。将同一账号的 token、设备码与可选 refreshToken 写在同一行。
- 填写格式：每个非空行一个账号：token|devCode 或 token|devCode|refreshToken。仅按竖线拆分字段；不要用 &、@ 分隔多账号。

### 可选参数

### `DNA_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：未设置 DNA_ACCOUNTS 时使用。来源同 App token，可多行对应多账号。
- 填写格式：每行一个 access token；须与 DNA_DEVICE_CODE 按行对应（或设备码仅一行共用）。

### `DNA_DEVICE_CODE`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：与 DNA_TOKEN 配套的 App 设备码（devCode）。
- 填写格式：每行一个设备码；行数为 1 或与 DNA_TOKEN 相同。

### `DNA_REFRESH_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：可选长期 refreshToken；access token 返回 220 时自动续期。可在 DNA_ACCOUNTS 第三字段或本变量中配置。
- 填写格式：每行一个 refreshToken；行数为 1 或与账号数相同。

### `DNA_SIGN_MODE`

- 必填：否
- 敏感：否
- 获取或设置：按需强制签名模式；默认有设备码时使用 app。
- 填写格式：h5 或 app。

### `DNA_LOCAL_TEXT`

- 必填：否
- 敏感：否
- 获取或设置：评论失败回退或断网预演使用的本地文案；正式运行优先请求一言，且不会向一言发送账号凭据。
- 填写格式：多行或逗号分隔短文本，单条不超过 280 字。

### `DNA_HTTP_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按需设置业务请求超时秒数。
- 填写格式：正数秒，默认 15。

### `DNA_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：手动设为 1 开启完全断网配置预演。
- 填写格式：1、true、yes、on 开启；默认关闭。

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

每个非空行一个账号；同一账号的 token、设备码与可选 refreshToken 写在同一行并用竖线连接；账号独立执行，任一账号失败则进程非零退出。

## 验证与兼容性

SHA-256 `a56f32a514141fb406f6881f762254bbc5a27d4c8fac9ff9b201642939bb77b9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3b82fe4eb92e84d2`。

## 副作用与风险

- 正式运行时浏览社区帖子并增加浏览计数
- 正式运行时对推荐帖子点赞
- 正式运行时上报分享任务完成
- 正式运行时在帖子评论区发布回复文案
- 正式运行时执行社区签到并可能领取经验/金币类奖励
- 正式运行且配置 refreshToken、access token 失效时会续期并使用新 token
- 正式运行且通知开启、青龙组件可用时发送脱敏任务汇总

## 许可证与来源

上游 `abyss-stars/dna-sign` / `src/daily_tasks.py` / `9c33ca7dd0bb92b177563e0d6c1274f9ff0d61b5`。
