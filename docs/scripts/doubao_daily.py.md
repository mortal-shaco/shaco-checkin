# 豆包天天领额度签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/doubao_daily.py`
- 青龙命令：`python3 scripts/doubao_daily.py`
- 建议 Cron：`23 9 * * *`
- 发布哈希：`f808884a85ddaeaa8b357331407a3964653e457e8a1bdbc9efd140da6336e0fe`
- 许可证：`MIT`

## 脚本功能

- 豆包「天天领额度」可配置接口每日签到
- 成功/已签到/鉴权失败/风控关键词与可选 JSON 路径成功判定
- 响应额度数字提取与公开账号身份展示
- 多账号换行配置、超时重试与完全断网预演
- 时间轴日志、TASK_SUMMARY 与青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `DOUBAO_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录豆包官网或 App 后，打开开发者工具复制请求 Cookie。多账号仅用换行分隔，每行一个完整 Cookie；禁止用 &、@ 分账号。
- 填写格式：每行：name1=value1; name2=value2; ...

### `DOUBAO_CHECKIN_URL`

- 必填：是
- 敏感：否
- 获取或设置：在豆包「天天领额度」签到时抓包，复制完整签到接口 URL（须含 http/https）。各账号共用同一接口地址。
- 填写格式：https://...

### 可选参数

### `COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容别名。仅当 DOUBAO_COOKIE 为空时生效，格式相同。
- 填写格式：每行一个完整 Cookie

### `CHECKIN_URL`

- 必填：否
- 敏感：否
- 获取或设置：可选兼容别名。仅当 DOUBAO_CHECKIN_URL 为空时生效。
- 填写格式：https://...

### `DOUBAO_CHECKIN_METHOD`

- 必填：否
- 敏感：否
- 获取或设置：可选。签到请求方法，默认 POST。
- 填写格式：GET|POST|PUT

### `DOUBAO_CHECKIN_BODY`

- 必填：否
- 敏感：否
- 获取或设置：可选。抓包得到的 JSON 请求体字符串；留空则不发送 body。
- 填写格式：合法 JSON 对象字符串

### `DOUBAO_EXTRA_HEADERS`

- 必填：否
- 敏感：否
- 获取或设置：可选。额外请求头 JSON 对象，会与默认头合并；Cookie 仍以账号行为准。
- 填写格式：{"Header-Name":"value"}

### `DOUBAO_USER_AGENT`

- 必填：否
- 敏感：否
- 获取或设置：可选。自定义 User-Agent；缺省使用内置桌面 Chrome UA。
- 填写格式：UA 字符串

### `DOUBAO_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：单次 HTTP 超时秒数，默认 20。
- 填写格式：数字 3~120

### `DOUBAO_RETRY`

- 必填：否
- 敏感：否
- 获取或设置：失败重试次数，默认 3。
- 填写格式：正整数

### `DOUBAO_RETRY_BACKOFF`

- 必填：否
- 敏感：否
- 获取或设置：重试退避基数秒，默认 3。
- 填写格式：数字 0~60

### `DOUBAO_SUCCESS_KEYWORDS`

- 必填：否
- 敏感：否
- 获取或设置：可选。逗号分隔成功关键词；缺省含签到成功/领取成功等。
- 填写格式：关键词1,关键词2

### `DOUBAO_ALREADY_KEYWORDS`

- 必填：否
- 敏感：否
- 获取或设置：可选。逗号分隔已签到关键词。
- 填写格式：关键词1,关键词2

### `DOUBAO_AUTH_KEYWORDS`

- 必填：否
- 敏感：否
- 获取或设置：可选。逗号分隔鉴权失败关键词。
- 填写格式：关键词1,关键词2

### `DOUBAO_RISK_KEYWORDS`

- 必填：否
- 敏感：否
- 获取或设置：可选。逗号分隔风控关键词。
- 填写格式：关键词1,关键词2

### `DOUBAO_SUCCESS_JSON_PATH`

- 必填：否
- 敏感：否
- 获取或设置：可选。逗号分隔 JSON 路径成功规则，格式 path=value，例如 data.code=0。
- 填写格式：path=value,path2=value2

### `DOUBAO_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：设为 1/true/yes/on 开启完全断网预演，不发起业务请求。
- 填写格式：1/true/yes/on

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：限定通知脚本列表；空值关闭全部；* 匹配全部。可选 catalog-id、相对路径、文件名或 glob。
- 填写格式：逗号/分号/空白/换行分隔的选择器

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：自定义 notify.py / sendNotify.js 所在目录。
- 填写格式：绝对路径目录

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

DOUBAO_COOKIE 按换行分隔，每个非空行一个账号 Cookie；兼容别名 COOKIE 仅在 DOUBAO_COOKIE 为空时生效。签到 URL 与请求参数各账号共用。任一账号失败则进程非零退出。

## 验证与兼容性

SHA-256 `f808884a85ddaeaa8b357331407a3964653e457e8a1bdbc9efd140da6336e0fe`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4ac225148a2befcd`。

## 副作用与风险

- 向用户配置的豆包签到接口提交签到/领额度请求，可能写入当日签到状态并发放活动额度

## 许可证与来源

上游 `meliissy/doubao-daily-checkin` / `main.py` / `cb28058d325e2bf355860bf09d984f83862bb4e4`。
