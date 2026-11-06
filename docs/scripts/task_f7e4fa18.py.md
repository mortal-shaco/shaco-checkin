# 网易云音乐人签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_f7e4fa18.py`
- 青龙命令：`python3 scripts/task_f7e4fa18.py`
- 建议 Cron：`21 9 * * *`
- 发布哈希：`c0b1ecd892f93aa37f8413a5648c648b0a88e37565d0a13a847227678ed6a073`
- 许可证：`MIT`

## 脚本功能

- 手机号密码或 Cookie 登录网易云音乐人兼容接口
- 音乐人中心每日签到
- 拉取任务并领取可领云豆奖励
- 查询账户云豆余额并展示公开身份（若返回）
- 多账号逐行独立处理与失败汇总
- 完全断网预演、时间轴日志与单行 TASK_SUMMARY
- 青龙脱敏通知及全局通知开关

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `NETEASE_MUSICIAN_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：使用本人网易云音乐人账号。密码方式：国内 11 位手机号与登录密码；Cookie 方式：浏览器登录 music.163.com 后在开发者工具复制含 MUSIC_U（建议含 __csrf）的完整 Cookie。切勿写入公开仓库或日志。
- 填写格式：每个非空行一个账号：phone|password（仅按第一个 | 分割）或整行 Cookie；支持空行与 # 注释；不要用 & 或 @ 分隔账号

### 可选参数

### `NETEASE_MUSICIAN_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当 NETEASE_MUSICIAN_ACCOUNTS 为空时，按多行 Cookie 解析
- 填写格式：每个非空行一条含 MUSIC_U 的完整 Cookie

### `NETEASE_MUSICIAN_PHONE`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名；仅当 NETEASE_MUSICIAN_ACCOUNTS 与 NETEASE_MUSICIAN_COOKIE 均为空时与 NETEASE_MUSICIAN_PASSWORD 成对使用
- 填写格式：11 位国内手机号，不含 +86

### `NETEASE_MUSICIAN_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名；仅当规范变量为空时与 NETEASE_MUSICIAN_PHONE 成对使用
- 填写格式：对应手机号的登录密码明文，或在 NETEASE_MUSICIAN_PASSWORD_MD5=1 时填 32 位小写 MD5

### `NETEASE_MUSICIAN_PASSWORD_MD5`

- 必填：否
- 敏感：否
- 获取或设置：当账号行密码字段已是 MD5 密文时设为 1
- 填写格式：1/true/yes/on 表示密码已是 32 位小写 MD5；默认按明文本地 MD5 后登录

### `NETEASE_MUSICIAN_API_BASE`

- 必填：否
- 敏感：否
- 获取或设置：真实执行必填：配置本人信任、兼容 NeteaseCloudMusicApi 路径的 HTTPS 服务根地址。本脚本不安装或启动该服务；禁止使用来源不明的公共实例（含上游默认 vercel）。断网预演可不填。
- 填写格式：HTTPS 根地址，例如 https://your-api.example，末尾无斜杠，不得含凭据或查询串

### `NETEASE_MUSICIAN_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：自定义单次 HTTPS 请求超时秒数
- 填写格式：5 到 60 的数字秒，默认 20

### `NETEASE_MUSICIAN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要完全断网预演、只校验配置时手动设置为 1
- 填写格式：1/true/yes/on 启用预演；默认实际执行

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

NETEASE_MUSICIAN_ACCOUNTS 中每个非空行是一个独立账号；密码账号格式 phone|password（仅按第一个 | 分割），或整行 Cookie；逐账号登录、签到、领云豆与查余额，任一账号失败时进程整体非零退出

## 验证与兼容性

SHA-256 `c0b1ecd892f93aa37f8413a5648c648b0a88e37565d0a13a847227678ed6a073`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/f7e4fa182acc7d66`。

## 副作用与风险

- 实际执行时向配置的兼容 API 登录并建立会话（仅内存，不落盘）
- 实际执行时触发音乐人中心签到，可能改变当日签到状态
- 实际执行时领取可领云豆任务奖励，可能增加账户云豆
- 启用青龙通知时会向已配置渠道发送脱敏任务汇总

## 许可证与来源

上游 `ghaction/Musician-Auto-Check` / `main.py` / `23e1f798d7ebfcb75fd7178a685556c822ac9be3`。
