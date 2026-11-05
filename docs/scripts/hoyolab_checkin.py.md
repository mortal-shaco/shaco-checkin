# HoYoLAB 多游戏每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/hoyolab_checkin.py`
- 青龙命令：`python3 scripts/hoyolab_checkin.py`
- 建议 Cron：`25 8 * * *`
- 发布哈希：`40ff9d2736b5f6373b24d5463bb8824eaaa2924ee8cb168da10e1173c5a591e7`
- 许可证：`MIT`

## 脚本功能

- HoYoLAB 国际服原神、崩坏：星穹铁道、崩坏3、绝区零、未定事件簿每日签到
- 可按 HOYOLAB_GAMES 选择游戏或全部签到；可开启仅查询签到信息模式
- 签到前查询已绑定游戏角色并展示公开昵称/UID/区服，便于核对账号
- 支持每行一个账号，独立汇总成功、已完成与失败；兼容上游 LTOKEN_V2+LTUID_V2 单账号别名
- 识别今日已签到与 Cookie 失效/频率限制等业务码
- 完全断网预演、请求超时与响应大小限制、时间轴日志与单行 TASK_SUMMARY
- 按青龙通知策略发送脱敏汇总，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `HOYOLAB_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录 https://www.hoyolab.com ，打开开发者工具 → Application → Cookies，复制当前账号的 ltoken_v2 与 ltuid_v2。不要把 Cookie 发给他人或写入公开仓库。
- 填写格式：每个非空行一个账号。推荐 Cookie 片段：ltoken_v2=...; ltuid_v2=...。也支持「ltuid|ltoken」，仅在第一个竖线处拆分。不使用 & 或 @ 分隔账号。

### 可选参数

### `LTOKEN_V2`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游单账号别名；仅当 HOYOLAB_ACCOUNTS 为空时与 LTUID_V2 一起生效。获取方式同 HOYOLAB_ACCOUNTS。
- 填写格式：ltoken_v2 Cookie 值字符串。

### `LTUID_V2`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游单账号别名；仅当 HOYOLAB_ACCOUNTS 为空时与 LTOKEN_V2 一起生效。获取方式同 HOYOLAB_ACCOUNTS。
- 填写格式：ltuid_v2 数字 UID。

### `HOYOLAB_GAMES`

- 必填：否
- 敏感：否
- 获取或设置：按需选择要签到或查询的游戏；不填默认全部。
- 填写格式：all 或逗号分隔代号：genshin,starrail,honkai3rd,zzz,tears；默认 all。

### `HOYOLAB_INFO_ONLY`

- 必填：否
- 敏感：否
- 获取或设置：仅想查询签到信息而不提交签到时自行开启。
- 填写格式：1/true/yes/on 仅查询；默认关闭并执行签到。

### `HOYOLAB_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况自行调整；不填使用默认 30 秒。
- 填写格式：整数秒，允许 5..120；默认 30。

### `HOYOLAB_DRY_RUN`

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
- 填写格式：逗号、分号或空白分隔；可匹配 catalogId、scripts/hoyolab_checkin.py、文件名或通配符；* 全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：目录路径；失败后继续尝试 /ql/data/scripts 与 /ql/scripts；通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；同一账号的 ltuid 与 ltoken 写在同一行。账号独立执行，任一失败或配置错误则整体非零退出。

## 验证与兼容性

SHA-256 `40ff9d2736b5f6373b24d5463bb8824eaaa2924ee8cb168da10e1173c5a591e7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/a79010908be3c115`。

## 副作用与风险

- 正式执行且非仅查询模式时，向所选游戏提交每日签到请求，可能发放签到奖励并改变当日签到状态
- 通知启用且适配器可用时向青龙通知渠道投递脱敏任务总结

## 许可证与来源

上游 `oratis/gameclaw` / `gameclaw_skill/scripts/hoyolab_checkin.py` / `c5b8f3b304b0061575f108172da4dc45de585597`。
