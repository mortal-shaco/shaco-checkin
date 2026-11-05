# 极核ZEEHO每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/zeeho_signin.py`
- 青龙命令：`python3 scripts/zeeho_signin.py`
- 建议 Cron：`32 8 * * *`
- 发布哈希：`ad37e67220547049ba289f373bad32fa741f4d713d77678f65497be57cb9c929`
- 许可证：`MIT`

## 脚本功能

- 使用极核 App Bearer Token 查询账号资料并展示昵称与公开 userId
- 查询 H5 签到状态、连续签到天数与积分，未签则 POST 签到并以回查 lastTime 判定成功
- 可选查询车辆主页电量、续航、里程与锁车状态
- 支持多账号分行配置、仅查询模式、强制重签与断网预演
- 输出脱敏时间轴日志、TASK_SUMMARY 并发送青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ZEEHO_TOKEN`

- 必填：是
- 敏感：是
- 获取或设置：从已登录的极核（ZEEHO）App 抓包：任意业务请求头 Authorization: Bearer <UUID>，或签到页 URL 中的 token 参数。只需 UUID 一段，不要抄 Cfmoto-X-Sign。官方 App 为单会话，别处使用同一 Token 可能挤下线手机端。过期后需重新抓包。
- 填写格式：每个非空行一个账号 Token（UUID）。可带 Bearer 前缀或完整 URL，脚本会规范化。不使用 & 或 @ 分隔账号。

### 可选参数

### `ZEEHO_TOKENS`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名。未设置 ZEEHO_TOKEN 时读取本变量，格式相同。
- 填写格式：与 ZEEHO_TOKEN 相同：每行一个 UUID Token。

### `ZEEHO_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：验证配置时设为 1，不发起任何网络请求。
- 填写格式：1/true/yes/on 开启断网预演；0/false/no/off 真实执行。默认 0。

### `ZEEHO_STATUS_ONLY`

- 必填：否
- 敏感：否
- 获取或设置：仅查询签到状态、积分与车辆概要时设为 1，不发起签到 POST。
- 填写格式：1/true/yes/on 或 0/false/no/off。默认 0。

### `ZEEHO_FORCE`

- 必填：否
- 敏感：否
- 获取或设置：今日已签到时仍强制尝试 POST 签到时设为 1。
- 填写格式：1/true/yes/on 或 0/false/no/off。默认 0。

### `ZEEHO_FETCH_VEHICLE`

- 必填：否
- 敏感：否
- 获取或设置：默认开启车辆主页查询；设为 0 可跳过 tapi 车辆接口。
- 填写格式：1/true/yes/on 或 0/false/no/off。默认 1。

### `ZEEHO_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：网络较慢时可适当增大。
- 填写格式：整数秒，默认 30，范围 5..120。

### `ZEEHO_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：一般无需修改；仅当官方 H5 域名变更且确认安全时调整。
- 填写格式：HTTPS 根地址，默认 https://h5.zeehoev.com。

### `ZEEHO_APP_ID`

- 必填：否
- 敏感：否
- 获取或设置：原生 tapi 签名用公开客户端 appId；一般使用默认值。
- 填写格式：字符串，默认 Sw5F9uJi。

### `ZEEHO_APP_SECRET`

- 必填：否
- 敏感：否
- 获取或设置：原生 tapi 签名用公开客户端密钥；不是登录 Token。
- 填写格式：十六进制字符串。

### `ZEEHO_H5_APP_ID`

- 必填：否
- 敏感：否
- 获取或设置：H5 签到通道公开客户端 appId；一般使用默认值。
- 填写格式：字符串，默认 AiTXmBrm。

### `ZEEHO_H5_APP_SECRET`

- 必填：否
- 敏感：否
- 获取或设置：H5 签到通道公开客户端密钥；不是登录 Token。
- 填写格式：十六进制字符串。

### `ZEEHO_INSECURE_SSL`

- 必填：否
- 敏感：否
- 获取或设置：仅在证书校验失败且确认环境需要时开启；默认关闭（校验证书）。
- 填写格式：1/true/yes/on 跳过证书校验；默认 0。

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

每个非空行一个账号 Token；同一账号仅需一个 Bearer UUID。不使用 & 或 @ 分隔账号。任一账号失败则进程非零退出。

## 验证与兼容性

SHA-256 `ad37e67220547049ba289f373bad32fa741f4d713d77678f65497be57cb9c929`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d95dd43dd4755fbe`。

## 副作用与风险

- 向极核 H5 签到接口提交每日签到（未签或强制时）

## 许可证与来源

上游 `desfate/macOS_for_zeeho_auto_signin` / `scripts/zeeho_signin.py` / `e73bb229d0e549cc4fae9f1d101731faa3eec282`。
