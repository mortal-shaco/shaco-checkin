# Fa米家每日签到与发米粒查询

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/ck_fmapp.py`
- 青龙命令：`python3 scripts/ck_fmapp.py`
- 建议 Cron：`57 1 * * *`
- 发布哈希：`5c7d1126eef3513dfe046073d0335f3401ad02e0961016d28ef56b47b1cd1fc6`
- 许可证：`MIT`

## 脚本功能

- 每日 App 签到并显示下一次及累计签到发米粒奖励信息
- 查询并原样显示官方返回的非敏感账号昵称
- 查询发米粒余额
- 每行一个 JSON 账号，保留上游四个凭据字段及三个可选请求头默认值
- 完全断网预演、分阶段脱敏日志、账号统计及单行 TASK_SUMMARY 结构化结果
- 正式运行调用青龙通知发送器发送脱敏任务总结，支持全局关闭
- 兼容 FMAPP_ACCOUNTS 旧变量和 blackBox、deviceId、fmVersion、userAgent 字段别名
- 支持 FMAPP_TIMEOUT 1 至 60 秒；原 FMAPP 默认 15 秒、旧 FMAPP_ACCOUNTS 默认 10 秒
- 旧 Fa米家脚本 ID 和文件名仍可选择青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `FMAPP`

- 必填：是
- 敏感：是
- 获取或设置：在自己的手机登录 Fa米家 App，使用本人授权的抓包工具查看 fmapp.chinafamilymart.com.cn 的 App 请求头。将 token、cookie、blackBox、deviceId 分别填入 token、cookie、blackbox、device_id；可从同一请求头获取 fmVersion、os、User-Agent，分别填入可选字段 fmversion、os、useragent。不要公开或分享抓包内容，登录失效后重新获取。
- 填写格式：每个非空行为一个 JSON 对象，必须包含非空字符串 token、cookie、blackbox、device_id。同一账号的全部凭据合并在该对象中；Cookie 中的分号、&、@ 等字符按 JSON 字符串原样保存，不用于账号分隔。可选字段 fmversion 默认 2.2.3、os 默认 ios、useragent 默认 Fa；字段值不可含换行。

### 可选参数

### `FMAPP_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：1 启用完全断网预演；默认 0 正式执行。预演校验账号配置和请求构造，不签到、不查询、不实际发送通知，不代表真实业务成功。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：使用自定义青龙通知模块目录时设置，通常无需配置。
- 填写格式：包含 notify.py 或 sendNotify.js 的本机目录；也会自动检查可导入的 notify 模块及 /ql/data/scripts、/ql/scripts。通知不可用不改变业务退出码。

### `FMAPP_ACCOUNTS`

- 必填：否
- 敏感：是
- 获取或设置：与 FMAPP 相同；旧 Fa米家任务已使用该变量时可直接沿用。
- 填写格式：每个非空行一个 JSON 账号对象；仅在 FMAPP 为空时读取；兼容 blackBox、deviceId、fmVersion、userAgent 字段别名。

### `FMAPP_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中按网络情况设置。
- 填写格式：1 至 60 秒；FMAPP 默认 15 秒，旧 FMAPP_ACCOUNTS 默认 10 秒。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认上架列表，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、scripts/相对路径、文件名或文件名通配符；* 表示全部，空值表示全部关闭。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行填写一个账号 JSON 对象；账号逐个独立执行，某个账号配置或业务失败不阻止后续账号，任一账号失败时整体非零退出。

## 验证与兼容性

SHA-256 `5c7d1126eef3513dfe046073d0335f3401ad02e0961016d28ef56b47b1cd1fc6`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b448219b57620cb7`。

## 副作用与风险

- 向 Fa米家提交每日签到，按服务端规则更新签到记录并发放发米粒

## 许可证与来源

上游 `OreosLab/checkinpanel` / `ck_fmapp.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。
