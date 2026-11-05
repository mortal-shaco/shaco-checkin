# 小米VIP会员签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/xiaomi_sign.py`
- 青龙命令：`python3 scripts/xiaomi_sign.py`
- 建议 Cron：`29 8 * * *`
- 发布哈希：`a35ecfcfc722584a7376bf8ee311448a5eb32b8c6ea35670d21d37d8c852a178`
- 许可证：`MIT`

## 脚本功能

- 调用小米 VIP 会员 checkinV2 接口完成每日签到
- 从 Cookie 提取 miui_vip_ph，并结合用户提供的签到表单 token 提交
- 支持逐行多账号，账号间短暂间隔
- 展示官方返回的公开身份或 Cookie 中的公开 userId 以便核对
- 断网预演、时间轴日志、脱敏通知与 TASK_SUMMARY

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `XIAOMI_VIP_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：在自己的设备打开小米 VIP 会员中心（web.vip.miui.com 或 VIP 账号 App），登录后用抓包工具拦截签到请求 api.vip.miui.com/mtop/planet/vip/user/checkinV2：从请求头复制完整 Cookie（须含 miui_vip_ph），并从请求体复制 token 字段。每个非空行填写 cookie|token，仅在第一个竖线处分割。失效后重新登录并抓取。勿使用他人公开样例凭据。
- 填写格式：每行 cookie|token；Cookie 内分号键值对原样保留

### 可选参数

### `MIUI_VIP_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容别名；仅当 XIAOMI_VIP_COOKIE 未设置有效内容时生效，格式与规范变量相同。
- 填写格式：每行 cookie|token

### `XIAOMI_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容别名；仅当规范变量与 MIUI_VIP_COOKIE 均未提供有效内容时生效。
- 填写格式：每行 cookie|token

### `XIAOMI_VIP_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选；单次 HTTPS 请求超时秒数，不设置则默认 20。
- 填写格式：5 到 120 之间的数字秒数

### `XIAOMI_VIP_DRY_RUN`

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

每个非空行一个账号，格式为 cookie|token；仅在第一个竖线处分割。任一账号失败则进程非零退出。

## 验证与兼容性

SHA-256 `a35ecfcfc722584a7376bf8ee311448a5eb32b8c6ea35670d21d37d8c852a178`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/201d530a0f4973ba`。

## 副作用与风险

- 向小米 VIP 会员账户提交每日签到，可能变更签到状态或会员积分

## 许可证与来源

上游 `James081105/xiaomiautosign` / `xiaomi_sign.py` / `708955c2b40503ee7b38c1d8a1ba0e0690502866`。
