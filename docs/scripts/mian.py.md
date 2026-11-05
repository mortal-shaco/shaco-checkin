# HDSky签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/mian.py`
- 青龙命令：`python3 scripts/mian.py`
- 建议 Cron：`20 9 * * *`
- 发布哈希：`0975971730b6dbd1a738d6744f8a97ed3987195c12b2430bd571e5d4c517289d`
- 许可证：`MIT`

## 脚本功能

- HDSky（hdsky.me）每日签到，提交 showup 接口完成到场签到
- 通过 image_code_ajax 获取验证码哈希并下载验证码图片，使用内嵌模板与 OpenCV 识别后提交
- 识别业务成功（success=true）与今日已签到（message=date_unmatch）
- 首页核验登录态；页面返回公开用户名或 UID 时直接展示以便核对账号
- 多账号按行处理；规范变量 HDSKY_COOKIE，兼容 HDSKY_COOKIES 与上游 JSON cookies 写法
- 完全断网预演 HDSKY_DRY_RUN、HTTPS 超时、验证码重试、脱敏时间轴日志、TASK_SUMMARY 与青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `HDSKY_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录 https://hdsky.me 后，打开开发者工具网络面板，刷新任意站内页面，复制发往 hdsky.me 的请求 Cookie 完整值（通常含 c_secure_uid、c_secure_pass、c_secure_login 等）。每个非空行填写一个账号。也可填写一行上游风格的 JSON 对象（含 cookies 字段或直接为 c_secure_* 映射）。不要把真实 Cookie 写入公开仓库、日志或通知。
- 填写格式：每行一个 Cookie 字符串（内部分号分隔键值对）或一行 JSON；账号之间只用换行分隔，不使用 & 或 @

### 可选参数

### `HDSKY_COOKIES`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当 HDSKY_COOKIE 为空时生效，格式与规范变量相同。
- 填写格式：每行一个 Cookie 或 JSON；与 HDSKY_COOKIE 二选一

### `HDSKY_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线检查时设置；只校验配置并模拟签到阶段，不访问网络、不改动签到状态、不真实发送通知。
- 填写格式：1、true、yes、on 开启完全断网预演；默认关闭

### `HDSKY_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选：单次 HTTPS 请求超时秒数。
- 填写格式：5 到 60 的数字；默认 20

### `HDSKY_CAPTCHA_RETRIES`

- 必填：否
- 敏感：否
- 获取或设置：可选：验证码识别或签到提交失败时的重试次数（沿用上游最多三次思路）。
- 填写格式：1 到 5 的整数；默认 3

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认名单，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、相对路径、文件名或通配符；* 表示全部，空值表示全部关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录；失败不改变业务退出码。
- 填写格式：目录路径；还会尝试 /ql/data/scripts 与 /ql/scripts

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每行一个已登录 Cookie（或一行 JSON）；账号独立处理，任一账号失败时整体以非零退出码结束

## 验证与兼容性

SHA-256 `0975971730b6dbd1a738d6744f8a97ed3987195c12b2430bd571e5d4c517289d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/71c961d59b5546a3`。

## 副作用与风险

- 向 HDSky showup.php 提交每日签到，改变当日签到状态并可能获得站点魔力值或其他奖励
- 通知已启用且适配器可用时向青龙通知通道发送脱敏任务统计

## 许可证与来源

上游 `xxlgenius/hdsky-auto-sign-in` / `mian.py` / `643376edc2e6914ebc1f575edf4c5d0f8b2c9913`。
