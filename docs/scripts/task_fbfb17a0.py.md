# 起点阅读 App 签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_fbfb17a0.py`
- 青龙命令：`python3 scripts/task_fbfb17a0.py`
- 建议 Cron：`4 1 * * *`
- 发布哈希：`18a4890bfc67b3a48b312d654298a4abb54ecd0d958cd3e3d3dc37ec74a767ea`
- 许可证：`MIT`

## 脚本功能

- 使用抓包 Cookie 与 QDSign 材料，按上游 DES3 算法本地重算 QDSign 后请求起点 App 签到接口
- 识别业务 Result=0 为签到成功，并将常见「已签到」类文案视为今日已完成
- 官方响应若含昵称、用户名或公开 UID 则直接展示以便核对账号
- 支持每行一个账号的多账号独立处理，任一账号失败时非零退出
- 支持完全断网预演、请求超时、时间轴日志、脱敏青龙通知与单行 TASK_SUMMARY

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `QIDIAN_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在安卓抓包起点阅读 App 访问 druidv6.if.qidian.com/argus/api/v2/ 的任意请求，复制同一次请求的 Cookie 与 QDSign（Base64）。仅写入青龙环境变量，不要公开或提交到仓库。
- 填写格式：每个非空行一个账号：QDSign|Cookie。仅在第一个竖线处分割，首段为 QDSign，其余整段为 Cookie（Cookie 可含竖线）；不要用 & 或 @ 分隔账号；以 # 开头的行为注释。

### 可选参数

### `QIDIAN_QDSIGN`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名：当未设置 QIDIAN_ACCOUNTS 时，与 QIDIAN_COOKIE 成对使用；取值来源同 QDSign 抓包说明。
- 填写格式：单行 Base64 QDSign；须与 QIDIAN_COOKIE 同时配置

### `QIDIAN_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号别名：当未设置 QIDIAN_ACCOUNTS 时，与 QIDIAN_QDSIGN 成对使用；取值来源同 Cookie 抓包说明。
- 填写格式：单行 Cookie 原文；须与 QIDIAN_QDSIGN 同时配置

### `QIDIAN_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置单次 HTTPS 请求超时；留空使用 20 秒。
- 填写格式：5 至 90 之间的秒数

### `QIDIAN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要验证配置与执行路径但禁止联网时启用；预演不访问业务接口。
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

QIDIAN_ACCOUNTS 中每个非空行代表一个账号，格式为 QDSign|Cookie；脚本逐账号独立处理，任一账号失败时进程非零退出。

## 验证与兼容性

SHA-256 `18a4890bfc67b3a48b312d654298a4abb54ecd0d958cd3e3d3dc37ec74a767ea`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/fbfb17a0c5ba2e60`。

## 副作用与风险

- 正式模式向起点阅读 App 签到接口提交每日签到，可能写入签到记录并领取签到奖励
- 正式执行且通知开启时向青龙通知组件发送脱敏任务总结

## 许可证与来源

上游 `BRSblackshoot/qd_autosign` / `某阅读软件app自动签到.py` / `006557e86f4095ff16ea5c96c59987864c907464`。
