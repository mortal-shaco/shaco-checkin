# 奥波莱大学Moodle作业监控

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_6bed5fef.py`
- 青龙命令：`python3 scripts/task_6bed5fef.py`
- 建议 Cron：`*/5 * * * *`
- 发布哈希：`80d2c8390b6ae5be406d6bd5f5d26d04475a78890bf9c75472b576e7bf14f9d8`
- 许可证：`GPL-3.0-only`

## 脚本功能

- 使用 Moodle 用户名密码登录指定站点
- 读取课程页作业（assign）活动列表
- 与本地缓存比对检测作业新增或移除
- 展示课程名称与公开身份（若页面返回）
- 多账号逐行独立处理与失败汇总
- 完全断网预演、时间轴日志与单行 TASK_SUMMARY
- 青龙脱敏通知及全局通知开关

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `UO_MOODLE_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：使用奥波莱大学数学 Moodle（默认 moodle.math.uni.opole.pl）的学号/用户名与密码，并在课程页地址中确认 course id（view.php?id=数字）。在青龙环境变量中按行配置，切勿写入公开仓库或日志。
- 填写格式：每个非空行一个账号，格式 username|password|course_id；先按最后一个 | 取出课程 ID，再按第一个 | 分割用户名与密码，密码中后续 | 原样保留；支持空行与 # 开头注释；不要用 & 或 @ 分隔账号

### 可选参数

### `UO_MOODLE_USERNAME`

- 必填：否
- 敏感：否
- 获取或设置：兼容上游单账号别名；仅当 UO_MOODLE_ACCOUNTS 为空时与密码、课程 ID 成对使用
- 填写格式：Moodle 登录用户名

### `UO_MOODLE_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游单账号别名；仅当 UO_MOODLE_ACCOUNTS 为空时使用，填写 Moodle 登录密码
- 填写格式：Moodle 登录密码明文，勿写入公开位置

### `UO_MOODLE_COURSE_ID`

- 必填：否
- 敏感：否
- 获取或设置：兼容上游单账号别名；仅当 UO_MOODLE_ACCOUNTS 为空时使用，从课程页 URL 的 id 参数获取
- 填写格式：正整数字符串，例如 123

### `UO_MOODLE_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：仅当 Moodle 根地址与默认站点不同时覆盖
- 填写格式：https:// 开头的 Moodle 根地址，默认 https://moodle.math.uni.opole.pl

### `UO_MOODLE_STATE_DIR`

- 必填：否
- 敏感：否
- 获取或设置：需要持久化作业 ID 缓存到指定目录时设置；青龙容器建议指向可写数据目录
- 填写格式：本地目录路径；默认脚本旁 uo_moodle_state

### `UO_MOODLE_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：自定义单次 HTTPS 请求超时秒数
- 填写格式：5 到 60 的数字秒，默认 20

### `UO_MOODLE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要完全断网预演、只校验配置时手动设置为 1
- 填写格式：1/true/yes/on 启用预演；默认实际执行

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要按脚本白名单启用通知时设置；空值表示全部禁用
- 填写格式：catalog-id、脚本路径、文件名或 glob，可用逗号/分号/空白/换行分隔；* 表示全部

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：仅当青龙通知脚本不在默认路径时，设为 notify.py 或 sendNotify.js 所在目录
- 填写格式：本地目录绝对路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

UO_MOODLE_ACCOUNTS 中每个非空行是一个独立账号，格式 username|password|course_id；先取末段课程 ID，再按第一个 | 分割用户名与密码；逐账号登录并检查对应课程，任一账号失败时进程整体非零退出

## 验证与兼容性

SHA-256 `80d2c8390b6ae5be406d6bd5f5d26d04475a78890bf9c75472b576e7bf14f9d8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/6bed5fef3c9bac1c`。

## 副作用与风险

- 实际执行时登录 Moodle 并创建会话 Cookie
- 作业列表相对缓存发生变化或首次运行时写入本地作业 ID 状态文件
- 启用青龙通知时会向已配置渠道发送脱敏任务汇总

## 许可证与来源

上游 `gitlab.com/Anav0/uo-moodle-notifier` / `main.py` / `d5fd430e7515f13157eb034ee7ea097439fb7dd9`。
