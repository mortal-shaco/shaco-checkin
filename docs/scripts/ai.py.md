# AiCheckin 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/ai.py`
- 青龙命令：`python3 scripts/ai.py`
- 建议 Cron：`54 10 * * *`
- 发布哈希：`88199c18bd23d0ff483d3224e5bde961340e34c7e56fd01f8da2868ef056fbeb`
- 许可证：`MIT`

## 脚本功能

- WorkBuddy 状态预检、每日积分签到及已签到幂等识别
- Trae CN 状态预检、每日签到、稳定设备请求头、积分余额和最早过期日期查询
- Qoder 查询并仅领取积分权益签到活动、逐活动校验及幂等回放识别
- 保留主脚本已有三项服务，支持按账号配置、停领标记及 --no-trae、--no-qoder 跳过选项
- 令牌有效期提示、限流与网络错误重试、可选 Trae 和 Qoder 自动续期及私有原子状态保存
- 多账号独立处理、离线预演、时间轴日志、单行结构化汇总与青龙脱敏通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `AI_CHECKIN_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人已登录客户端的开发者工具网络面板取得对应接口请求凭据。WorkBuddy 取 billing 请求 Authorization 的 Bearer 值；Trae 取 checkin_credits 请求 Cloud-IDE-JWT 值和本人用户 ID；Qoder 取 campaigns 请求 Bearer 及 Cosy-MachineId、Cosy-MachineToken、Cosy-MachineCode、Cosy-MachineType。禁止分享或提交凭据。
- 填写格式：每个非空行一个 JSON 对象。必填 service（workbuddy、trae、qoder）和 token。Trae 另填 user_id，region 仅支持 CN。Qoder 另填 machine_id 和 device 对象，其中 machineToken、machineCode、machineType 必填。可选 excluded 为布尔值，refresh_token 为本人刷新令牌，expires_at 为带时区的 ISO 时间。对象内部字段组合本账号配套凭据，不使用其他符号分隔账号。

### 可选参数

### `WORKBUDDY_ACCESS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容输入，从本人 WorkBuddy billing 请求的 Authorization 取得；仅未配置规范账号变量时读取。
- 填写格式：每个非空行一个令牌，不带 Bearer 前缀。

### `WORKBUDDY_UID`

- 必填：否
- 敏感：否
- 获取或设置：可选兼容输入，从本人 WorkBuddy 账号信息取得。
- 填写格式：按账号行对应的 UID，仅用于参数兼容。

### `TRAE_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容输入，从本人 Trae CN checkin_credits 请求 Authorization 取得；仅未配置规范账号变量时读取。
- 填写格式：每个非空行一个 JWT，不带 Cloud-IDE-JWT 前缀。

### `TRAE_USER_ID`

- 必填：否
- 敏感：否
- 获取或设置：可选兼容输入，从本人 Trae CN 账号信息取得；缺省尝试 JWT 的 data.id。
- 填写格式：按令牌账号行对应的用户 ID。

### `TRAE_REGION`

- 必填：否
- 敏感：否
- 获取或设置：本人 Trae 客户端区域，仅支持国内版。
- 填写格式：CN。

### `CHECKIN_REFRESH_STATE`

- 必填：否
- 敏感：否
- 获取或设置：自行指定专用私有状态文件位置；启用后才允许刷新令牌及安全持久化。文件应仅供本任务访问，勿提交或放入订阅目录。
- 填写格式：可写文件路径，父目录须已存在；文件权限 600，锁文件保护并发；不配置则不轮换凭据。

### `WORKBUDDY_DOMAIN`

- 必填：否
- 敏感：否
- 获取或设置：按本人账号的官方 CodeBuddy 服务区域选择，默认 www.codebuddy.cn。
- 填写格式：www.codebuddy.cn 或 www.codebuddy.com。

### `CHECKIN_HTTP_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按运行环境配置请求超时，默认 30 秒。
- 填写格式：1 至 120 的整数，单位秒。

### `CHECKIN_MAX_RETRY`

- 必填：否
- 敏感：否
- 获取或设置：按运行环境配置 WorkBuddy 重试次数，默认 14。
- 填写格式：1 至 20 的整数。

### `CHECKIN_TRAE_MAX_RETRY`

- 必填：否
- 敏感：否
- 获取或设置：按运行环境配置 Trae 领取重试次数，默认 4。
- 填写格式：1 至 20 的整数。

### `CHECKIN_RETRY_WAIT_MIN`

- 必填：否
- 敏感：否
- 获取或设置：按运行环境配置网络失败等待下限，默认 15 秒。
- 填写格式：0 至 300 的整数。

### `CHECKIN_RETRY_WAIT_MAX`

- 必填：否
- 敏感：否
- 获取或设置：按运行环境配置网络失败等待上限，默认 30 秒；业务限流保留上游递增等待。
- 填写格式：下限至 300 的整数。

### `AI_CHECKIN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线验证时设为 1。
- 填写格式：1、true、yes、on 启用，其他值正式执行。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙设置需要通知的脚本选择器；默认未列入，不投递。
- 填写格式：逗号、分号、空白或换行分隔的目录相对路径、文件名、通配符或目录编号；* 选择全部，空值关闭自动选择。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知组件所在目录；可选，自动发现标准目录或可导入的 notify 模块。
- 填写格式：含 notify.py 或 sendNotify.js 的目录路径。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个 JSON 账号对象，同一账号的凭据集中在该对象；逐账号独立处理，任一账号失败则整体非零退出。兼容令牌别名也按非空行分账号。

## 验证与兼容性

SHA-256 `88199c18bd23d0ff483d3224e5bde961340e34c7e56fd01f8da2868ef056fbeb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/89bf4d992b4beaa3`。

## 副作用与风险

- 正式执行时领取 WorkBuddy 每日签到积分
- 正式执行时领取 Trae CN 每日签到积分
- 正式执行时领取 Qoder 可领取的积分权益活动
- 显式配置私有状态文件及刷新令牌后轮换 Trae 或 Qoder 凭据并保存状态
- 按通知开关与选择器发送脱敏青龙通知

## 许可证与来源

上游 `LiSeafood/AiCheckin` / `checkin.py` / `2c7c9eaff484c45e539dd15288551b4166604032`。
