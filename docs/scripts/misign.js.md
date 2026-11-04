# Discuz k_misign 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/misign.js`
- 青龙命令：`node scripts/misign.js`
- 建议 Cron：`19 8 * * *`
- 发布哈希：`67444d183c3cb2a4658d8be0c83afabf3f4d9e4ab90cf694e1521ac56e171737`
- 许可证：`MIT`

## 脚本功能

- 按论坛根地址打开 k_misign 签到页并识别今日已签到（您的签到排名）
- 提取 JD_sign 或 k_misign 签到链接并执行签到，再回读确认页验证成功
- 读取确认页 lxreward 奖励文案（若存在）并写入结果说明
- 支持每行一个「论坛地址|Cookie」账号，独立汇总结果
- 展示页面中可解析的非敏感 Discuz 用户名，隐藏 Cookie 与原始响应
- 完全断网预演、超时与响应大小限制、时间轴日志与单行 TASK_SUMMARY
- 按青龙通知策略发送脱敏汇总，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `MISIGN_ACCOUNT`

- 必填：是
- 敏感：是
- 获取或设置：确认目标论坛使用 k_misign 签到插件（签到页形如 plugin.php?id=k_misign:sign）。在浏览器登录该论坛后，打开开发者工具网络面板，选择发往本站的已登录请求，复制请求头 Cookie 的完整值；论坛根地址填写首页 URL。Cookie 失效后重新登录再复制。不要将凭据发给他人。
- 填写格式：每个非空行一个账号，写成「论坛根地址|完整 Cookie」，仅在首个竖线处拆分，后续 Cookie 原文保留。Cookie 内分号与等号原样保留，不使用 & 或 @ 分隔账号。

### 可选参数

### `MISIGN_USER_AGENT`

- 必填：否
- 敏感：否
- 获取或设置：可选；建议与抓取 Cookie 时的浏览器一致。不填则使用脚本内置桌面 Chrome UA。
- 填写格式：完整 User-Agent 字符串；不得包含 Cookie 或 Token。

### `MISIGN_DRY_RUN`

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
- 填写格式：逗号、分号或空白分隔；可匹配 catalogId、scripts/misign.js、misign.js、candidate.js、当前文件名或通配符；* 全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：目录路径；失败后继续尝试 /ql/data/scripts 与 /ql/scripts；通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，格式为论坛根地址|Cookie，仅拆首个竖线。账号独立执行，任一失败或配置错误则整体非零退出。

## 验证与兼容性

SHA-256 `67444d183c3cb2a4658d8be0c83afabf3f4d9e4ab90cf694e1521ac56e171737`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/a4947a6ba0940e49`。

## 副作用与风险

- 正式执行时向目标 Discuz 论坛提交 k_misign 每日签到，改变账号当日签到状态并可能发放积分或插件奖励
- 通知启用且非预演时向青龙通知渠道投递脱敏任务总结

## 许可证与来源

上游 `lwhx/daily-checkin-panel` / `src/sites/misign.js` / `1ff7daeefbdfa2d444ab5bad989e4ad0ad4d9db5`。
