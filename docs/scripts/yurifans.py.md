# Yurifans 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/yurifans.py`
- 青龙命令：`python3 scripts/yurifans.py`
- 建议 Cron：`32 10 * * *`
- 发布哈希：`93af8640147cdd5117e746ff61365a36506dd9f8e29dcd05687703723e43109a`
- 许可证：`MIT`

## 脚本功能

- 邮箱密码登录并校验登录态，显示官方返回的非敏感账号名称
- 逐行多账号独立执行，兼容原邮箱与密码环境变量
- 复用手动取得的 WAF 通行 Cookie 与匹配的 User-Agent，可显式只读兼容旧缓存
- 查询每日签到状态、今日奖励与当前积分，已签到时跳过重复提交
- 执行每日签到并再次查询状态验证成功
- 完全断网预演、阶段耗时与账号及任务统计、单行 TASK_SUMMARY 汇总
- 遵循全局开关和选择器发送青龙脱敏通知，通知故障保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `YURIFANS_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 https://yuri.website 注册并取得本人邮箱与密码。遇到雷池验证时，在浏览器正常通过验证后，从开发者工具 Network 的本站请求头复制 Cookie 和 User-Agent，加入同一账号对象。严禁分享凭据。
- 填写格式：每个非空行一个 JSON 对象，必填 email、password，选填 cookie、user_agent，所有字段值为字符串。JSON 转义可保留密码中的分隔符。账号以换行分隔，不使用 & 或 @ 分隔账号。优先使用本变量。

### 可选参数

### `YURIFANS_EMAIL`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游邮箱变量，来自本人 Yurifans 账号；仅在未配置 YURIFANS_ACCOUNTS 时使用。
- 填写格式：每行一个邮箱，非空行与 YURIFANS_PASSWORD 一一对应。

### `YURIFANS_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游密码变量，来自本人 Yurifans 账号；仅在未配置 YURIFANS_ACCOUNTS 时使用。
- 填写格式：每行一个密码，非空行与 YURIFANS_EMAIL 一一对应。需要 Cookie 时建议迁移到统一账号变量。

### `YURIFANS_COOKIE_CACHE`

- 必填：否
- 敏感：是
- 获取或设置：可显式指定已有上游 Cookie 缓存供兼容读取。建议使用统一账号变量内的 cookie 和 user_agent。
- 填写格式：可选本地 JSON 路径，支持旧 Cookie 数组或含 cookies、user_agent 的对象。仅复用 sl- 前缀通行 Cookie，不读取登录 Cookie。默认不访问缓存，不写入、不删除。

### `YURIFANS_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：本地验证或青龙环境变量中设置。
- 填写格式：1、true、yes、on 开启完全断网预演，验证账号配置并模拟阶段，跳过外部通知投递。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙配置要接收通知的脚本选择器。
- 填写格式：逗号、分号或空白分隔，支持目录相对路径、文件名及通配符、目录编号 b1ca5d9bad50645c；* 选择全部；空字符串关闭全部默认选择。全局显式开关优先。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填入青龙通知模块所在目录。
- 填写格式：目录内含 notify.py 或 sendNotify.js；同时尝试可导入的 notify.send、脚本同目录、/ql/data/scripts、/ql/scripts。JavaScript 通知需要青龙已有 Node.js。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个独立账号 JSON 对象，同一账号的邮箱、密码与可选通行凭据放在同一对象。各账号独立会话和错误处理，任一账号失败整体非零退出。旧变量按非空行配对。

## 验证与兼容性

SHA-256 `93af8640147cdd5117e746ff61365a36506dd9f8e29dcd05687703723e43109a`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b1ca5d9bad50645c`。

## 副作用与风险

- 登录产生本站会话
- 每日签到并领取站点积分奖励
- 通知启用时通过青龙通知渠道发送脱敏结果

## 许可证与来源

上游 `jckling/Daily-Bonus` / `checkin/yurifans.py` / `79782fbeca62f1c9b514e0e13d0c94570a782a3a`。
