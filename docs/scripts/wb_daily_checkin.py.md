# WorkBuddy 每日积分签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/wb_daily_checkin.py`
- 青龙命令：`python3 scripts/wb_daily_checkin.py`
- 建议 Cron：`38 9 * * *`
- 发布哈希：`8d131996755db5b032ffeb0be640ef6405f5a82b9313a2e3e05524aebb2450cb`
- 许可证：`MIT`

## 脚本功能

- 每日领取 WorkBuddy 积分；领取请求只发送一次，避免不确定结果下自动重复写入。
- 按原顺序使用两个官方状态接口兜底，官方状态显示已签到时跳过领取。
- 汇总本次和累计积分、账户真实余额、连续签到天数及活动名称；保留原有逐账号 JSON 结果并正确显示数值零。
- 支持令牌环境变量、兼容 --token 参数、可选本人本机登录文件，以及用户、组织和租户请求头。
- 支持每行一个账号，账号独立处理，全部账号结束后按业务结果返回退出码。
- 增加完全断网预演、超时、禁止重定向、响应大小限制、严格业务核验和敏感信息隐藏。
- 展示官方返回的昵称、用户名、显示名及公开用户标识，逐阶段记录结果与耗时，最终输出唯一 TASK_SUMMARY。
- 支持青龙通知开关、脚本选择与通知模块发现，通知失败不影响业务退出码。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `WB_DAILY_CHECKIN_TOKEN`

- 必填：是
- 敏感：是
- 获取或设置：在本人已登录的 WorkBuddy 客户端登录信息中读取 auth.accessToken 或 auth.access_token；也可从本人向 https://www.codebuddy.cn 发起的已认证请求中获取 Authorization 的 Bearer 令牌部分。不要分享或公开这些值。macOS 文件位于 ~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info；Windows 位于 LOCALAPPDATA 或 APPDATA 下相同相对路径；Linux 位于 XDG_DATA_HOME 或 ~/.local/share 下相同相对路径。可在无客户端的青龙环境直接填写令牌，无需复制客户端或安装额外程序。
- 填写格式：每个非空行一个账号；每行为原始令牌、uid+token（只在第一个 + 处分割），或单行 JSON 对象，字段 token 必填，uid、org、domain 可选。uid 对应 account.uid/id，org 对应 account.enterpriseId/enterprise_id，domain 对应 auth.domain 或根级 domain。不同账号只能换行分隔。兼容 --token 参数优先输入；未配置环境变量时可选读取本人本机登录文件。

### 可选参数

### `WB_DAILY_CHECKIN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：设置为 1 开启完全断网预演；正式运行取消设置。
- 填写格式：1、true、yes、on 表示启用，默认关闭；预演仍需占位账号参数。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：通知设为 auto 时配置选中脚本。未配置时此任务不在默认推送名单中。
- 填写格式：逗号、分号、空白或换行分隔；支持目录路径、文件名、文件名通配符、437220302cb75855；* 表示全部，空值表示关闭全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填写本人青龙 notify.py 或 sendNotify.js 所在目录；默认先尝试导入 notify.send，再查找青龙标准脚本目录。
- 填写格式：现有通知模块目录路径；通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；配套令牌和用户、组织、域字段放在同一个单行 JSON 对象中；兼容 uid+token 时只在第一个 + 处分割。逐账号执行，任一账号失败时整体非零退出。

## 验证与兼容性

SHA-256 `8d131996755db5b032ffeb0be640ef6405f5a82b9313a2e3e05524aebb2450cb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/437220302cb75855`。

## 副作用与风险

- 正式运行时对尚未签到或状态暂不可查询的账号尝试领取每日积分。
- 启用通知且非预演时通过现有青龙通知模块发送脱敏任务总结。

## 许可证与来源

上游 `Keefe-Hu/WB-daily-checkin` / `scripts/wb_daily_checkin.py` / `740e36c8bcd5d9725eac08ecbd948ea8aa09d042`。
