# WorkBuddy签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/workbuddy.py`
- 青龙命令：`python3 scripts/workbuddy.py`
- 建议 Cron：`45 1 * * *`
- 发布哈希：`9a5d4dbdf22758a828ec4a19aed4111aa6ff04374f2df0e39515eaceab1c7d57`
- 许可证：`MIT`

## 脚本功能

- 每日签到和今日状态查询；主状态接口失败时回退兼容接口，令牌失效不盲目回退。
- 展示每日积分、签到获得积分、连续签到天数及连签奖励标记。
- 识别官方确认的活动关闭或今日已签；签到失败后复查，确认已签则视为完成。
- 可选刷新令牌续期并重试一次，兼容企业、租户、域名及自定义浏览器请求头。
- 逐行 JSON 多账号和驼峰凭据字段兼容，保留每日 08:30 定时与启动错峰参数。
- 完全断网预演、逐阶段脱敏日志、账号与子任务统计、单行结构化汇总和青龙通知。
- 官方返回公开昵称、用户名、显示名称或公开 UID 时显示可核对身份；不打印凭据或原始响应。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `WORKBUDDY_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录官方 WorkBuddy／CodeBuddy CN 客户端，在本人授权的接口请求中取得 Authorization 的 Bearer 令牌。可选 refresh_token 来自本人可读取的官方登录态 auth.refreshToken；uid、enterprise_id、domain 分别对应 X-User-Id、X-Enterprise-Id、X-Domain。可手动将旧配置 workbuddy.accounts 的对象逐行复制到此变量。不自动解密登录态、不要求安装其他工具或读取私有仓库。加密字段不可直接填写，应重新登录并取得可用凭据。
- 填写格式：每个非空行一个 JSON 对象；access_token 为必填字符串，refresh_token、uid、enterprise_id、domain、user_agent 为同账号的可选字符串。兼容 accessToken、refreshToken、enterpriseId、userAgent。JSON 保留完整字段内容，不按 &、@ 或其他字符分割账号。

### 可选参数

### `WORKBUDDY_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：由用户设置，开启完全断网预演。
- 填写格式：1、true、yes、on 开启；默认 0。

### `WORKBUDDY_JITTER_MAX`

- 必填：否
- 敏感：否
- 获取或设置：沿用上游启动随机延迟参数，按需要设置。
- 填写格式：0～3600 的整数秒；默认 600，0 关闭。正式运行账号间保留 5～10 秒等待。

### `WORKBUDDY_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络环境设置单次 HTTP 超时。
- 填写格式：1～120 的整数秒；默认 30。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可指定本人青龙 notify.py 所在目录；也检查常用青龙脚本目录和可导入的 notify 模块。
- 填写格式：可选本机目录路径，仅用于通知，不用于业务 HTTP。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认上架列表，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、scripts/相对路径、文件名或文件名通配符；* 表示全部，空值表示全部关闭。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个独立账号 JSON 对象，配套凭据合并在同一行；逐账号独立运行，任一账号失败则进程非零退出。

## 验证与兼容性

SHA-256 `9a5d4dbdf22758a828ec4a19aed4111aa6ff04374f2df0e39515eaceab1c7d57`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/af0ae4c86279f8da`。

## 副作用与风险

- 每日签到及服务端积分、连签奖励状态变更。
- 配置刷新令牌且访问令牌过期时向服务端申请续期，仅在进程内更新凭据。
- 正式运行且通知启用时发送脱敏青龙任务总结。

## 许可证与来源

上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/workbuddy/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
