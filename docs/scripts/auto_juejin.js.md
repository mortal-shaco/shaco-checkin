# 掘金每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/auto_juejin.js`
- 青龙命令：`node scripts/auto_juejin.js`
- 建议 Cron：`36 10 * * *`
- 发布哈希：`2854f6ba1611d1ac133b6304da1077b43567acd7db3a2cb844335361f9e2d7f2`
- 许可证：`MIT`

## 脚本功能

- 查询今日签到状态，未签到时执行签到并再次核验
- 读取连续签到天数、累计签到天数和当前矿石余额
- 读取累计幸运值
- 显式开启后使用有效抽奖历史记录沾喜气
- 显式开启后查询免费次数，仅在次数为正时抽奖一次并显示奖品
- 每行一个账号独立执行，失败汇总并非零退出
- 完全断网预演、带时间戳的分阶段日志、账号和任务统计、单行结构化汇总
- 按青龙通知开关和脚本名单发送脱敏摘要，通知失败保留业务退出码
- 默认查询并显示官方免费抽奖次数；无免费次数正常跳过，查询失败禁止抽奖
- 兼容逐行 aid|sessionid 多账号和旧 juejin_aid、juejin_sessionid 单账号参数；每个账号保留独立 aid 查询参数
- 保留云函数 main 导出及 result、msg 返回值，导入不自动执行，阶段保留 result、msg 机器可读输出
- 显示官方返回的昵称、用户名、显示名称或公开 UID；抑制凭据、手机号和原始响应
- 显式选择后从官方中奖记录取得有效历史编号，使用 JSON 请求体沾喜气并校验本次幸运值
- 兼容逐行 JSON 的 cookie、aid、uuid、signature 或 _signature，保留账号级查询参数
- 显式 signin、lucky、draw 追加开关，始终保留原签到和只读统计

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `JUEJIN_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：登录掘金网页版，打开浏览器开发者工具的网络面板，从本人 api.juejin.cn 已登录请求的请求头复制完整 Cookie。过期后重新登录获取，不要向他人发送请求或凭据。 这是维护版规范变量；也兼容 JUEJIN_ACCOUNTS 或旧变量对。
- 填写格式：每个非空行一个账号的完整 Cookie，使用键值对，保留分号及后续内容，不添加 Cookie: 前缀，不用 & 或 @ 分隔账号。 输入优先级为 JUEJIN_COOKIE、JUEJIN_ACCOUNTS、juejin_aid 与 juejin_sessionid；显式设置的高优先级空值视为配置错误，不回退。

### 可选参数

### `JUEJIN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要完全断网预演时设置为 1。预演不投递可能联网的通知，记录脱敏摘要与通知计划。
- 填写格式：1、true、yes、on 开启，0、false、no、off 关闭，默认关闭。

### `JUEJIN_DIP_LUCKY`

- 必填：否
- 敏感：否
- 获取或设置：需要沾喜气时显式设置为 1，同时提供有效历史记录 ID。
- 填写格式：布尔开关，默认 0，对所有账号生效。

### `JUEJIN_LOTTERY_HISTORY_ID`

- 必填：否
- 敏感：是
- 获取或设置：configured 来源开启沾喜气时必填，从本人请求取得有效 lottery_history_id；global 来源自动获取，不使用该值。
- 填写格式：十进制数字字符串，共享的目标抽奖历史记录标识，无需与登录凭据合并。

### `JUEJIN_FREE_LOTTERY`

- 必填：否
- 敏感：否
- 获取或设置：接受抽奖副作用时显式设置为 1。只在官方免费次数为正时抽奖一次；接口未提供强制免费参数，并发可能消耗矿石，请勿并发执行。
- 填写格式：布尔开关，默认 0，对所有账号生效。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：按需设置青龙通知开关；auto 仅通知名单内脚本，未提供名单默认关闭。强制开启仍遵守显式设置的名单；断网预演只记录通知摘要。
- 填写格式：逗号、分号、空白或换行分隔，支持 * 和 ?，* 匹配全部，空值关闭全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：通知模块位于自定义目录时填写，默认查找 /ql/data/scripts 和 /ql/scripts；模块不可用时保留业务退出码。
- 填写格式：可选目录路径，目录中应存在导出 sendNotify 函数的 sendNotify.js。

### `JUEJIN_ACCOUNTS`

- 必填：否
- 敏感：是
- 获取或设置：仅未设置 JUEJIN_COOKIE 时启用。登录掘金网页，从本人 api.juejin.cn 请求取得 Cookie 头及 aid、uuid、_signature 查询参数。所有字段须来自同一账号会话；signature 兼容 _signature。也保留旧 aid|sessionid 输入。
- 填写格式：每个非空行一个账号：aid|sessionid（仅按第一个 | 拆分），或完整 JSON 对象（cookie、aid、uuid、signature 均为非空字符串，aid 为数字）。不使用 & 或 @ 分隔账号。

### `juejin_aid`

- 必填：否
- 敏感：否
- 获取或设置：兼容上游单账号变量，从掘金请求查询参数取得。仅未设置 JUEJIN_ACCOUNTS 时使用，必须配合 juejin_sessionid。 同时未设置 JUEJIN_COOKIE 时才启用。
- 填写格式：数字应用标识

### `juejin_sessionid`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游单账号变量，从登录后的掘金请求 Cookie 取得 sessionid 值。仅未设置 JUEJIN_ACCOUNTS 时使用，必须配合 juejin_aid。 同时未设置 JUEJIN_COOKIE 时才启用。
- 填写格式：单账号会话值，不含字段名

### `JUEJIN_TASKS`

- 必填：否
- 敏感：否
- 获取或设置：按需显式追加来源任务，不取消维护版每日签到与只读统计。未设置时完全使用原开关。
- 填写格式：逗号分隔 signin、lucky、draw；lucky 开启沾喜气，draw 开启一次免费抽奖。lucky 且未提供来源和手动 ID 时使用 global。

### `JUEJIN_LUCKY_SOURCE`

- 必填：否
- 敏感：否
- 获取或设置：需要自动选择官方中奖记录时设置 global；configured 保留手动历史 ID。此变量不单独开启沾喜气。
- 填写格式：configured 或 global；默认 configured，但显式任务包含 lucky 且无手动 ID 时默认 global。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

优先读取 JUEJIN_COOKIE，每个非空行一个账号的完整 Cookie，不按分号、& 或 @ 拆分。未设置时兼容 JUEJIN_ACCOUNTS，每个非空行 aid|sessionid，仅按第一个 | 拆分并保留后续会话文本；再兼容旧变量对单账号。显式空值不回退。各账号独立执行，任一失败整体非零退出。 JUEJIN_ACCOUNTS 另支持逐行 JSON 对象，保留每账号 uuid、signature 查询参数；单账号无效不阻止其他账号。

## 验证与兼容性

SHA-256 `2854f6ba1611d1ac133b6304da1077b43567acd7db3a2cb844335361f9e2d7f2`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/9e33a705da89cfd6`。

## 副作用与风险

- 未签到时完成每日签到并触发平台签到奖励
- 显式开启后沾喜气并改变平台幸运值相关状态
- 显式开启后执行一次抽奖并改变抽奖次数、奖品及幸运值；并发情况下可能消耗矿石
- 开启并匹配通知条件时通过青龙通知模块发送任务摘要

## 许可证与来源

上游 `suojian0313/juejin_helper` / `auto_juejin.js` / `790a83033e4979e0a66399678be46337f09e218b`。
