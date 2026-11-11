# Qoder每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/qoder_airscript.js`
- 青龙命令：`node scripts/qoder_airscript.js`
- 建议 Cron：`17 8 * * *`
- 发布哈希：`2d373706b01dadaa4f16e919cc0ba76d38d16abadbae426f3be96087346abdfb`
- 许可证：`MIT`

## 脚本功能

- 规范 JSON 行多账号，兼容两套令牌字段命名、原账号开关及旧令牌环境变量，支持中国区、国际区及逐账号不同地区
- 优先使用访问令牌，缺少时刷新；活动 HTTP 401、403 或业务码 105、10019901001 时续期并仅重试一次，兼容设备与任务令牌刷新路径
- 保留带 forceRefresh=true 的活动列表查询，兼容顶层及 data 包装、device_token 和 campaignKey；中国区明确成功空列表时用来源四头协议无强制刷新补查一次
- 逐项领取全部可领 CLAIM_BENEFIT 活动，累计 Credits，显示有效期；明确幂等重放和活动有效窗口内已领取识别，不把未知响应或任意 409 当成功
- 中国区 Pro 活动及最多五项普通候选奖励面值只读核验；识别 Pro 后回读领取前后总剩余额度，区分领取确认与实际到账；额外非普通 Pro 活动必须明确启用
- 可选在北京时间 10:00 至 10:30 有界等待活动下发，保留原计划和默认单轮运行
- 保留仅刷新令牌、指定账号及关闭通知的环境变量和命令行方式
- 显式私有账号文件原子写回轮换令牌，未设置文件时只保存在内存，不自动写缓存或设备文件
- 保留 Server酱、PushPlus、企业微信逐账号通知，兼容全局 PushPlus、Bark、企业微信、钉钉通知，按名单策略发送青龙脱敏汇总；通知失败保留业务退出码
- 输出官方提供的非敏感身份，分阶段时间轴日志、逐账号及最终统计，保留原机器字段和全部处理完成标记，并且仅输出一条 TASK_SUMMARY
- 标准 Node.js 自行实现 HTTPS，校验证书、超时、响应大小限制、脱敏日志及完全断网预演，不依赖私有仓库、应用可执行文件或下载安装过程
- 新增 QODER_ACTION=status 和 --status，只读显示活动状态、奖励面值和有效窗口，成功仅表示查询完成；不领取、续期或写回令牌
- 兼容 QODER_CLAIM_TOKEN、--token、--from-file、官方地址 --base-url、--once、--dry-run 和脱敏 --json 结果；规范账号配置和原默认计划保留
- 支持中国区 PAT 换取短期任务令牌后领取全部活动；兼容两种兑换字段，仅字段错误时尝试备用字段，保留原领取及幂等成功标记
- PAT 账号无须设备头或本机客户端；保持规范 JSON 行账号及 QODER_PAT 兼容入口，默认不兑换、不领取，不隐式读取凭据文件
- PAT 活动支持秒、毫秒及日期文本有效窗口；成功收据需明确领取状态、明确幂等结果或正数奖励面值，未知结果失败退出
- 兼容旧 JSON 数组、accounts 包装、token 与 expires_at 别名，以及显式配置文件中的设备字段，保持规范 JSON 行和原文件优先级
- 显式设置 QODER_EMPTY_RETRY 或 QODER_EMPTY_WAIT 时，仅无普通活动才在本轮重查；--once 禁用等待，未设置时保留规范版单轮默认
- 可选临期刷新，解析秒、毫秒、ISO 过期时间及访问令牌到期字段；刷新失败仅沿用未过期令牌
- 兼容 silent、poll、silent-poll 调用，可选追加脱敏 JSON 行记录及企业微信、PushPlus、HTTPS Webhook 汇总通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `QODER_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人已登录的 Qoder 客户端授权请求中取得 Authorization 访问令牌及 Cosy-* 设备头，刷新令牌从本人登录凭据取得。仅处理本人账号，避免上传凭据。兼容原取号工具 JSON，但运行不依赖该工具。 PAT 也可在 https://qoder.cn/account/integrations 创建本人个人访问令牌，放在同一账号 JSON 的 personalToken 字段。
- 填写格式：每非空行一个 JSON 对象。设备令牌模式：accessToken/access_token 与 refreshToken/refresh_token 至少一项，device 的 clientType、machineOS、machineHostname、machineId、machineToken、machineCode、machineType、version 八项非空单行字符串必填。PAT 模式：personalToken（兼容 pat/personal_token），仅中国区且不需要 device。enabled=true 或 qiandao=是 才执行兑换、领取或刷新。region 为 cn/global；可选 name、uid、serverchan、pushplus、qywx。只读及仅刷新使用原设备令牌模式。 兼容旧 JSON 数组、accounts 包装及 token、expires_at 别名；device 字段可由环境变量及显式配置补齐，仍须八项完整。可选 expiresAt 为秒、毫秒或 ISO 日期。

### 可选参数

### `QODER_ACCOUNTS_FILE`

- 必填：否
- 敏感：是
- 获取或设置：自行建立私有 JSON 行账号文件并显式指定路径，格式同 QODER_ACCOUNTS。该方式或旧变量可替代规范账号变量。
- 填写格式：文件路径，优先于环境账号；刷新后原子写回并设置权限0600，预演不写回。--from-file 则只读取单个 JSON 对象且不写回。 兼容 JSON 数组及 accounts 包装，写回保留原容器结构。

### `QODER_TOKENS`

- 必填：否
- 敏感：是
- 获取或设置：兼容旧配置，从本人授权请求或登录凭据取得令牌。仅在未配置规范账号变量及账号文件时使用。
- 填写格式：中国区每行 access 或 access|refresh 或 备注|access|refresh，可追加 |uid。按首个分隔符保留后续文本，含 | 的凭据使用规范 JSON 行避免歧义。领取须 QODER_ENABLED=1 并配置设备头。

### `QODER_GLOBAL_TOKENS`

- 必填：否
- 敏感：是
- 获取或设置：兼容旧配置，从本人授权请求或登录凭据取得令牌。仅在未配置规范账号变量及账号文件时使用。
- 填写格式：国际区每行 access 或 access|refresh 或 备注|access|refresh，可追加 |uid。按首个分隔符保留后续文本，含 | 的凭据使用规范 JSON 行避免歧义。领取须 QODER_ENABLED=1 并配置设备头。

### `QODER_CLAIM_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容主来源，从本人授权请求 Authorization 中取得访问令牌。规范及旧账号变量均未配置时使用。--token 可显式提供单账号令牌。
- 填写格式：每非空行一个访问令牌，配合 QODER_COSY_* 设备头；领取须 QODER_ENABLED=1。

### `QODER_PAT`

- 必填：否
- 敏感：是
- 获取或设置：在 https://qoder.cn/account/integrations 创建本人 PAT；兼容主来源环境变量，推荐使用规范 QODER_ACCOUNTS 的 personalToken 字段。
- 填写格式：每非空行一个 PAT，仅其他账号入口均未配置时使用；仅中国区，须 QODER_ENABLED=1 才兑换并领取。不会隐式读取 qoder_pat.txt；私有文件请使用 QODER_ACCOUNTS_FILE 的 JSON 行。

### `QODER_ENABLED`

- 必填：否
- 敏感：否
- 获取或设置：自行选择旧变量及命令行单账号的领取或刷新授权。
- 填写格式：1/true/yes/on 启用，默认关闭；规范 JSON 行仍使用各自 enabled/qiandao。只读模式忽略领取开关。

### `QODER_COSY_CLIENT_TYPE`

- 必填：否
- 敏感：否
- 获取或设置：旧变量或命令行导入缺少 device 时，从本人授权请求的 Cosy-ClientType 头取得。
- 填写格式：非空单行字符串；仅 CLIENT_TYPE 默认10，其余必须提供，不生成设备身份。 优先账号 device，其次环境变量，再其次 QODER_CONFIG_FILE 的 device。

### `QODER_COSY_MACHINE_OS`

- 必填：否
- 敏感：是
- 获取或设置：旧变量或命令行导入缺少 device 时，从本人授权请求的 Cosy-MachineOS 头取得。
- 填写格式：非空单行字符串；仅 CLIENT_TYPE 默认10，其余必须提供，不生成设备身份。 优先账号 device，其次环境变量，再其次 QODER_CONFIG_FILE 的 device。

### `QODER_COSY_MACHINE_HOSTNAME`

- 必填：否
- 敏感：是
- 获取或设置：旧变量或命令行导入缺少 device 时，从本人授权请求的 Cosy-MachineHostname 头取得。
- 填写格式：非空单行字符串；仅 CLIENT_TYPE 默认10，其余必须提供，不生成设备身份。 优先账号 device，其次环境变量，再其次 QODER_CONFIG_FILE 的 device。

### `QODER_COSY_MACHINE_ID`

- 必填：否
- 敏感：是
- 获取或设置：旧变量或命令行导入缺少 device 时，从本人授权请求的 Cosy-MachineId 头取得。
- 填写格式：非空单行字符串；仅 CLIENT_TYPE 默认10，其余必须提供，不生成设备身份。 优先账号 device，其次环境变量，再其次 QODER_CONFIG_FILE 的 device。

### `QODER_COSY_MACHINE_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：旧变量或命令行导入缺少 device 时，从本人授权请求的 Cosy-MachineToken 头取得。
- 填写格式：非空单行字符串；仅 CLIENT_TYPE 默认10，其余必须提供，不生成设备身份。 优先账号 device，其次环境变量，再其次 QODER_CONFIG_FILE 的 device。

### `QODER_COSY_MACHINE_CODE`

- 必填：否
- 敏感：是
- 获取或设置：旧变量或命令行导入缺少 device 时，从本人授权请求的 Cosy-MachineCode 头取得。
- 填写格式：非空单行字符串；仅 CLIENT_TYPE 默认10，其余必须提供，不生成设备身份。 优先账号 device，其次环境变量，再其次 QODER_CONFIG_FILE 的 device。

### `QODER_COSY_MACHINE_TYPE`

- 必填：否
- 敏感：是
- 获取或设置：旧变量或命令行导入缺少 device 时，从本人授权请求的 Cosy-MachineType 头取得。
- 填写格式：非空单行字符串；仅 CLIENT_TYPE 默认10，其余必须提供，不生成设备身份。 优先账号 device，其次环境变量，再其次 QODER_CONFIG_FILE 的 device。

### `QODER_COSY_VERSION`

- 必填：否
- 敏感：否
- 获取或设置：旧变量或命令行导入缺少 device 时，从本人授权请求的 Cosy-Version 头取得。
- 填写格式：非空单行字符串；仅 CLIENT_TYPE 默认10，其余必须提供，不生成设备身份。 优先账号 device，其次环境变量，再其次 QODER_CONFIG_FILE 的 device。

### `QODER_MACHINE_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从本人授权请求的对应 Cosy-Machine 设备头取得，兼容旧参数名。
- 填写格式：非空单行字符串；优先使用对应 QODER_COSY_MACHINE_TOKEN。

### `QODER_MACHINE_CODE`

- 必填：否
- 敏感：是
- 获取或设置：从本人授权请求的对应 Cosy-Machine 设备头取得，兼容旧参数名。
- 填写格式：非空单行字符串；优先使用对应 QODER_COSY_MACHINE_CODE。

### `QODER_MACHINE_TYPE`

- 必填：否
- 敏感：是
- 获取或设置：从本人授权请求的对应 Cosy-Machine 设备头取得，兼容旧参数名。
- 填写格式：非空单行字符串；优先使用对应 QODER_COSY_MACHINE_TYPE。

### `QODER_REGION`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：cn 或 global，默认 cn；账号 region 可覆盖。--base-url 仅接受两个官方 HTTPS 根地址，不自动跨区转发凭据。

### `QODER_ACTION`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：checkin 默认领取，refresh 仅续期，status 只读活动状态、奖励及窗口。命令行 --refresh-only 或 --status 可覆盖；只读不续期、不领取、不写回。

### `QODER_ONLY`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：从1开始的账号序号，可用 --only 指定。

### `QODER_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：1/true/yes/on 完全断网预演，不写凭据、不运行通知模块；--dry-run 等效。

### `QODER_PRO_VERIFY`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：默认1，中国区只读核验 Pro 奖励与额度，可设0关闭；辅助检查不替代明确领取结果。

### `QODER_PRO_UPGRADE`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：默认0，明确设1后才额外领取列表中非 CLAIM_BENEFIT 的 Pro 活动。

### `QODER_WINDOW_RETRY`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：默认0，可设1在北京时间10:00至10:30等待活动；--once 禁止该等待。

### `QODER_WINDOW_RETRY_MAX`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：1至16的整数，默认16。

### `QODER_WINDOW_RETRY_GAP`

- 必填：否
- 敏感：否
- 获取或设置：由账号所有者自行配置。
- 填写格式：1至300秒整数，默认90。

### `PUSHPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从本人 PushPlus 通道取得。
- 填写格式：非空单行通道令牌。

### `BARK_URL`

- 必填：否
- 敏感：是
- 获取或设置：从本人 Bark 应用取得。
- 填写格式：完整 HTTPS 推送地址。

### `WECOM_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：从本人企业微信群机器人取得。
- 填写格式：HTTPS webhook 或机器人 key。

### `DINGTALK_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：从本人钉钉群机器人取得。
- 填写格式：完整 HTTPS webhook。

### `DINGTALK_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：从本人钉钉机器人安全设置取得。
- 填写格式：可选加签密钥。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：自行配置通知名单，设置后替换默认名单。
- 填写格式：逗号、分号、空白或换行分隔 catalogId、相对路径、文件名或通配符；*全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：使用青龙已配置的通知模块目录。
- 填写格式：含 sendNotify.js 的目录；也查找 /ql/data/scripts 和 /ql/scripts。缺失或失败保留业务退出码。

### `QODER_EMPTY_RETRY`

- 必填：否
- 敏感：否
- 获取或设置：可选，自行设置活动未下发时本轮查询次数。
- 填写格式：显式配置才开启；整数至少1，非法值使用3。未配置两个重查变量时保持原规范脚本单轮；--once 禁用等待重查。

### `QODER_EMPTY_WAIT`

- 必填：否
- 敏感：否
- 获取或设置：可选，自行设置空活动重查的等待秒数。
- 填写格式：显式配置才开启；整数秒至少0，非法值使用20。任一重查变量存在时次数默认3、间隔默认20秒；预演不等待。

### `QYWX_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从本人企业微信机器人设置取得 webhook 的 key，兼容配置 notify.qywxToken。
- 填写格式：机器人 key 或含 key= 的完整地址；受全局通知开关控制。

### `PLUSPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从本人 PushPlus 取得推送令牌，兼容配置 notify.plusplusToken。
- 填写格式：推送令牌；受全局通知开关控制。

### `QODER_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：指定本人信任的 HTTPS 通知接收端，兼容配置 notify.webhook。
- 填写格式：HTTPS 地址，仅发送中文标题和脱敏统计；受全局通知开关控制。 成功须 HTTP 200 且 success=true 或 code 为0或200；失败不改变业务退出码。

### `QODER_CONFIG_FILE`

- 必填：否
- 敏感：否
- 获取或设置：自行创建私有配置 JSON 并显式指定路径，无须运行提取器。
- 填写格式：不默认读取文件；支持 device、refreshMarginH、notify、baseUrls。device 字段低于账号及环境变量优先级。notify 支持 qywxToken、plusplusToken、webhook。

### `QODER_REFRESH_MARGIN_H`

- 必填：否
- 敏感：否
- 获取或设置：自行选择临期续期窗口。
- 填写格式：非负整数小时；优先于显式配置 refreshMarginH。未配置时保持优先使用访问令牌，鉴权失效才刷新。

### `QODER_LOG_FILE`

- 必填：否
- 敏感：否
- 获取或设置：自行指定可写的脱敏日志路径。
- 填写格式：默认关闭文件日志，显式启用后追加 JSON 行，预演不写。

### `QODER_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：仅从官方请求核对同区域基址；一般无需配置。
- 填写格式：逗号分隔的官方根地址，仅允许与当前区域相同的 https://openapi.qoder.com.cn 或 https://openapi.qoder.sh；不向任意地址或其他地区转发凭据。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每非空行一个 JSON 账号对象；同账号令牌及设备头放在同一对象，不用 & 或 @ 分隔账号。逐账号独立执行，任一失败均非零退出。规范变量为必填凭据入口，兼容旧变量、显式文件及命令行输入可替代。

## 验证与兼容性

SHA-256 `2d373706b01dadaa4f16e919cc0ba76d38d16abadbae426f3be96087346abdfb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e034e75509550071`。

## 副作用与风险

- 显式启用账号后领取可领活动奖励，可能消耗同设备活动领取资格；额外非 CLAIM_BENEFIT 的中国区 Pro 活动仅在明确打开对应开关后领取
- 必要时或仅刷新模式下刷新令牌，可能使旧刷新令牌轮换失效
- 显式配置私有账号文件时将轮换后的令牌原子写回该文件
- 通知启用且非预演时向青龙通知渠道及配置的账号或全局渠道投递脱敏汇总
- 显式启用的中国区 PAT 账号向官方兑换短期任务令牌，随后领取有效活动奖励；短期令牌仅存内存
- 显式设置 QODER_LOG_FILE 且非预演时追加脱敏 JSON 行日志

## 许可证与来源

上游 `wallechfox/qoder-checkin` / `qoder-checkin-金山云文档/Qoder签到-金山文档AirScript.js` / `19ab6365c1f0759bb424a3d69e7de8dca89bf75d`。
