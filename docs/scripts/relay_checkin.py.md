# Relay 中转站每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/relay_checkin.py`
- 青龙命令：`python3 scripts/relay_checkin.py`
- 建议 Cron：`38 9 * * *`
- 发布哈希：`7a6c20ebfd6603c97bfb773cf90720e5f6862ed7b3b94ef256007e44630e8b9c`
- 许可证：`MIT`

## 脚本功能

- 多站点每日签到，兼容原 JSON 配置、--config、重复 --site 筛选及 --list 列表
- 独立实现 HTTPS POST，保留 Authorization、New-Api-User 请求头及空 JSON 请求体
- 明确检查业务成功，识别可配置的重复签到提示并输出 quota_awarded 奖励
- 逐行多账号及旧凭据变量兼容，逐账号独立执行并汇总失败退出码
- 支持 --timeout、--version、--help、--dry-run 及环境变量断网预演
- 显示官方返回的非敏感昵称、用户名、显示名称或公开用户编号
- 时间戳分阶段日志、账号与任务统计及单行 TASK_SUMMARY 结构化汇总
- 按青龙开关和脚本选择发送脱敏总结；预演模拟通知且不联网

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `RELAY_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：从本人登录后的浏览器网络面板中找到签到请求，获取同账号的 Authorization 完整值和 New-Api-User 数字编号；不是模型调用密钥。
- 填写格式：每个非空行一个账号：站点标识:数字用户编号|Authorization；仅在首个竖线处分割令牌，保留后续文本及 Bearer 前缀。站点标识对应配置 id，简易配置为 example；不用 & 或 @ 分隔账号。

### 可选参数

### `RELAY_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：从本人支持 New API 签到的站点地址栏获取；与 RELAY_SITES_JSON 或 --config 三选一。
- 填写格式：无凭据、查询串或片段的 HTTPS 地址；生成 example 站点，签到路径 /api/user/checkin；不预设真实站点。

### `RELAY_SITES_JSON`

- 必填：否
- 敏感：否
- 获取或设置：根据本人签到请求确认站点地址和路径。可替代原 sites.json；优先顺序为 --config、本变量、脚本旁 sites.json、RELAY_BASE_URL。
- 填写格式：JSON 对象含 sites 非空数组。每站必填字符串 id、name、homepage、base_url、checkin_path、access_token_env、user_id_env；可选 already_checked_in_messages 字符串数组。地址必须 HTTPS、路径必须站内绝对路径；凭据不放入 JSON。

### `EXAMPLE_ACCESS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：旧版 example 站点兼容输入：从本人签到请求的 Authorization 请求头获取完整值。优先使用规范变量 RELAY_ACCOUNTS。
- 填写格式：单账号令牌；RELAY_ACCOUNTS 未设置时与 EXAMPLE_USER_ID 配套使用。自定义旧站点按 access_token_env 指定的变量读取。

### `EXAMPLE_USER_ID`

- 必填：否
- 敏感：是
- 获取或设置：旧版 example 站点兼容输入：从同账号签到请求的 New-Api-User 请求头获取。
- 填写格式：单个数字用户编号；自定义旧站点按 user_id_env 指定的变量读取。

### `RELAY_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：预演时设为 1；也支持 --dry-run，任一启用即预演。
- 填写格式：1、true、yes、on 启用；仅验证配置，不请求签到和通知服务。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：填写通知脚本选择，设置后替代默认选择。
- 填写格式：逗号、分号、空白或换行分隔；支持 b3357f7fc6526506、relay_checkin.py、candidate.py、scripts/relay_checkin.py 及文件名通配符；* 全选，空值全关。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选填写青龙已有通知模块的目录；不自动安装。
- 填写格式：目录内含 notify.py 或 sendNotify.js；另支持导入 notify.send 及 /ql/data/scripts、/ql/scripts 标准目录。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

RELAY_ACCOUNTS 每个非空行一个账号，格式为站点标识:数字用户编号|Authorization；仅在首个竖线处分割。各账号独立执行，任一失败则整体非零退出；--site 筛选站点。兼容旧版每站一组凭据变量。

## 验证与兼容性

SHA-256 `7a6c20ebfd6603c97bfb773cf90720e5f6862ed7b3b94ef256007e44630e8b9c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b3357f7fc6526506`。

## 副作用与风险

- 正式运行向配置站点提交签到，可能改变签到记录和账户奖励额度
- 通知启用且选中时，通过青龙已有通知模块发送脱敏任务总结

## 许可证与来源

上游 `sstxww/relay-checkin` / `relay_checkin.py` / `51aa0d47ee6f3e768d19270eba5f1738abf85bf3`。
