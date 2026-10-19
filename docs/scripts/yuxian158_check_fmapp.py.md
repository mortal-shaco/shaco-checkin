# Fa米家每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/yuxian158_check_fmapp.py`
- 青龙命令：`python3 scripts/yuxian158_check_fmapp.py`
- 建议 Cron：`52 0 * * *`
- 发布哈希：`63c7b194e7ac1404a4652498e7977b9640e6f062a6498af10881f0f73153dcf1`
- 许可证：`MIT`

## 脚本功能

- 使用 Fa米家官方接口执行每日签到，并显示接口返回的签到奖励进度。
- 查询并显示官方返回的账号昵称，便于核对执行账号。
- 查询并显示当前发米粒余额。
- 支持按行配置多个账号，逐账号独立执行并汇总成败。
- 支持完全不访问 Fa米家业务接口的断网预演模式。
- 输出带时间戳的阶段日志、账号统计、任务统计和单行 TASK_SUMMARY JSON。
- 按青龙通知开关和脚本选择器发送不含凭据与原始响应的任务摘要。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `FMAPP_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录 Fa米家 App 后，在本人设备上抓取 fmapp.chinafamilymart.com.cn 接口请求头中的 token、Cookie、blackBox 和 deviceId；只保存自己的账号信息，不要在日志或聊天中粘贴这些值。
- 填写格式：每个非空行一个 JSON 对象，必填字段为 token、cookie、blackbox、device_id；兼容 blackBox、deviceId、fmVersion、userAgent 字段名。示例只应使用占位值：{"token":"<TOKEN>","cookie":"<COOKIE>","blackbox":"<BLACKBOX>","device_id":"<DEVICE_ID>"}

### 可选参数

### `FMAPP_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置单次接口超时秒数；不设置时使用 10 秒。
- 填写格式：1 至 60 的数字

### `FMAPP_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要仅检查参数且完全不访问 Fa米家接口时设为 1。
- 填写格式：1、true、yes 或 on 表示启用

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要只为指定脚本发送通知时设置选择器；可使用目录中的发布路径、文件名或目录通配符。
- 填写格式：以逗号、分号、空白或换行分隔；支持 4bf795804a91086f、scripts/famijia_daily.py、famijia_daily.py 或 *

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

FMAPP_ACCOUNTS 每个非空行表示一个账号，行内使用一个 JSON 对象组合该账号的全部配套凭据；各账号独立执行，任一账号配置或任务失败都会使进程以非零状态退出。

## 验证与兼容性

SHA-256 `63c7b194e7ac1404a4652498e7977b9640e6f062a6498af10881f0f73153dcf1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4bf795804a91086f`。

## 副作用与风险

- 调用签到接口会完成当日签到，并可能增加发米粒或推进连续签到进度。

## 许可证与来源

上游 `yuxian158/check` / `dailycheckin_scripts/ck_fmapp.py` / `723c834f121ff4eef2dec7afe521071a7efff1a9`。
