# CordCloud 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/action.py`
- 青龙命令：`python3 scripts/action.py`
- 建议 Cron：`38 8 * * *`
- 发布哈希：`05710cb947f9264e45260123901de328d941a113dfd2149cce3b311de96774d9`
- 许可证：`MIT`

## 脚本功能

- CordCloud 邮箱密码登录
- 可选两步验证 TOTP
- 多站点主机名自动回退
- 每日签到
- 今日已签到状态识别
- 查询今日已用、过去已用与剩余流量
- 多账号独立处理与脱敏汇总通知
- 断网预演配置验证

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `CORDCLOUD_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 CordCloud 官网注册或登录后，使用注册邮箱与登录密码。若开启两步验证，在安全设置中查看 TOTP 密钥（Base32），不要把凭据写入公开仓库或聊天。未设置本变量时，可改用兼容项 CORDCLOUD_EMAIL 与 CORDCLOUD_PASSWD（可选 CORDCLOUD_SECRET），并兼容上游 GitHub Secrets 名 CC_EMAIL/CC_PASSWD/CC_SECRET。
- 填写格式：每个非空行一个账号：邮箱|密码；启用两步验证时为 邮箱|密码||TOTP密钥。仅在首个竖线处分割邮箱与后续字段，密码中后续单个竖线保留；TOTP 以双竖线引入且密钥不得含竖线。不要用 & 或 @ 分隔账号

### 可选参数

### `CORDCLOUD_EMAIL`

- 必填：否
- 敏感：是
- 获取或设置：仅当未设置 CORDCLOUD_ACCOUNTS 时生效的单账号兼容输入；填写 CordCloud 登录邮箱。亦可使用上游别名 CC_EMAIL。
- 填写格式：单个邮箱地址，不要包含 |

### `CORDCLOUD_PASSWD`

- 必填：否
- 敏感：是
- 获取或设置：与 CORDCLOUD_EMAIL 成对使用的登录密码；亦可使用上游别名 CC_PASSWD。
- 填写格式：明文登录密码；可含 |

### `CORDCLOUD_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：可选两步验证 TOTP 密钥，仅在兼容单账号模式下与邮箱密码一起使用；亦可使用上游别名 CC_SECRET。
- 填写格式：Base32 密钥，可含空格（脚本会忽略空白）

### `CORDCLOUD_HOST`

- 必填：否
- 敏感：否
- 获取或设置：仅当官方站点域名变更时覆盖；默认依次尝试 cordcloud.us,cordcloud.one,cordcloud.biz,c-cloud.xyz
- 填写格式：逗号分隔的主机名，不含协议或路径，例如 cordcloud.us,cordcloud.one

### `CORDCLOUD_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：网络较慢时可适当增大单次请求超时
- 填写格式：5..60 整数或小数秒，默认 15

### `CORDCLOUD_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要完全断网预演时手动设置为 1
- 填写格式：1/true/yes/on 启用；0/false/no/off 关闭

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

CORDCLOUD_ACCOUNTS 中每个非空行是一个独立账号（邮箱|密码，或 邮箱|密码||TOTP密钥）；逐账号执行，任一账号失败时进程整体非零退出

## 验证与兼容性

SHA-256 `05710cb947f9264e45260123901de328d941a113dfd2149cce3b311de96774d9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/acd4b880b9d34d61`。

## 副作用与风险

- 成功请求会完成 CordCloud 当日签到并可能增加账户流量
- 启用青龙通知时会向已配置的通知渠道发送脱敏任务汇总

## 许可证与来源

上游 `yanglbme/cordcloud-action` / `app/action.py` / `16b0b61483ac99124b6ea1ced39b4b16d7139a8d`。
