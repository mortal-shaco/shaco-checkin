# NewAPI 活动中心签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/activity_checkin.py`
- 青龙命令：`python3 scripts/activity_checkin.py`
- 建议 Cron：`22 8 * * *`
- 发布哈希：`5c235fafca6439c7dcaf245e678ead1c489a461c8f96584bc5750c9e16282756`
- 许可证：`MIT`

## 脚本功能

- 账号密码登录获取 JWT，适配活动中心白银签到、星河每日领取与晚晚舟 /api/v1 签到
- 可按 site_hint 指定站点类型，或自动探测活动中心与星河流程
- 支持每行一个账号，独立汇总成功、已完成与失败
- 展示登录返回的非敏感昵称/用户名/公开 UID，隐藏密码、JWT 与原始响应
- 完全断网预演、请求超时与响应大小限制、时间轴日志与单行 TASK_SUMMARY
- 按青龙通知策略发送脱敏汇总，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ACTIVITY_CHECKIN_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人使用的 NewAPI fork 站点注册并登录，准备站点根地址、登录用户名（晚晚舟站点可填邮箱）与密码。系统访问令牌(nap_)只读，不能替代密码登录。user_id 可从本人 /api/user/self 的 data.id 或请求头 New-Api-User 获取，不能根据用户名猜测。不要把密码发给他人或写入公开仓库。
- 填写格式：每个非空行一个账号。推荐 JSON：{"url":"https://站点根","username":"用户名","password":"密码"}，可选 user_id、site_hint（activity_center/xingya/wanwanzhou/auto）。也支持「站点|用户名|密码」，仅拆前两个竖线以保留密码中的竖线；可再追加|数字user_id 与|site_hint。不使用 & 或 @ 分隔账号。

### 可选参数

### `ACTIVITY_CHECKIN_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按站点网络情况自行调整；不填使用默认 30 秒。
- 填写格式：整数秒，允许 5..120；默认 30。

### `ACTIVITY_CHECKIN_DRY_RUN`

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
- 填写格式：逗号、分号或空白分隔；可匹配 catalogId、scripts/activity_checkin.py、文件名或通配符；* 全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：目录路径；失败后继续尝试 /ql/data/scripts 与 /ql/scripts；通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；同一账号的站点、用户名、密码及可选 user_id/site_hint 写在同一行。账号独立执行，任一失败或配置错误则整体非零退出。

## 验证与兼容性

SHA-256 `5c235fafca6439c7dcaf245e678ead1c489a461c8f96584bc5750c9e16282756`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/1e2ace06c33b3dec`。

## 副作用与风险

- 正式执行时登录并提交签到/领取请求，可能发放白银、额度或余额奖励并改变当日签到状态
- 通知启用且适配器可用时向青龙通知渠道投递脱敏任务总结

## 许可证与来源

上游 `yan470777-commits/checkin` / `activity_checkin.py` / `c0420cd3ba766b26a03014e40c9ca05d2ae1e6b2`。
