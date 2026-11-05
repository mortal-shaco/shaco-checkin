# 米游社游戏签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/miyoushe_sign.py`
- 青龙命令：`python3 scripts/miyoushe_sign.py`
- 建议 Cron：`11 8 * * *`
- 发布哈希：`99ff2aa0bb1d152dbfed37c2e37875c5d118a7bee9bffb103c88e00a49430eb1`
- 许可证：`MIT`

## 脚本功能

- 使用 Cookie 或 stoken 准备网页签到凭证（可自动刷新 cookie_token）
- 查询账号绑定的原神 / 崩坏:星穹铁道 / 绝区零角色
- 为已绑定角色执行游戏月卡签到并展示奖励
- 可选按 game_biz 过滤仅签指定游戏
- 返回角色昵称等公开身份便于核对账号
- 不做社区米游币签到（上游已说明第三方社区签到接口不可用）

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `MIYOUSHE_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：在本人设备本地运行同仓 miyoushe_qr_login.py，使用米游社 App 扫码登录后，将生成的 Cookie 整串复制到青龙环境变量；也可从浏览器登录 user.mihoyo.com / act.mihoyo.com 后导出含 account_id 与 cookie_token（或 cookie_token_v2 系列）的 Cookie。不要把 Cookie 提交到公开仓库。stoken 形态可自动刷新 cookie_token。
- 填写格式：每个非空行一个账号的完整 Cookie 字符串（字段用分号分隔）。支持 account_id+cookie_token、account_id+cookie_token_v2 或含 stoken 的扫码 Cookie；可把 device_id=... 写进同一行。仅按换行分隔账号，不使用 &、@ 或逗号分隔账号。# 开头行忽略。

### 可选参数

### `MIYOUSHE_DEVICE_ID`

- 必填：否
- 敏感：是
- 获取或设置：可选。扫码登录时绑定的设备 ID；Cookie 行内已含 device_id 时优先用 Cookie 内值。混用设备 ID 可能导致登录失效。兼容旧名 DEVICE_ID。
- 填写格式：字母数字字符串；未设置且 Cookie 也无 device_id 时由脚本临时生成（仅适合网页 cookie_token 形态）。

### `MIYOUSHE_ONLY`

- 必填：否
- 敏感：否
- 获取或设置：可选。只签指定游戏，避免未使用游戏的请求。
- 填写格式：game_biz 列表，逗号分隔：hk4e_cn（原神）、hkrpg_cn（崩坏:星穹铁道）、nap_cn（绝区零）。留空表示签全部已绑定角色。

### `MIYOUSHE_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选。单次 HTTP 超时秒数。
- 填写格式：3–120 之间的整数，默认 15。

### `MIYOUSHE_GAME_GAP`

- 必填：否
- 敏感：否
- 获取或设置：可选。同一账号多个游戏签到之间的间隔，降低触发风控概率。
- 填写格式：0–30 之间的整数秒，默认 3；断网预演不睡眠。

### `MIYOUSHE_ACCOUNT_GAP`

- 必填：否
- 敏感：否
- 获取或设置：可选。多账号之间的间隔。
- 填写格式：0–60 之间的整数秒，默认 2；断网预演不睡眠。

### `MIYOUSHE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线验证配置时设置为 1。
- 填写格式：1、true、yes、on 启用完全断网预演；0、false、no、off 或空值关闭。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙中将本任务加入通知名单；存在该变量时替换默认名单。
- 填写格式：逗号、分号或空白分隔；支持 132658a551b47b61、scripts/miyoushe_sign.py、miyoushe_sign.py、文件名通配符及 *；空值关闭全部名单通知。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，指定本人青龙 notify.py 或 sendNotify.js 所在目录；也自动查找青龙标准目录。
- 填写格式：目录路径；优先 Python 通知，兼容 JavaScript 通知。通知缺失、超时或失败保留业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 Cookie。同一账号的 stoken/cookie_token/device_id 等字段写在同一行，用分号连接；仅按换行分隔账号。账号独立处理，任一失败则进程非零退出。

## 验证与兼容性

SHA-256 `99ff2aa0bb1d152dbfed37c2e37875c5d118a7bee9bffb103c88e00a49430eb1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/132658a551b47b61`。

## 副作用与风险

- 提交原神每日签到领奖
- 提交崩坏:星穹铁道每日签到领奖
- 提交绝区零每日签到领奖
- 在使用 stoken 时向通行证接口换取新的 cookie_token（仅会话内使用，不写本地文件）

## 许可证与来源

上游 `zyhqwq/sign-myself` / `mihoyo/miyoushe_sign.py` / `35c8def73338135c4bf72ad10fd939d2dea541d7`。
