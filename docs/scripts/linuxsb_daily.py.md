# linux.sb 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/linuxsb_daily.py`
- 青龙命令：`python3 scripts/linuxsb_daily.py`
- 建议 Cron：`10 8 * * *`
- 发布哈希：`e9c32b5b2daf8ccf8fadb1b5bcb139597ebce12e1880adc9baff2f150f793f03`
- 许可证：`MIT`

## 脚本功能

- 使用 Cookie 访问 linux.sb 每日签到页并提交签到
- 识别今日已签到/重复签到并按成功收尾
- 展示官方返回的用户名、当前积分与连续签到等非敏感概览
- 识别 Cloudflare 挑战并明确失败（不启动本机浏览器）
- 换行多账号、完全断网预演、请求超时与响应大小限制
- 时间轴脱敏日志、账号与任务统计及单行 TASK_SUMMARY
- 按青龙通知策略发送脱敏汇总，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `LINUXSB_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录 https://linux.sb 后，打开开发者工具网络面板，任选同域请求，复制请求头 Cookie 的完整值（需含 bbs_auth 等登录态）；不要复制响应头 Set-Cookie。登录过期或邮箱验证后请重新获取。不要把 Cookie 发给他人或写入公开仓库。
- 填写格式：每个非空行一个账号的完整 Cookie；同一账号内多个字段用分号连接并保留在同一行；不使用 &、@ 分隔账号。

### 可选参数

### `LINUXSB_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况自行调整；不填使用默认 30 秒。
- 填写格式：数字秒，允许 5..120；默认 30。

### `LINUXSB_SITE_GAP_MIN`

- 必填：否
- 敏感：否
- 获取或设置：需要拉开与其它任务执行间隔时自行设置；默认 0 表示不等待。兼容别名 SITE_GAP_MIN。
- 填写格式：非负整数秒；与 LINUXSB_SITE_GAP_MAX 组成随机区间，上限 600。

### `LINUXSB_SITE_GAP_MAX`

- 必填：否
- 敏感：否
- 获取或设置：需要拉开与其它任务执行间隔时自行设置；默认 0。兼容别名 SITE_GAP_MAX。
- 填写格式：非负整数秒；不小于 LINUXSB_SITE_GAP_MIN，上限 600。

### `LINUXSB_DRY_RUN`

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
- 填写格式：逗号、分号或空白分隔；可匹配 b60e5edc4107a20d、scripts/linuxsb_daily.py、文件名或通配符；* 全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：目录路径；失败后继续尝试 /ql/data/scripts 与 /ql/scripts；通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 Cookie；同一账号的 bbs_auth、bbs_csrf 等字段放在同一行。账号独立处理，任一账号签到失败则整体非零退出。

## 验证与兼容性

SHA-256 `e9c32b5b2daf8ccf8fadb1b5bcb139597ebce12e1880adc9baff2f150f793f03`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b60e5edc4107a20d`。

## 副作用与风险

- 正式执行时向 https://linux.sb/daily_checkin 提交签到，可能增加积分或连续签到天数
- 通知启用且适配器可用时向青龙通知渠道投递脱敏任务总结

## 许可证与来源

上游 `Eitan-S-23/NodeSeek-DeepFlood-LinuxSB-Checkin` / `linuxsb_daily.py` / `ad893f7a5885cac2dfd9bd67dfd6ab72414f8a70`。
