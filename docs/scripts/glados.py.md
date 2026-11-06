# GLaDOS每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/glados.py`
- 青龙命令：`python3 scripts/glados.py`
- 建议 Cron：`58 0 * * *`
- 发布哈希：`ebd428003697661efbaf877c480b83be082579ed1ed59dff3e8ec1b248327fee`
- 许可证：`GPL-3.0`

## 脚本功能

- 每日签到与重复签到业务识别，兼容上游消息判定
- 官方账号身份原样展示与剩余天数查询
- 可选积分余额与连续签到天数查询，兼容历史余额与签到响应补充统计
- 可选积分兑换 plan100/plan200/plan500，默认关闭避免自动消费
- 显式选择 rocks、cloud 或 railgun 同产品接口，保留默认配置且不自动跨域
- 设备平台不匹配时按 loginDevice 切换 User-Agent 重试一次（已手动指定 UA 时不改写）
- 换行多账号与旧 Cookie、会话签名配对变量及 GLADOS_COOKIES 兼容
- 请求超时、可选重试、代理及浏览器标识配置
- 完整断网预演、分阶段脱敏日志、账号与任务统计及单行结构化汇总
- 青龙通知开关、任务选择、Python 到 JavaScript 通知发现链及可选飞书签名通知
- 显式归档站点列表、旧超时与预演开关兼容；保留归档表单编码、同站设备 UA 延续、无身份状态响应及仅签到决定账号结果的失败语义

## 环境变量与参数

先配置必选参数再运行；条目注明的兼容变量可以替代规范变量。缺少任一必选参数及其全部兼容变量时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `GR_COOKIE`

- 必填：是（也可设置 `GLADOS_COOKIES`）
- 敏感：是
- 获取或设置：登录对应 GLaDOS 或 Railgun 网站后，在浏览器开发者工具网络面板打开 /api/user/status 或 /api/user/checkin 请求，复制请求头中的完整 Cookie；不要复制响应头 Set-Cookie，也不要把该值发给他人或写入公开仓库。
- 填写格式：每个非空行一个完整 Cookie；同一账号 Cookie 内的会话、签名及其他字段原样保留在同一行；不使用 &、@ 分隔账号。 规范模式的凭据入口至少配置一组，按 GR_COOKIE、GLADOS_COOKIE、GLADOS_COOKIES、GLADOS_GLD 配对、GLADOS_KOA 配对依次选择首组；归档模式不使用本变量。

### 可选参数

### `GLADOS_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容旧变量名；未设置 GR_COOKIE 时按相同方式获取并填写。
- 填写格式：与 GR_COOKIE 相同，每行一个完整 Cookie。

### `GLADOS_COOKIES`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游复数变量名；未设置 GR_COOKIE 与 GLADOS_COOKIE 时按相同方式获取并填写。
- 填写格式：与 GR_COOKIE 相同，必须换行分隔账号，不再使用上游的 & 分隔。 显式设置 GLADOS_RAILGUN_SITES 时本变量必填且独占，不回退至其他账号变量；每行 Cookie 必须明确授权用于所列 cloud/railgun 站点。

### `GLADOS_GLD_SESS`

- 必填：否
- 敏感：是
- 获取或设置：仅当无法提供完整 Cookie 时，从同一账号 Cookie 中拆出 gld:sess 值；建议优先合并为 GR_COOKIE。
- 填写格式：每行一个会话值，必须与 GLADOS_GLD_SESS_SIG 逐行配对。

### `GLADOS_GLD_SESS_SIG`

- 必填：否
- 敏感：是
- 获取或设置：与 GLADOS_GLD_SESS 来自同一账号 Cookie 的 gld:sess.sig。
- 填写格式：每行一个签名，必须与 GLADOS_GLD_SESS 逐行配对。

### `GLADOS_KOA_SESS`

- 必填：否
- 敏感：是
- 获取或设置：仅当无法提供完整 Cookie 时，从同一账号 Cookie 中拆出 koa:sess 值；建议优先合并为 GR_COOKIE。
- 填写格式：每行一个会话值，必须与 GLADOS_KOA_SESS_SIG 逐行配对。

### `GLADOS_KOA_SESS_SIG`

- 必填：否
- 敏感：是
- 获取或设置：与 GLADOS_KOA_SESS 来自同一账号 Cookie 的 koa:sess.sig。
- 填写格式：每行一个签名，必须与 GLADOS_KOA_SESS 逐行配对。

### `GLADOS_SITE`

- 必填：否
- 敏感：否
- 获取或设置：按账号实际登录站点自行选择；默认 rocks，不自动跨域、不探测多域名。
- 填写格式：rocks、cloud 或 railgun；cloud 使用 glados.cloud 与 token=glados.cloud；railgun 使用 railgun.info 与 token=railgun.info。 与 GLADOS_RAILGUN_SITES 不得同时设置，包括显式 rocks。

### `GLADOS_POINTS`

- 必填：否
- 敏感：否
- 获取或设置：需要查询积分与连续签到天数时自行开启；cloud/railgun 默认开启，rocks 默认关闭。
- 填写格式：1/true/yes/on 开启；0/false/no/off 关闭。启用兑换时会自动查询积分。 仅控制规范单站模式；归档兼容模式保留每站固定积分查询。

### `GLADOS_EXCHANGE_PLAN`

- 必填：否
- 敏感：否
- 获取或设置：仅在确认需要自动用积分兑换套餐时自行设置；默认不兑换，避免意外消费积分。上游默认自动兑换不会恢复。
- 填写格式：none（默认，不兑换）、plan100、plan200 或 plan500。

### `GLADOS_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况自行调整单次请求超时；不填使用默认 15 秒。
- 填写格式：1 到 60 之间的数字秒，默认 15。 显式设置时优先于旧超时；未设置两种超时时，规范模式默认 15 秒，归档模式默认 30 秒。

### `GLADOS_RETRIES`

- 必填：否
- 敏感：否
- 获取或设置：网络抖动时可自行增加签到重试次数；登录失效、拒绝访问或设备不匹配不会按该次数重试。
- 填写格式：0 到 5 的整数，默认 0。

### `GLADOS_USER_AGENT`

- 必填：否
- 敏感：否
- 获取或设置：需要固定浏览器标识时自行设置；未设置时若遇 device-mismatch 会按 loginDevice 自动切换平台 UA 重试一次。
- 填写格式：普通 User-Agent 字符串，不能包含控制字符。

### `CHECKIN_PROXY_URL`

- 必填：否
- 敏感：是
- 获取或设置：需要经代理访问时自行配置；不填则直连。
- 填写格式：带端口的 http 或 https 代理地址，例如 http://127.0.0.1:7890。

### `GLADOS_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在测试环境自行开启；正式执行时删除或设为 0。
- 填写格式：1/true/yes/on 开启完全断网预演；默认关闭。 与 GLADOS_RAILGUN_DRY_RUN 按逻辑或合并，任一开启即禁止全部业务与通知网络。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在 auto 模式下需要替换默认通知名单时自行设置。
- 填写格式：逗号、分号或空白分隔；可匹配 catalogId、脚本路径、文件名或通配符；* 全选，空值全关。 同时兼容归档 ID 6c2dc52b4d88710b、scripts/glados_railgun.py 和 glados_railgun.py。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：目录路径；失败后继续尝试 /ql/data/scripts 与 /ql/scripts；通知失败不改变业务退出码。

### `FEISHU_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：需要额外飞书通知时，在飞书开放平台创建自定义机器人并复制 webhook。
- 填写格式：仅允许 https://open.feishu.cn 或 https://open.larksuite.com 的官方 bot/v2/hook 地址。

### `FEISHU_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：飞书机器人启用签名校验时填写对应密钥。
- 填写格式：飞书自定义机器人签名密钥；未启用签名可留空。

### `GLADOS_RAILGUN_SITES`

- 必填：否
- 敏感：否
- 获取或设置：仅在确认 GLADOS_COOKIES 的每行 Cookie 均可用于所列归档站点后显式填写；不填保持规范单站，不恢复旧双站默认值。
- 填写格式：逗号分隔，仅允许 glados.cloud 与 railgun.info，保序去重；空值、其他域名及与 GLADOS_SITE 同设均报配置错误。归档账号及设备缓存、积分和兑换判断仅在当前站点使用，不向 rocks 发送归档模式凭据。

### `GLADOS_RAILGUN_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况自行调整；不填使用默认 30 秒。
- 填写格式：有限数字秒，范围 5..120；空值按 30 秒。仅在 GLADOS_TIMEOUT 未设置时使用；单独设置本变量不会开启多站。

### `GLADOS_RAILGUN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在测试环境自行开启；正式执行时删除或设为 0。
- 填写格式：1/true/yes/on/y 开启完全断网预演；与 GLADOS_DRY_RUN 按逻辑或合并，不能被另一开关的 0 覆盖；不会开启多站。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，按原顺序独立执行。

## 验证与兼容性

SHA-256 `ebd428003697661efbaf877c480b83be082579ed1ed59dff3e8ec1b248327fee`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/2d633fe3129937b6`。

## 副作用与风险

- 执行 GLaDOS 签到，可能按平台规则增加积分或账户可用天数
- 当 GLADOS_EXCHANGE_PLAN 设为有效套餐时提交积分兑换，可能消费积分并变更套餐
- 非预演模式下按通知配置向青龙通知渠道和已配置的飞书机器人发送脱敏摘要
- 归档兼容模式仅向显式所列 glados.cloud/railgun.info 发送 GLADOS_COOKIES；默认不兑换，预演不签到、不兑换、不发送通知

## 许可证与来源

上游 `hennessey-v/GlaDOS_Checkin_ql` / `checkin.py` / `d858874736fc8d80f24ebcd17721fd1f924252db`。
