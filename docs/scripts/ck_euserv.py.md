# EUserv 自动续期

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/ck_euserv.py`
- 青龙命令：`python3 scripts/ck_euserv.py`
- 建议 Cron：`56 10 */7 * *`
- 发布哈希：`4364d5d8150e1d64cde62049891db9ea193453be7986250247d8a0c11d300f9e`
- 许可证：`MIT`

## 脚本功能

- 登录 EUserv 并在需要时调用 TrueCaptcha 识别验证码
- 读取 EUserv 服务器列表并判断每台服务器是否进入续期窗口
- 通过 Mailparser 获取六位续期 PIN，申请安全令牌并提交续期
- 续期提交后重新读取服务器状态，只有确认不再显示可续期才判定成功
- 支持多个账号逐行配置、独立处理和汇总失败退出
- 支持完全断网预演、时间轴日志、脱敏通知和单行结构化汇总

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `EUSERV_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录 EUserv 获取账号密码；在 TrueCaptcha 控制台创建 userid 与 apikey；将 EUserv 续期 PIN 邮件自动转发到 Mailparser，并从解析结果下载地址取得末尾 ID。每个账号的全部字段写成一行 JSON。
- 填写格式：每个非空行一个 JSON 对象，必含 username、password、mailparser_dl_url_id、userid、apikey；账号之间只能换行分隔。

### 可选参数

### `EUSERV`

- 必填：否
- 敏感：是
- 获取或设置：旧版兼容变量；凭据获取方法与 EUSERV_ACCOUNTS 相同。仅在未设置 EUSERV_ACCOUNTS 时读取。
- 填写格式：支持逐行 JSON、JSON 数组，或含 EUSERV 数组的 JSON 对象。建议迁移到 EUSERV_ACCOUNTS。

### `EUSERV_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：自行设置为 1，可检查配置与日志而不发起任何网络请求或续期操作。
- 填写格式：1、true、yes 或 on 表示启用。

### `EUSERV_HTTP_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络状况自行设置单次 HTTP 请求超时；不设置时为 20 秒。
- 填写格式：3 到 120 之间的秒数。

### `EUSERV_PIN_WAIT_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按邮件转发与 Mailparser 解析速度自行设置；不设置时为 15 秒。
- 填写格式：0 到 300 之间的秒数。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要只通知指定脚本时自行设置选择器；空值表示全部禁用。
- 填写格式：可用逗号、分号、空白或换行分隔 catalogId、文件名或通配模式；* 表示全部脚本。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知脚本不在标准目录时，填写包含 notify.py 或 sendNotify.js 的目录。
- 填写格式：本机绝对目录路径。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行只放一个账号 JSON 对象；同一账号的 EUserv、Mailparser 与 TrueCaptcha 凭据必须位于同一对象中。各账号独立执行，任一账号配置或业务失败时进程返回非零状态。

## 验证与兼容性

SHA-256 `4364d5d8150e1d64cde62049891db9ea193453be7986250247d8a0c11d300f9e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/9b86f9dc679c7816`。

## 副作用与风险

- 登录时可能消耗 TrueCaptcha 识别次数并查询其用量
- 打开续期安全校验窗口会触发 EUserv 向账号邮箱发送续期 PIN
- 对进入续期窗口的服务器提交合同续期
- 非预演模式下按通知开关发送脱敏任务结果

## 许可证与来源

上游 `OreosLab/checkinpanel` / `ck_euserv.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。
