# CodeArts 每日福利领取

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/codearts_daily.py`
- 青龙命令：`python3 scripts/codearts_daily.py`
- 建议 Cron：`16 8 * * *`
- 发布哈希：`214d4f561c6648c369d5deb9b598585ea8371b42d8015a0ca73b504bc8e4c7a8`
- 许可证：`MIT`

## 脚本功能

- 查询每日登录积分及新人一次性注册礼；领取、确认并回读官方活动状态，只有 CONFIRMED/CONSUMED 且不可领取才确认到账。
- 按当前来源支持 DESKTOP 渠道、中文请求头、追踪标识及包含 Host 的 SDK-HMAC-SHA256 签名；解析 code=0/200 与 data/result 数据。
- 通过真正的 userBenefitId 确认到账；支持字段别名和已领取记录恢复；缺少确认 ID 时拒绝重放领取或猜测 ID。
- 保留北京时间每日 08:15 定时及 --preview、--only N、--force、--no-notify；预览只查询活动，不续期、不读写台账。
- 每行一个账号，支持单行 JSON、AK|SK|STS、既有字段别名、账号独立失败隔离及整体非零失败码。
- 凭据到期前十五分钟可自动续期；保留 refresh_token、PKCE、DPoP 续期链及凭据缓存；cryptography 仅续期时使用，可从公共 PyPI 安装，不自动安装。
- 领取前保存幂等键；每天最多六轮写尝试且间隔十分钟，--force 可显式绕过；兼容版本二台账迁移到版本三，保留幂等记录与新人结清标记。
- 官方返回昵称、用户名、显示名或公开 UID 时显示非凭据身份；抑制手机号、凭据、原始响应和任意异常详情。
- 完全断网预演在内存模拟同一业务执行链，覆盖签名、领取、确认、回读，不代表真实账号业务成功。
- 各结果均生成脱敏通知摘要，支持全局开关、选择名单、青龙 Python/JavaScript 通知模块及原有四种备用通知渠道；通知失败不改变业务退出码。
- 时间轴日志包含编号阶段、请求结果、耗时、账号与任务统计，并保留每轮一条 TASK_SUMMARY JSON。
- 独立实现 HTTPS 请求与安全证书验证、超时、大小限制、禁重定向和只重试只读请求；学生认证及邀请活动不自动领取。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `CODEARTS_CREDENTIALS`

- 必填：是
- 敏感：是
- 获取或设置：在本人设备使用官方 CodeArts 客户端登录；从本人登录态或发往 sts.cn-north-4.myhuaweicloud.com/v1/oauth2/tokens 的本人 HTTPS 响应取得同一账号的 access_key_id、secret_access_key、security_token。不要使用其他业务的永久 AK/SK。将凭据转成单行 JSON 填入青龙环境变量，每行一个账号。续期可从同次登录的本人 OAuth 上下文补充 refresh_token、PKCE code_verifier 和 P-256 DPoP 私钥 JWK；无需私有仓库、辅助程序或自动下载安装。
- 填写格式：每个非空行一个账号；首选单行 JSON，必含 access_key_id、secret_access_key、security_token。兼容 accessKeyId/secretAccessKey/securityToken、ak/sk/sts 别名；可含 expiration/expires_at/expiresAt、domain_id/domainId、user_name/userName、note。续期使用 refresh_token/refreshToken、oauth_context.pkce_pair.code_verifier（兼容顶层 code_verifier）、oauth_context.dpop_key_pair.private_key_jwk（含 kty=EC、crv=P-256、x、y、d）。简写 AK|SK|STS 仅在前两个 | 处分隔，后续 STS 文本完整保留；简写不支持续期，不使用 & 或 @ 分隔账号；以 # 开头的行忽略。

### 可选参数

### `CODEARTS_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：青龙环境变量中自行设置；离线测试设为 1。
- 填写格式：1/true/yes/on 开启，默认关闭；仅内存模拟，不联网、不读写状态、不调用通知模块。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中自行设置通知选择名单。
- 填写格式：设置后替换默认名单，逗号、分号或空白分隔；支持目录编号 b896028c3fdcd52d、脚本相对路径 checkin/codearts_daily.py、文件名 codearts_daily.py/candidate.py、文件名通配符和 *；空值关闭全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选填写本机青龙现有通知模块目录；未设置时先尝试 import notify.send，再检查 /ql/data/scripts 与 /ql/scripts。
- 填写格式：目录中包含 notify.py 或 sendNotify.js；只用于青龙通知发现，业务请求不依赖该目录；不自动安装模块。

### `PUSHPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：可选在 PushPlus 个人中心取得自己的推送令牌；青龙通知不可用时作为备用渠道。
- 填写格式：单个推送令牌，不是 CodeArts 凭据。

### `BARK_URL`

- 必填：否
- 敏感：是
- 获取或设置：可选从本人 Bark 客户端复制推送地址；青龙通知不可用时作为备用渠道。
- 填写格式：完整 HTTPS 推送地址，可包含私有推送密钥；禁止 HTTP。

### `WECOM_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：可选在本人企业微信群机器人配置页取得 Webhook；青龙通知不可用时作为备用渠道。
- 填写格式：完整 HTTPS Webhook 或机器人 key；禁止 HTTP。

### `DINGTALK_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：可选在本人钉钉群机器人配置页取得 Webhook；青龙通知不可用时作为备用渠道。
- 填写格式：完整 HTTPS Webhook；可配套 DINGTALK_SECRET。

### `DINGTALK_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：可选在同一个钉钉群机器人的安全设置中取得加签密钥。
- 填写格式：仅用于钉钉通知加签，与对应 Webhook 配套；不与账号凭据混合。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，采用单行 JSON 或 AK|SK|STS；同一账号的登录与续期材料放入同一个 CODEARTS_CREDENTIALS 行。不按 &、@ 或其他符号分隔账号；各账号独立执行，任一执行账号失败则整体非零退出。--only N 按非空且非注释行的账号序号选择。

## 验证与兼容性

SHA-256 `214d4f561c6648c369d5deb9b598585ea8371b42d8015a0ca73b504bc8e4c7a8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b896028c3fdcd52d`。

## 副作用与风险

- 正常模式领取每日登录积分和新人一次性注册礼，并向官方确认福利到账。
- 配置完整续期材料且临近到期时刷新临时登录凭据，更新脚本目录中的 codearts_credentials.json。
- 正常执行领取流程时以原子写入方式更新脚本目录中的 codearts_welfare_ledger.json，记录幂等键、尝试次数和新人结清标记。
- 通知启用时发送脱敏汇总；青龙通知不可用时尝试已配置的 PushPlus、Bark、企业微信和钉钉备用渠道。

## 许可证与来源

上游 `L0NE-6/CodeArts-Daily` / `codearts_daily.py` / `c337a9340877cdf7afef0a679f3d020d28183140`。
