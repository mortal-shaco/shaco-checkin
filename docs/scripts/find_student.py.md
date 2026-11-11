# 今日校园同学列表

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/find_student.py`
- 青龙命令：`python3 scripts/find_student.py`
- 建议 Cron：`59 10 * * *`
- 发布哈希：`3d2fa4714f784ec88b11122f7b9fa741111e82bdfdc16107a4cb868066cd8ccd`
- 许可证：`GPL-3.0-only`

## 脚本功能

- 通过固定 HTTPS 接口以 GET 查询今日校园同学列表，保留上游 limits=20、offset=0 默认分页参数
- 使用独立标准库 HTTP 实现，从同一账号 JSON 读取原 config.headers 和 config.cookies 对应内容
- 按换行处理多账号，业务成功字段和值需严格匹配，返回同学数组后才视为成功
- 仅显示返回对象中安全的昵称、用户名、显示名称及公开用户标识，不输出原始响应或凭据
- 支持完全断网参数预演、分阶段日志、每账号统计和唯一 TASK_SUMMARY 记录
- 按青龙通知订阅规则投递脱敏摘要；失败不覆盖业务退出码；预演只生成摘要并跳过外部投递

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `CPDAILY_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人授权登录今日校园后的网络请求中找到 https://www.cpdaily.com/v6/user/findStudent，复制该请求实际使用的 Cookie 和请求头。上游未提供 config 内容，本脚本不猜测学校特定认证字段。将配套凭据放在同一行 JSON 中；不得复制到日志或公开仓库。
- 填写格式：每个非空行一个 JSON 对象，包含 cookies 和 headers 字符串映射；至少提供非空 cookies，或 headers 内的 Cookie/Authorization。Cookie 只能配置一处，不配置 Host 等传输层字段。账号仅按换行分隔，字段值中的 &、@ 保持原值。

### `CPDAILY_RESPONSE_RULE`

- 必填：是
- 敏感：否
- 获取或设置：从该接口已知成功响应核对业务成功字段和值，以及同学对象数组路径。本次输入没有响应样本，不能假定成功码或数据层级。正式运行必须填写，预演可省略。可选 identityPath 指向当前账号身份对象。
- 填写格式：JSON 对象：successPath 为点号分隔对象字段路径，successValue 为精确成功值（字符串、整数或布尔值，类型也需相同），studentsPath 为同学数组路径；可选 identityPath 为当前账号身份对象路径。不要填入凭据或原始响应。

### 可选参数

### `CPDAILY_LIMITS`

- 必填：否
- 敏感：否
- 获取或设置：按单次查询数量需要设置，默认沿用上游的 20。
- 填写格式：1～1000 的整数

### `CPDAILY_OFFSET`

- 必填：否
- 敏感：否
- 获取或设置：按分页需要设置，默认沿用上游的 0；仅查询当前页，不自动遍历。
- 填写格式：0～2147483647 的整数

### `CPDAILY_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选请求超时秒数，默认 15。
- 填写格式：1～60 的整数

### `CPDAILY_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：验证参数时设置为 1；不请求接口、不执行外部通知组件。
- 填写格式：1/true/yes/on 开启，默认关闭

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：指定需要通知的脚本，设置后替换默认订阅；空值关闭全部。可填目录编号 9698197c18a7c2eb、文件名 find_student.py/candidate.py、对应 scripts/ 相对路径或通配符。
- 填写格式：逗号、分号或空白分隔；* 匹配全部

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选青龙通知组件目录；同时支持可导入的 notify，以及 /ql/data/scripts、/ql/scripts 下的 notify.py 或 sendNotify.js。未安装组件不影响业务退出码。
- 填写格式：包含 notify.py 或 sendNotify.js 的目录；脚本业务不依赖该目录

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON，将该账号配套 headers 和 cookies 放在同一对象；不使用 &、@ 分隔账号。各账号独立运行，任一失败整体非零退出。

## 验证与兼容性

SHA-256 `3d2fa4714f784ec88b11122f7b9fa741111e82bdfdc16107a4cb868066cd8ccd`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/9698197c18a7c2eb`。

## 副作用与风险

- 无额外已记录副作用。

## 许可证与来源

上游 `jerryshell/cpdaily-api` / `find_student.py` / `02a6360cfb6c2a79e5e019a19ee4e9324ed15648`。
