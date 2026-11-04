# 电子科大晚安成电打卡

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/faq_daily_checkin.py`
- 青龙命令：`python3 scripts/faq_daily_checkin.py`
- 建议 Cron：`25 21 * * *`
- 发布哈希：`2cd7b92abffd77ca3d07535f6a3397d6bba2fa29907dff7064de146871e6778e`
- 许可证：`MIT`

## 脚本功能

- 使用学号、密码与浏览器指纹登录电子科技大学统一身份认证并获取 jzsz SESSION
- 可选直接复用 SESSION 跳过登录
- 向晚安成电接口提交带坐标与逆地理地址的每日打卡
- 支持多账号分行配置与断网预演
- 输出脱敏时间轴日志、TASK_SUMMARY 并发送青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `FAQ_CHECKIN_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录模式：使用电子科技大学统一身份认证学号与密码；在浏览器打开 https://idas.uestc.edu.cn 并登录后，从 Cookie 复制 MULTIFACTOR_BROWSER_FINGERPRINT；经纬度与逆地理地址填写本人真实打卡位置。会话模式：从 jzsz.uestc.edu.cn 已登录请求 Cookie 复制 SESSION，可跳过账密登录。每行一个账号，不要把凭据发给他人。
- 填写格式：每个非空行一个账号。推荐 JSON：登录模式需 student_id、password、browser_fingerprint、latitude、longitude、address；会话模式需 session、latitude、longitude、address。也支持「学号|密码|指纹|纬度|经度|地址」（按前五个竖线拆分）或「session|SESSION|纬度|经度|地址」（按前四个竖线拆分）。不使用 & 或 @ 分隔账号。

### 可选参数

### `FAQ_STUDENT_ID`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名。未设置 FAQ_CHECKIN_ACCOUNTS 时，与 FAQ_PASSWORD、FAQ_BROWSER_FINGERPRINT、FAQ_LATITUDE、FAQ_LONGITUDE、FAQ_ADDRESS 组合使用。
- 填写格式：单个学号字符串。

### `FAQ_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名；与 FAQ_STUDENT_ID 等配套使用。
- 填写格式：统一身份认证密码明文，仅保存在青龙环境变量中。

### `FAQ_BROWSER_FINGERPRINT`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名。从 idas.uestc.edu.cn Cookie 中的 MULTIFACTOR_BROWSER_FINGERPRINT 复制。
- 填写格式：单个指纹字符串。

### `FAQ_SESSION`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号会话别名。未设置 FAQ_CHECKIN_ACCOUNTS 时，可与坐标、地址组合跳过登录。
- 填写格式：jzsz.uestc.edu.cn 的 SESSION Cookie 值。

### `FAQ_LATITUDE`

- 必填：否
- 敏感：否
- 获取或设置：兼容单账号别名；填写本人打卡纬度。
- 填写格式：十进制度数，例如 30.123456。

### `FAQ_LONGITUDE`

- 必填：否
- 敏感：否
- 获取或设置：兼容单账号别名；填写本人打卡经度。
- 填写格式：十进制度数，例如 104.123456。

### `FAQ_ADDRESS`

- 必填：否
- 敏感：否
- 获取或设置：兼容单账号别名；填写与坐标对应的逆地理中文地址，不再使用上游硬编码地址。
- 填写格式：非空中文地址文本。

### `FAQ_CHECKIN_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：网络较慢时可适当增大。
- 填写格式：整数秒，默认 15，范围 5..120。

### `FAQ_CHECKIN_MMWEBID`

- 必填：否
- 敏感：否
- 获取或设置：可选。若已知微信 MMWEBID 可填写；未设置则随机生成。
- 填写格式：正整数。

### `FAQ_CHECKIN_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：一般无需修改；仅当官方业务域名变更且确认安全时调整。
- 填写格式：HTTPS 根地址，默认 https://jzsz.uestc.edu.cn。

### `FAQ_CHECKIN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：验证配置时设为 1，不发起任何网络请求。
- 填写格式：1/true/yes/on 开启断网预演；0/false/no/off 真实执行。默认 0。

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

每个非空行一个账号；同一账号的学号、密码、浏览器指纹、坐标与地址写在同一行。推荐 JSON；管道格式按固定字段数拆分，地址保留后续全部文本。不使用 & 或 @ 分隔账号。

## 验证与兼容性

SHA-256 `2cd7b92abffd77ca3d07535f6a3397d6bba2fa29907dff7064de146871e6778e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d8ce25fb54ffde83`。

## 副作用与风险

- CAS 登录建立或刷新业务 SESSION
- 提交学生每日打卡记录（晚安成电）

## 许可证与来源

上游 `kznLeaf/faq-daily-checkin` / `src/faq_daily_checkin/checkin.py` / `eab5794e2abbbbd17fe11e2cc8388939824e2038`。
