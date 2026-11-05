# GLaDOS/Railgun 签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/glados_railgun.py`
- 青龙命令：`python3 scripts/glados_railgun.py`
- 建议 Cron：`21 1 * * *`
- 发布哈希：`76df7af05655efc85ca2e74d2a62ff6047429d56f3d7a155a045b3dde401e125`
- 许可证：`GPL-3.0`

## 脚本功能

- 在 glados.cloud 与 railgun.info 执行每日签到，并识别重复签到
- 查询剩余天数，并展示官方返回的非敏感账号身份
- 查询积分余额
- 可选积分兑换 plan100/plan200/plan500，默认关闭避免自动消费
- 设备平台不匹配时按 loginDevice 切换 User-Agent 重试
- 换行多账号、完全断网预演、请求超时与响应大小限制
- 时间轴脱敏日志、账号与任务统计及单行 TASK_SUMMARY
- 按青龙通知策略发送脱敏汇总，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `GLADOS_COOKIES`

- 必填：是
- 敏感：是
- 获取或设置：分别登录 https://glados.cloud 或 https://railgun.info，在浏览器开发者工具网络面板找到 /api/user/status 或 /api/user/checkin 请求，复制请求头 Cookie 的完整值；不要复制响应头 Set-Cookie。登录过期后重新获取。不要把 Cookie 发给他人或写入公开仓库。
- 填写格式：每个非空行一个完整 Cookie；同一账号 Cookie 内的会话、签名及其他字段原样保留在同一行；不使用 &、@ 分隔账号。

### 可选参数

### `GLADOS_EXCHANGE_PLAN`

- 必填：否
- 敏感：否
- 获取或设置：仅在确认需要自动用积分兑换套餐时自行设置；默认不兑换，避免意外消费积分。
- 填写格式：none（默认，不兑换）、plan100、plan200 或 plan500。

### `GLADOS_RAILGUN_SITES`

- 必填：否
- 敏感：否
- 获取或设置：需要只跑单一站点时自行设置；默认双站点与上游一致。
- 填写格式：逗号分隔；仅支持 glados.cloud 与 railgun.info；默认 glados.cloud,railgun.info。

### `GLADOS_RAILGUN_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况自行调整；不填使用默认 30 秒。
- 填写格式：数字秒，允许 5..120；默认 30。

### `GLADOS_RAILGUN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在测试环境自行开启；正式执行时删除或设为 0。
- 填写格式：1/true/yes/on 开启完全断网预演；默认关闭。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在 auto 模式下需要替换默认通知名单时自行设置。
- 填写格式：逗号、分号或空白分隔；可匹配 6c2dc52b4d88710b、scripts/glados_railgun.py、文件名或通配符；* 全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：目录路径；失败后继续尝试 /ql/data/scripts 与 /ql/scripts；通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 Cookie；同一账号的会话与签名放在同一行。账号独立处理，任一账号签到失败则整体非零退出。

## 验证与兼容性

SHA-256 `76df7af05655efc85ca2e74d2a62ff6047429d56f3d7a155a045b3dde401e125`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/6c2dc52b4d88710b`。

## 副作用与风险

- 正式执行时向配置站点提交签到，可能按平台规则增加积分或可用天数
- 当 GLADOS_EXCHANGE_PLAN 设为有效套餐时提交积分兑换，可能消费积分并变更套餐
- 通知启用且适配器可用时向青龙通知渠道投递脱敏任务总结

## 许可证与来源

上游 `zzguang83325/Glados-Railgun-checkin` / `checkin.py` / `97109b0ca9eabb56341fe78454e54a0f6163d9db`。
