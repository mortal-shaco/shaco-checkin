# 量界智算签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/liangjie.py`
- 青龙命令：`python3 scripts/liangjie.py`
- 建议 Cron：`10 9 * * *`
- 发布哈希：`0f05fb80010535f1fe48b1ae3bbbf3bec87c13ac7515bb36a04d2abb35910696`
- 许可证：`MIT`

## 脚本功能

- 量界智算（liangjiewis.com）每日签到
- 签到前查询 /api/user/self 获取公开身份与 New-API-User
- 识别业务 success 与「已签到」文案
- 官方接口返回昵称、用户名或公开 UID 时直接展示以便核对账号
- 多账号按行处理；规范变量 LIANGJIE_COOKIE（可选用户ID|Cookie）
- 完全断网预演 LIANGJIE_DRY_RUN、HTTPS 超时、业务成功/已签到判定
- 脱敏时间轴日志、账号与任务统计、单行 TASK_SUMMARY 与青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `LIANGJIE_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：在浏览器登录 https://liangjiewis.com/ 后，打开开发者工具「网络」面板，找到个人中心或签到相关请求，完整复制 Cookie 请求头（通常含 session=…）。可选在同一行前置本人数字用户 ID，格式为「用户ID|Cookie」。不要把真实 Cookie 写入公开仓库、日志或通知。
- 填写格式：每行一个账号：Cookie 原文，或「数字用户ID|Cookie」（仅在第一个 | 处分割）；账号之间只用换行分隔，不使用 & 或 @

### 可选参数

### `LIANGJIE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线检查时设置；只校验配置并模拟查询/签到阶段，不访问网络、不改动签到状态、不真实发送通知。
- 填写格式：1、true、yes、on 开启完全断网预演；默认关闭

### `LIANGJIE_TIMEOUT`

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

每行一个 Cookie（可选「用户ID|Cookie」）；账号独立处理，任一账号失败时整体以非零退出码结束

## 验证与兼容性

SHA-256 `0f05fb80010535f1fe48b1ae3bbbf3bec87c13ac7515bb36a04d2abb35910696`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/62fd8997988ca1e4`。

## 副作用与风险

- 向量界智算签到接口提交每日签到，改变当日签到状态并可能发放站点奖励
- 通知已启用且适配器可用时向青龙通知通道发送脱敏任务统计

## 许可证与来源

上游 `MDLZCOOL/liangjie-auto-checkin` / `checkin.py` / `5a65be226e4b6e7a5a689c1256d759f151144c64`。
