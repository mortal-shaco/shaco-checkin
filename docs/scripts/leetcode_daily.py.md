# LeetCode 中文站每日一题自动打卡

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/leetcode_daily.py`
- 青龙命令：`python3 scripts/leetcode_daily.py`
- 建议 Cron：`30 0 * * *`
- 发布哈希：`ae2401b77ebd4b18c590479da66b88a81c9eb161a3f43eb58a3086506fbd1fc5`
- 许可证：`MIT`

## 脚本功能

- 查询 LeetCode 中文站今日每日一题（dailyQuestionRecords，回退 todayRecord）
- 检查当前账号当天是否已 AC 该题
- 未完成时抓取题解中合法 C++ 代码并自动提交，轮询判题直至 AC 或候选耗尽
- 可开启 LEETCODE_CHECK_ONLY 仅查询题目与完成状态、不提交
- 查询并展示公开用户名/昵称/UID，便于核对账号
- 支持每行一个账号，独立汇总成功、已完成与失败；兼容 LEETCODE_SESSION+csrftoken 单账号别名
- 完全断网预演、请求超时与响应大小限制、时间轴日志与单行 TASK_SUMMARY
- 按青龙通知策略发送脱敏汇总，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `LEETCODE_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录 https://leetcode.cn ，打开开发者工具 → Application/应用 → Cookies → https://leetcode.cn，复制 LEETCODE_SESSION，并建议同时复制 csrftoken。不要把 Cookie 发给他人或写入公开仓库。
- 填写格式：每个非空行一个账号。推荐 Cookie 片段：LEETCODE_SESSION=...; csrftoken=...。也支持「会话值#csrf值」，仅在第一个 # 处拆分。不使用 & 或 @ 分隔账号。

### 可选参数

### `LEETCODE_SESSION`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游单账号别名；仅当 LEETCODE_COOKIE 为空时生效。获取方式同 LEETCODE_COOKIE。
- 填写格式：LEETCODE_SESSION Cookie 值字符串。

### `LEETCODE_CSRFTOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游 csrftoken；仅当 LEETCODE_COOKIE 为空时与 LEETCODE_SESSION 一起生效。亦可使用环境变量 csrftoken。
- 填写格式：csrftoken Cookie 值字符串。

### `csrftoken`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游 config.json 字段名；仅当 LEETCODE_COOKIE 与 LEETCODE_CSRFTOKEN 皆空时与 LEETCODE_SESSION 一起生效。
- 填写格式：csrftoken Cookie 值字符串。

### `LEETCODE_LANG`

- 必填：否
- 敏感：否
- 获取或设置：按需设置提交语言；题解抓取仍针对含 class Solution 的 C++ 代码块。
- 填写格式：默认 cpp；建议保持 cpp。

### `LEETCODE_CHECK_ONLY`

- 必填：否
- 敏感：否
- 获取或设置：仅想查询今日题目与完成状态、不自动提交代码时自行开启。
- 填写格式：1/true/yes/on 仅检查；默认关闭并在未 AC 时自动提交。

### `LEETCODE_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况自行调整；不填使用默认 30 秒。
- 填写格式：整数秒，允许 5..120；默认 30。

### `LEETCODE_POLL_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按判题耗时自行调整；不填使用默认 60 秒。
- 填写格式：整数秒，允许 10..300；默认 60。

### `LEETCODE_DRY_RUN`

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
- 填写格式：逗号、分号或空白分隔；可匹配 catalogId、scripts/leetcode_daily.py、文件名或通配符；* 全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：目录路径；失败后继续尝试 /ql/data/scripts 与 /ql/scripts；通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；同一账号的 LEETCODE_SESSION 与 csrftoken 写在同一行。账号独立执行，任一失败或配置错误则整体非零退出。

## 验证与兼容性

SHA-256 `ae2401b77ebd4b18c590479da66b88a81c9eb161a3f43eb58a3086506fbd1fc5`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/afb968077b55cdf8`。

## 副作用与风险

- 正式执行且未开启仅检查模式、且今日尚未 AC 时，向 leetcode.cn 提交题解代码并产生提交记录，可能改变当日每日一题完成状态
- 通知启用且适配器可用时向青龙通知渠道投递脱敏任务总结

## 许可证与来源

上游 `JadenSailing/leetcode-check` / `leetcode_daily.py` / `0c16610c7e02079767df35b3ccac2b2e87ab40a4`。
