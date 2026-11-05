# VManAPI 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/check_in.py`
- 青龙命令：`python3 scripts/check_in.py`
- 建议 Cron：`23 8 * * *`
- 发布哈希：`777b9054095ae91633e46ff739d6ccfdbc5e55bf5e04deeb7113fd866df2456a`
- 许可证：`MIT`

## 脚本功能

- 使用 Authorization Token 调用 VManAPI 每日签到接口
- 请求头随机化（User-Agent、语言与 Chromium Client Hints）
- 支持逐行多账号轮询，账号间随机延迟
- 断网预演、时间轴日志、脱敏通知与 TASK_SUMMARY

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `VMAN_AUTHORIZATION`

- 必填：是
- 敏感：是
- 获取或设置：打开 https://donate.avman.ai 并登录；按 F12 打开开发者工具 → Network；手动执行一次签到，选中 check_in 请求，在 Request Headers 中复制 Authorization 字段的完整 token 值（不要包含 Authorization: 或 Bearer 前缀）。每个非空行填写一个账号的 token；可选 备注|token，仅在第一个竖线处分割。
- 填写格式：每行一个 JWT Token；可选 备注|token

### 可选参数

### `VMAN_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选；单次 HTTPS 请求超时秒数，不设置则默认 30。
- 填写格式：5 到 120 之间的数字秒数

### `VMAN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：设为 1/true/yes/on 启用完全断网预演；预演只校验配置，不发起网络请求。
- 填写格式：1/true/yes/on 或 0/false/no/off

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：当 QINGLONG_NOTIFY=auto 时，用 catalog-id、脚本路径、文件名或 glob 选择需要通知的脚本；空值表示全部禁用。
- 填写格式：逗号/分号/空白/换行分隔的选择器；* 表示全部

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选；自定义青龙 notify.py / sendNotify.js 所在目录。
- 填写格式：本地目录路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号的 Authorization Token；可用 备注|token，仅在第一个竖线处分割。任一账号失败则进程非零退出。

## 验证与兼容性

SHA-256 `777b9054095ae91633e46ff739d6ccfdbc5e55bf5e04deeb7113fd866df2456a`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/bb9220b13809926a`。

## 副作用与风险

- 向 VManAPI 账户提交每日签到，可能变更签到状态或积分余额

## 许可证与来源

上游 `Jasonliu-0/VManAPI-check_in` / `check_in.py` / `e14fca9799a21f4756723135f3f2593b0fc1d712`。
