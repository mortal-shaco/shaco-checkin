# MiniMax Code每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_7b47bad6.js`
- 青龙命令：`node scripts/task_7b47bad6.js`
- 建议 Cron：`27 9 * * *`
- 发布哈希：`0afe401bc827b68423af29511594d80c496b00434bacd72c5470a26e6e0aef83`
- 许可证：`MIT`

## 脚本功能

- 查询 MiniMax Code 七日签到面板，识别今日可领、已领与连签天数。
- 在今日可领时向 agent 网关提交签到领取，识别本次领取与今天已领幂等结果。
- 支持国内版（agent.minimax.cn）与国际版（agent.minimax.io）Bearer accessToken 多账号。
- 完全断网预演：校验区域与 accessToken 格式、模拟阶段与通知摘要，不发起业务或通知网络请求。
- 按青龙全局开关与脚本名单发送脱敏通知。
- 提供中文时间轴日志、编号阶段、耗时、逐账号与全局统计，以及唯一单行 TASK_SUMMARY JSON。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `MINIMAX_CODE_TOKEN`

- 必填：是
- 敏感：是
- 获取或设置：规范账号变量。在已登录的 MiniMax Code 桌面端本地 auth.json 中，从 records 内 oauth 记录复制 accessToken（常见路径 ~/.minimax/auth/prod/cn 或 en/mcode-public/auth.json）。只填 accessToken，不要填 refreshToken，也不要在青龙中调用刷新接口，否则可能踢掉桌面端登录。令牌通常约 1 小时有效，过期后请重新复制。勿写入公开仓库或日志。
- 填写格式：每个非空行一个账号。推荐 region|accessToken（region 为 cn 或 en），只在首个竖线处拆分。也可整行 JSON：{"region":"cn","accessToken":"...","timezone":"Asia/Shanghai","label":"备注"}。仅 token 时默认国内版。以 # 开头的行忽略。不使用 & 或 @ 分隔账号。

### 可选参数

### `MINIMAX_MCODE_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当未设置 MINIMAX_CODE_TOKEN 时读取；获取方式与规范变量相同。
- 填写格式：与 MINIMAX_CODE_TOKEN 相同。

### `MINIMAX_ACCESS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当 MINIMAX_CODE_TOKEN 与 MINIMAX_MCODE_TOKEN 皆为空时读取。
- 填写格式：与 MINIMAX_CODE_TOKEN 相同。

### `MINIMAX_CODE_REGION`

- 必填：否
- 敏感：否
- 获取或设置：账号行未写 region 时使用的默认区域；国内版填 cn，国际版填 en。
- 填写格式：cn 或 en；缺省 cn。

### `MINIMAX_CODE_TIMEZONE`

- 必填：否
- 敏感：否
- 获取或设置：签到接口 timezone_id 参数；需与账号活动时区一致时可手动设置。
- 填写格式：IANA 时区名，例如 Asia/Shanghai；缺省使用运行环境本机时区，失败时回退 Asia/Shanghai。

### `MINIMAX_CODE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要断网验证配置时手动设置；正式执行时删除或设为 0。
- 填写格式：1、true、yes、on 表示完全断网预演；其他值或未设置表示正式执行。预演不访问业务接口、不投递真实通知。

### `MINIMAX_CODE_TIMEOUT_MS`

- 必填：否
- 敏感：否
- 获取或设置：需要调整单次 HTTP 超时时间时手动设置。
- 填写格式：1000 至 120000 的整数毫秒；缺省或非法值使用 20000。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙通知名单中填入 7b47bad620ba7931、实际脚本文件名或 scripts 相对路径；未设置时默认对本任务发送通知。
- 填写格式：逗号、分号、空白或换行分隔的选择器；支持 * 与 ? 通配；* 表示全部；显式空值关闭全部青龙通知。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知工具不在默认目录时，填写本机 sendNotify.js 或 notify.py 所在目录。
- 填写格式：本地目录路径。依次尝试指定目录与 /ql/data/scripts、/ql/scripts 下的 sendNotify.js，再尝试 notify.py；通知失败只记录脱敏状态。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

MINIMAX_CODE_TOKEN（或兼容别名）每个非空行一个账号；同一账号的区域与 accessToken 合并在一行。账号逐个独立查询并领取，任一账号失败则整体非零退出，其余账号继续执行。

## 验证与兼容性

SHA-256 `0afe401bc827b68423af29511594d80c496b00434bacd72c5470a26e6e0aef83`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7b47bad620ba7931`。

## 副作用与风险

- 正式运行且今日可领时，向 MiniMax agent 网关提交签到领取，可能增加账户积分并更新签到状态。
- 启用通知且非预演时，通过青龙 notify 发送脱敏账号统计。

## 许可证与来源

上游 `jk-uzi/minimax-proxy` / `src/signin.ts` / `7be1e3c5f585c2ad962813fd2cde2961cd2aef26`。
