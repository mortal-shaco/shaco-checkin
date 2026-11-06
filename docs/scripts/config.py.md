# 魅魔AI每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/config.py`
- 青龙命令：`python3 scripts/config.py`
- 建议 Cron：`26 9 * * *`
- 发布哈希：`7c89109085dcf5ae483cc885c0b83866e21a9eec9977162051fa76cc9a76d340`
- 许可证：`MIT`

## 脚本功能

- 连接魅魔 AI / Meimoai 站点并完成邮箱密码登录，或使用 Cookie 跳过登录
- 查询用户信息并展示昵称与电量等非凭据身份信息
- 调用每日签到接口，核验业务成功或今日已签，并尽量对比签到前后电量
- 多账号逐行配置、独立执行及任一失败非零退出
- 完全断网预演、编号阶段与耗时、账号及子任务统计、单行 TASK_SUMMARY
- 按青龙通知策略发送脱敏汇总，通知不可用不改变业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `MEIMODU_ACCOUNT`

- 必填：是
- 敏感：是
- 获取或设置：打开魅魔 AI（Meimodu / Meimoai，默认 https://www.sexyai.ai/ ）注册并登录。方式一：浏览器开发者工具复制发往该站点的完整 Cookie，按 cookie:完整Cookie 写入；方式二：使用网站注册邮箱与密码，按 邮箱#密码 写入。不要把凭据发给他人或写入公开仓库、日志、通知。
- 填写格式：每个非空行一个账号。支持：邮箱#密码；cookie:完整Cookie；邮箱#密码#cookie:完整Cookie；或直接粘贴 Cookie 字符串。账号之间只用换行分隔，不使用 &、@ 或 &&。仅在第一个 # 处分割邮箱与后续字段。

### 可选参数

### `EMAIL`

- 必填：否
- 敏感：是
- 获取或设置：上游兼容别名；未设置 MEIMODU_ACCOUNT 时，可与 PASSWORD 组成单账号登录。优先使用规范变量 MEIMODU_ACCOUNT。
- 填写格式：单个账号邮箱；需同时提供 PASSWORD。

### `PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：上游兼容别名；未设置 MEIMODU_ACCOUNT 时，可与 EMAIL 组成单账号登录。优先使用规范变量 MEIMODU_ACCOUNT。
- 填写格式：单个账号密码；需同时提供 EMAIL。

### `COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：上游兼容别名；未设置 MEIMODU_ACCOUNT 时可读此变量作为单账号 Cookie。优先使用规范变量 MEIMODU_ACCOUNT。
- 填写格式：单个账号的浏览器 Cookie 字符串。

### `MEIMODU_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容别名；未设置 MEIMODU_ACCOUNT 与 COOKIE 时可读此变量。优先使用规范变量 MEIMODU_ACCOUNT。
- 填写格式：单个账号的浏览器 Cookie 字符串。

### `MEIMODU_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：站点域名变更时可覆盖默认长期地址；亦兼容上游 TARGET_URL。
- 填写格式：以 http:// 或 https:// 开头的站点根地址；默认 https://www.sexyai.ai/。

### `TARGET_URL`

- 必填：否
- 敏感：否
- 获取或设置：上游兼容别名；未设置 MEIMODU_BASE_URL 时可读此变量。
- 填写格式：与 MEIMODU_BASE_URL 相同。

### `MEIMODU_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况调整单次 HTTP 超时秒数。
- 填写格式：5 至 90 的整数秒；默认 15。

### `MEIMODU_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要验证配置与执行路径但禁止联网时启用。
- 填写格式：设为 1、true、yes 或 on 时启用完全断网预演。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、scripts/相对路径、文件名或通配符；* 表示全部，空值表示全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定本地青龙 notify.py 所在目录；也支持导入 notify.send 和青龙标准目录。
- 填写格式：已存在的本地通知组件目录，不会下载或安装组件。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

MEIMODU_ACCOUNT 每个非空行一个账号。支持邮箱#密码、cookie:Cookie 或原始 Cookie；同一账号配套凭据写在同一行。账号逐个独立连接、登录、查询与签到；任一账号失败则整体非零退出。不使用 &、@ 或 && 分隔账号。

## 验证与兼容性

SHA-256 `7c89109085dcf5ae483cc885c0b83866e21a9eec9977162051fa76cc9a76d340`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/03d0e66b5d71fba8`。

## 副作用与风险

- 正式运行时向魅魔 AI 提交每日签到，可能增加账号电量/余额并改变当日签到状态
- 正式运行使用邮箱密码时会登录并更新会话 Authorization
- 启用通知且匹配策略时，通过青龙 notify 发送脱敏账号统计

## 许可证与来源

上游 `KingPlustar/Meimodu-auto-signin` / `config.py` / `d091efc1137e1981d9c96ba116d59cbf941f3625`。
