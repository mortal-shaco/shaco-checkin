# Holmes AI 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/bot.py`
- 青龙命令：`python3 scripts/bot.py`
- 建议 Cron：`14 8 * * *`
- 发布哈希：`664959624ee1706cc750cd190203a8bb6559b3ea37adbbcb4ef73ff136286ff1`
- 许可证：`MIT`

## 脚本功能

- Holmes AI Web3 私钥签名登录后每日签到
- 读取用户积分与 CheckinDone；未签到则提交 CheckIn，RetCode=0 视为成功
- 公开钱包地址作为账号身份直接展示以便核对
- 多账号按行处理；规范变量 HOLMESAI_PRIVATE_KEYS，兼容 HOLMESAI_PRIVATE_KEY
- 可选邀请码与 HTTP(S) 代理；默认不提交上游硬编码邀请码
- 完全断网预演 HOLMESAI_DRY_RUN、HTTPS 超时、业务成功/已签到判定
- 脱敏时间轴日志、账号与任务统计、单行 TASK_SUMMARY 与青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `HOLMESAI_PRIVATE_KEYS`

- 必填：是
- 敏感：是
- 获取或设置：在 https://www.holmesai.xyz/ 使用 EVM 钱包登录。将对应钱包的私钥填入青龙环境变量；每个非空行一个私钥。不要把真实私钥写入公开仓库、日志或通知。
- 填写格式：每行一个可选 0x 前缀的 64 位十六进制私钥；账号之间只用换行分隔，不使用 & 或 @

### 可选参数

### `HOLMESAI_PRIVATE_KEY`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名：仅当 HOLMESAI_PRIVATE_KEYS 为空时生效。
- 填写格式：单个可选 0x 前缀的 64 位十六进制私钥

### `HOLMESAI_INVITE_CODE`

- 必填：否
- 敏感：否
- 获取或设置：可选邀请码。上游曾硬编码第三方邀请码，维护版默认不提交；仅在你主动填写时随 GetUser 请求发送。
- 填写格式：短字符串邀请码；留空表示不提交 InviteCode

### `HOLMESAI_PROXY`

- 必填：否
- 敏感：否
- 获取或设置：可选 HTTP(S) 代理；维护版不再读取 proxy.txt，也不再交互选择代理。
- 填写格式：如 http://127.0.0.1:7890；留空表示直连

### `HOLMESAI_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线检查时设置；只校验私钥格式并模拟各阶段，不访问网络、不改动签到状态、不真实发送通知。
- 填写格式：1、true、yes、on 开启完全断网预演；默认关闭

### `HOLMESAI_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选：单次 HTTPS 请求超时秒数。
- 填写格式：5 到 120 的数字；默认 20

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认名单，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、相对路径、文件名或通配符；* 表示全部，空值表示全部关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录；失败不改变业务退出码。
- 填写格式：目录路径；还会尝试 /ql/data/scripts 与 /ql/scripts

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每行一个 EVM 私钥；账号独立处理，任一账号失败时整体以非零退出码结束

## 验证与兼容性

SHA-256 `664959624ee1706cc750cd190203a8bb6559b3ea37adbbcb4ef73ff136286ff1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/5bb7859665960364`。

## 副作用与风险

- Web3 签名登录会在 Holmes AI 建立或刷新会话 Cookie
- 若配置了邀请码，GetUser 可能绑定邀请关系
- 向 Holmes AI 签到接口提交每日签到，改变当日签到状态并可能累计积分（Clue）
- 通知已启用且适配器可用时向青龙通知通道发送脱敏任务统计

## 许可证与来源

上游 `BamarAirdropGroup/HOLMESAI_DAILY_CHECKIN` / `bot.py` / `b45c7937f4d462f2b0aa7cf8173bca92e72bcd47`。
