# SakuraFRP每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/auto_signin_http.py`
- 青龙命令：`python3 scripts/auto_signin_http.py`
- 建议 Cron：`7 9 * * *`
- 发布哈希：`c734785decddb554388046ddea58de761d9468e14b2a1e67e80db373f1b7ca23`
- 许可证：`MIT`

## 脚本功能

- 使用用户名或邮箱与密码经 OpenID 登录 SakuraFRP（natfrp.com）
- 登录与签到阶段处理 GeeTest v3 验证码，并通过 OpenAI 兼容多模态接口识别点选或九宫格
- 提交每日签到并区分签到成功与今日已签到
- 查询并展示官方返回的非凭据公开身份（name 或 id），未返回时使用账号序号
- 支持每行一个账号的多账号独立处理，任一账号失败时非零退出
- 支持完全断网预演、请求超时、时间轴日志、脱敏通知与单行 TASK_SUMMARY

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `SAKURAFRP_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：使用 SakuraFRP（natfrp.com）注册或登录时的用户名/邮箱与明文密码。仅写入青龙环境变量，不要分享或提交到公开仓库。
- 填写格式：每个非空行一个账号：用户名或邮箱|密码；仅在第一个竖线处分割，密码中后续竖线保留。空行和以 # 开头的注释行忽略。

### `SAKURAFRP_CAPTCHA_API_KEY`

- 必填：是
- 敏感：是
- 获取或设置：在 OpenAI 兼容的多模态服务商控制台创建 API Key，用于识别登录/签到 GeeTest 点选或九宫格验证码。正式执行必填；断网预演也需提供占位值以通过配置校验。
- 填写格式：非空字符串；兼容别名 CAPTCHA_API_KEY

### 可选参数

### `SAKURAFRP_CAPTCHA_API_BASE`

- 必填：否
- 敏感：否
- 获取或设置：可选；填写 OpenAI 兼容 Chat Completions 接口的根地址。留空使用官方 OpenAI。
- 填写格式：https:// 开头的 URL，默认 https://api.openai.com/v1；兼容别名 CAPTCHA_API_BASE

### `SAKURAFRP_CAPTCHA_MODEL`

- 必填：否
- 敏感：否
- 获取或设置：可选；指定支持图片输入的多模态模型名称。
- 填写格式：模型名字符串，默认 gpt-4o；兼容别名 CAPTCHA_MODEL

### `SAKURAFRP_MAX_RETRIES`

- 必填：否
- 敏感：否
- 获取或设置：按验证码识别成功率调整最大重试次数；留空使用 10。
- 填写格式：1 至 20 的整数；兼容别名 MAX_RETRIES

### `SAKURAFRP_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置单次 HTTPS 请求超时；留空使用 30 秒。
- 填写格式：5 至 120 之间的秒数

### `username`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容输入；当未设置 SAKURAFRP_ACCOUNTS 时，与 password 同时非空可视为单个账号。
- 填写格式：SakuraFRP 用户名或邮箱；需与 password 成对使用

### `password`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容输入；当未设置 SAKURAFRP_ACCOUNTS 时，与 username 同时非空可视为单个账号。
- 填写格式：SakuraFRP 明文密码；需与 username 成对使用

### `CAPTCHA_API_KEY`

- 必填：否
- 敏感：是
- 获取或设置：SAKURAFRP_CAPTCHA_API_KEY 的上游兼容别名；规范变量优先。
- 填写格式：非空 API Key 字符串

### `SAKURAFRP_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要验证配置与执行路径但禁止联网时启用；预演不访问业务接口，也不声明真实签到成功。
- 填写格式：布尔值，默认 0；1、true、yes、on 开启完全断网预演

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认名单，只为匹配的脚本开启通知。
- 填写格式：用逗号、分号、空白或换行分隔 catalog ID、相对路径、文件名或通配符；* 表示全部，空值表示全部关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选填写已有青龙 notify.py 或 sendNotify.js 所在目录；未填写时尝试导入 notify 和青龙标准脚本目录。
- 填写格式：已有通知模块所在目录路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

SAKURAFRP_ACCOUNTS 中每个非空行代表一个账号，格式为用户名或邮箱|密码；仅在第一个竖线处分割。脚本逐账号独立处理，任一账号失败时进程非零退出。

## 验证与兼容性

SHA-256 `c734785decddb554388046ddea58de761d9468e14b2a1e67e80db373f1b7ca23`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/997de6e58b1ddd7a`。

## 副作用与风险

- 登录后在 SakuraFRP 账号上写入每日签到记录（通常发放流量等奖励）
- 正式执行且通知开启时向青龙通知组件发送脱敏任务总结

## 许可证与来源

上游 `claaudy/sakurafrp-auto-sign` / `auto_signin_http.py` / `b27240b156718ee4b958e9bc72133349c4831953`。
