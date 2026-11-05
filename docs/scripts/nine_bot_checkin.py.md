# 九号出行每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/nine_bot_checkin.py`
- 青龙命令：`python3 scripts/nine_bot_checkin.py`
- 建议 Cron：`0 7 * * *`
- 发布哈希：`84dee357eef72e0ead3d6ad4d5c3597bc833ee8a1691f14f6a95709d5bd08f54`
- 许可证：`MIT`

## 脚本功能

- 使用 Authorization 令牌与 device_id 调用九号门户每日签到接口
- 区分签到成功与今日已签到，并在官方响应含非凭据公开身份时直接展示
- 合并同日签到里程碑盲盒列表查询与可领取盲盒领取（经验 / N币），可用开关关闭
- 支持每行一个账号的多账号独立处理，任一账号失败时非零退出
- 支持完全断网预演、请求超时、时间轴日志、脱敏通知与单行 TASK_SUMMARY

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `NINEBOT_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：从九号 App / H5 抓包取得门户接口请求头中的 Authorization（令牌）与 device_id。仅写入青龙环境变量，不要分享或提交到公开仓库。
- 填写格式：每个非空行一个账号：Authorization令牌|device_id；仅在第一个竖线处分割，后续凭据文本保留。空行和以 # 开头的注释行忽略。

### 可选参数

### `NINEBOT_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名；仅当未设置 NINEBOT_ACCOUNTS 时与 NINEBOT_DEVICE_ID 成对生效。推荐迁移到 NINEBOT_ACCOUNTS。
- 填写格式：九号门户接口 Authorization 请求头完整值

### `NINEBOT_DEVICE_ID`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名；仅当未设置 NINEBOT_ACCOUNTS 时与 NINEBOT_TOKEN 成对生效。推荐迁移到 NINEBOT_ACCOUNTS。
- 填写格式：九号门户接口 device_id / Device-Id 请求头值

### `NINEBOT_ENABLE_BLIND_BOX`

- 必填：否
- 敏感：否
- 获取或设置：控制签到后是否检查并领取可开启的签到里程碑盲盒；默认开启，与上游每日工作流一致。
- 填写格式：布尔值，默认 1；1、true、yes、on 开启；0、false、no、off 仅签到

### `NINEBOT_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置单次 HTTPS 请求超时；留空使用 30 秒。
- 填写格式：5 至 60 之间的秒数

### `NINEBOT_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要验证配置与执行路径但禁止联网时启用；预演不访问业务接口，也不声明真实签到或领取成功。
- 填写格式：布尔值，默认 0；1、true、yes、on 开启完全断网预演

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认名单，只为匹配的脚本开启通知。
- 填写格式：用逗号、分号、空白或换行分隔 catalog ID、相对路径、文件名或通配符；* 表示全部，空值表示全部关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选填写已有青龙 notify.py 或 sendNotify.js 所在目录；未填写时尝试导入 notify 和青龙标准脚本目录。
- 填写格式：已有通知模块所在目录路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

NINEBOT_ACCOUNTS 中每个非空行代表一个账号，格式为 Authorization令牌|device_id；仅在第一个竖线处分割。脚本逐账号独立处理，任一账号失败时进程非零退出。

## 验证与兼容性

SHA-256 `84dee357eef72e0ead3d6ad4d5c3597bc833ee8a1691f14f6a95709d5bd08f54`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8b80e03b90d5b3a1`。

## 副作用与风险

- 向九号账号写入每日签到记录
- 在开启盲盒功能时领取可开启的签到里程碑盲盒奖励（经验或 N币）
- 正式执行且通知开启时向青龙通知组件发送脱敏任务总结

## 许可证与来源

上游 `guopenglong/automation-scripts` / `ninebot/nine_bot_checkin.py` / `65931dcd9a3c37619b442bea4930df0dc44c57f2`。
