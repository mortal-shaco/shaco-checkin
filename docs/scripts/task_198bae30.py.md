# 洛谷签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_198bae30.py`
- 青龙命令：`python3 scripts/task_198bae30.py`
- 建议 Cron：`0 10 * * *`
- 发布哈希：`da6816e01e72474e95b1bde278d6dab43284d8826a0127e87f7147042ddc18fd`
- 许可证：`GPL-3.0`

## 脚本功能

- 洛谷（www.luogu.com.cn）使用 Cookie __client_id 与 _uid 每日打卡
- 识别业务 code=200 打卡成功、code=201 今日已打卡
- 展示公开 UID 以便核对账号
- 多账号按行处理；规范变量 LUOGU_ACCOUNTS（__client_id|_uid），兼容 Cookie 文本行
- 完全断网预演 LUOGU_DRY_RUN、HTTPS 超时、业务成功/已打卡判定
- 脱敏时间轴日志、账号与任务统计、单行 TASK_SUMMARY 与青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `LUOGU_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在浏览器登录 https://www.luogu.com.cn/ 后，打开开发者工具 → Application/应用 → Cookie → https://www.luogu.com.cn，复制 __client_id 与 _uid。每个非空行填写一个账号。不要把真实凭据写入公开仓库、日志或通知。
- 填写格式：每行一个账号：__client_id|_uid（仅在第一个 | 处分割）；也可填写同时含 __client_id= 与 _uid= 的 Cookie 文本。账号之间只用换行分隔，不使用 & 或 @

### 可选参数

### `LUOGU_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线检查时设置；只校验配置并模拟打卡阶段，不访问网络、不改动签到状态。
- 填写格式：1、true、yes、on 开启完全断网预演；默认关闭

### `LUOGU_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选：单次 HTTPS 请求超时秒数。
- 填写格式：5 到 60 的数字；默认 15

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认名单，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、相对路径、文件名或通配符；* 表示全部，空值表示全部关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录；失败不改变业务退出码。
- 填写格式：目录路径；还会尝试 /ql/data/scripts 与 /ql/scripts

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每行一个「__client_id|_uid」；账号独立处理，任一账号失败时整体以非零退出码结束

## 验证与兼容性

SHA-256 `da6816e01e72474e95b1bde278d6dab43284d8826a0127e87f7147042ddc18fd`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/198bae30a009b250`。

## 副作用与风险

- 向洛谷打卡接口提交每日打卡，改变当日签到状态并可能累计连续签到
- 通知已启用且适配器可用时向青龙通知通道发送脱敏任务统计

## 许可证与来源

上游 `kierankihn/auto-checkin` / `main.py` / `03a84c7abf61d75d85e81e32d1002a72ff9a78a8`。
