# AutoClaw 国内版每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/autoclaw_cn_daily.py`
- 青龙命令：`python3 scripts/autoclaw_cn_daily.py`
- 建议 Cron：`15 8 * * *`
- 发布哈希：`497df1c163561ea9fd933bdaca5cf661cae8a8f39536cfd7bff7413968a9c3e8`
- 许可证：`MIT`

## 脚本功能

- 每日签到并根据 HTTP 状态、业务码及奖励或明确成功标志核验；明确已签到单独统计，未知响应不冒充成功。
- 国内版默认运行；--region cn/intl/both 或 AUTOCLAW_REGION 选择地区，凭据仅发送至对应地区官方域名。
- 每行一个账号，逐账号独立执行；--only N 选择所选地区中的账号，both 时国内在前；任一账号或配置失败整体非零退出。
- 登录态过期自动续期并重试签到；保留 refresh 主接口及签名错误 400002 时的 agent-refresh 备用接口，支持 --refresh-only。
- 签到缺少成功标志时只读查询任务清单诊断，任务清单不代替奖励领取成功证据。
- 可选私有凭据缓存读取与续期结果原子保存；默认仅在本次内存更新，断网预演不读写缓存。
- 北京当天活动福利积分核查，匹配活跃与新用户奖励元数据，报告最近 50 笔收入中的命中逐笔积分和合计；默认关闭，read 模式只读。
- --promotion claim 显式开启登录活跃奖励触发，先查流水，未入账才调用 user-info，等待后复核；仅接口受理不视为到账。
- 保留青龙通知组件及青龙 API、PushPlus、Bark、企业微信、钉钉备用链；支持全局开关、任务名单及 --no-notify；通知失败保留业务退出码。
- 成功、部分失败、失败、配置错误均生成脱敏通知摘要，断网预演只模拟通知；时间轴、逐账号阶段和统计完整，恰好一条 TASK_SUMMARY JSON。
- 官方返回非敏感昵称、用户名、显示名称或公开 UID 时原样显示；不输出手机号、凭据、设备标识、自由响应文本或原始异常。
- 标准库独立实现 HTTPS、证书验证、超时、响应大小限制及禁止重定向；状态变更不自动网络重试；断网预演不调用任何外部提供方。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `AUTOCLAW_CN_TOKENS`

- 必填：是
- 敏感：是
- 获取或设置：在 AutoClaw 国内版官方桌面端登录自己的账号，从自己的登录响应安全提取 access_token、refresh_token 和同次登录的 device_id；只有 access_token 也可签到，失效后须重新登录。不要向他人发送响应或将凭据提交仓库。默认国内模式必填；显式仅国际模式时不读取。
- 填写格式：每个非空行一个账号；推荐单行 JSON 对象，文本字段 access 必填，refresh、device_id 可选。兼容 token、token|refresh_token、token|refresh_token|device_id、备注|token|refresh_token|device_id，以及旧备注|JWT、备注|JWT|refresh_token；逐次只分割首个 |，末字段保留余下文本。有歧义或含特殊字符时用 JSON；可带 Bearer 前缀；禁止用 &、@ 分隔账号。

### 可选参数

### `AUTOCLAW_INTL_TOKENS`

- 必填：否
- 敏感：是
- 获取或设置：仅 --region intl/both 或 AUTOCLAW_REGION=intl/both 时必填。在国际版官方桌面端登录，从自己的登录响应提取凭据；若仅能在本机配置获取，可在自己的电脑查看 ~/.openclaw-autoclaw/openclaw.json 中 models.providers 下 models[].headers 的 X-Authorization，去掉 Bearer 前缀。该来源通常没有 refresh_token，失效须重新登录。定时脚本不读取此文件。
- 填写格式：每个非空行一个账号；推荐单行 JSON 对象，文本字段 access 必填，refresh、device_id 可选。兼容 token、token|refresh_token、token|refresh_token|device_id、备注|token|refresh_token|device_id，以及旧备注|JWT、备注|JWT|refresh_token；逐次只分割首个 |，末字段保留余下文本。有歧义或含特殊字符时用 JSON；可带 Bearer 前缀；禁止用 &、@ 分隔账号。

### `AUTOCLAW_REGION`

- 必填：否
- 敏感：否
- 获取或设置：按自己的账号地区选择；命令行 --region 优先。
- 填写格式：默认 cn 为国内版，intl 为国际版，both 为国内后国际；各地区凭据及缓存隔离。

### `AUTOCLAW_PROMOTION`

- 必填：否
- 敏感：否
- 获取或设置：按活动风险选择；命令行 --promotion 优先。
- 填写格式：默认 off 关闭，保持维护候选默认签到行为；read 只读核查最近 50 笔收入中的北京当天活动积分；claim 显式允许未入账时调用 user-info 触发活跃奖励并复核。--refresh-only 不执行活动阶段。

### `AUTOCLAW_CN_STORE_FILE`

- 必填：否
- 敏感：是
- 获取或设置：需要跨运行保存续期结果时，用户须指定公开订阅和仓库以外的私有绝对文件路径，并准备受保护父目录；默认不读写凭据文件。
- 填写格式：非符号链接的绝对路径；已有文件须为 0600 或更严格权限；0600 原子写入，仅国内账号使用。

### `AUTOCLAW_INTL_STORE_FILE`

- 必填：否
- 敏感：是
- 获取或设置：国际账号需要持久化时显式指定与国内缓存不同的私有绝对文件路径；默认不读写。
- 填写格式：同国内缓存约束，仅国际账号使用，不得指向国内缓存文件。

### `AUTOCLAW_CN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：本地断网预演时设置为 1；无需真实凭据，仍校验账号格式。
- 填写格式：1、true、yes、on 启用整项任务断网预演；默认关闭。不联网、不读写缓存、不执行真实通知组件。

### `AUTOCLAW_INTL_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：保留国际版兼容入口，设置为 1 同样启用全任务断网预演。
- 填写格式：与 AUTOCLAW_CN_DRY_RUN 相同，任一开关启用即全任务断网。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要限定自动通知任务时配置；设置后替换默认名单，仅在 QINGLONG_NOTIFY 自动模式生效。
- 填写格式：逗号、分号或空白分隔目录编号、脚本相对路径、文件名或通配符；本任务编号为 3813c988ddc0c592，规范文件名为 autoclaw_cn_daily.py；* 全选，空值关闭全部自动通知。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：需要指定青龙通知组件时填其目录；否则尝试 import notify.send、/ql/data/scripts、/ql/scripts。通知不可用不改变业务退出码。
- 填写格式：含 notify.py 或 sendNotify.js 的目录；组件是可选通知扩展，业务 HTTP 由本脚本实现。

### `PUSHPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：在自己的 PushPlus 账号获取推送令牌，用作青龙通知失败后的备用通道。
- 填写格式：单个推送令牌，不用于 AutoClaw 登录。

### `BARK_URL`

- 必填：否
- 敏感：是
- 获取或设置：从自己管理的 Bark 服务获取推送地址，用作备用通道。
- 填写格式：包含推送密钥的完整 HTTPS 地址。

### `WECOM_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：从自己管理的企业微信群机器人配置获取，用作备用通道。
- 填写格式：完整 HTTPS 机器人地址或机器人密钥。

### `DINGTALK_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：从自己管理的钉钉群机器人配置获取，用作备用通道。
- 填写格式：完整 HTTPS 机器人地址。

### `DINGTALK_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：钉钉机器人启用加签时从该机器人安全设置获取，须与 DINGTALK_WEBHOOK 配套。
- 填写格式：机器人加签密钥；未启用加签时留空。

### `QL_URL`

- 必填：否
- 敏感：否
- 获取或设置：仅需要旧版青龙 API 通知备用通道时填写自己的青龙服务地址。
- 填写格式：HTTPS 青龙服务根地址，与 QL_TOKEN 配套。

### `QL_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从自己授权的青龙服务获取通知 API 令牌，仅用作显式配置的备用通道。
- 填写格式：单个 API 令牌，与 QL_URL 配套。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；同账号登录态、续期令牌、设备标识合并在同一行。兼容旧竖线格式，逐次只分割首个字段分隔符，末字段保留余下文本；复杂凭据用单行 JSON。不得用 &、@ 分隔账号。国内、国际独立凭据；所选地区均须配置。

## 验证与兼容性

SHA-256 `497df1c163561ea9fd933bdaca5cf661cae8a8f39536cfd7bff7413968a9c3e8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3813c988ddc0c592`。

## 副作用与风险

- 默认提交每日签到并可能领取积分；--refresh-only 不签到。
- 登录态过期或 --refresh-only 时续期，可能轮换服务端会话。
- 仅显式 --promotion claim 或 AUTOCLAW_PROMOTION=claim 时触发登录活跃，可能领取活动奖励。
- 仅显式配置私有缓存路径时保存续期结果，写入本地凭据文件；断网预演不读写。
- 通知开启且非断网预演时，通过用户配置的通知通道发送脱敏任务摘要。

## 许可证与来源

上游 `L0NE-6/AutoClaw-Daily` / `autoclaw_cn_daily.py` / `745a15b42d58bcaf9bb50920f5405e04b4f4964b`。
