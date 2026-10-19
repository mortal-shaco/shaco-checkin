# Vortexa 免费主机检查与领取

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/vortexa_free_claim.js`
- 青龙命令：`node scripts/vortexa_free_claim.js`
- 建议 Cron：`1,11,21,31,41,51 * * * *`
- 发布哈希：`8c4f8f8b8853243dc2c8d4615fc898e0c1c3c1543d959ece49c67c8f91bc4e1e`
- 许可证：`MIT`

## 脚本功能

- 账号密码登录，邮箱或用户名字段自动识别与自定义登录字段；访问 Token、刷新 Cookie 登录；授权失效后按原方式重新登录一次。
- 检查已有免费主机，显示公开服务名称或 ID；官网返回昵称、用户名、显示名或公开 UID 时输出身份以核对账号，不输出邮箱登录凭据。
- 查询免费主机库存、领取资格，默认完成只读检查；已有免费主机时确认已完成。
- 独立产品列表模式，列出免费产品名称、slug、产品 ID、套餐 ID、名称、类型和价格。
- 按产品 ID、slug 或名称选择免费产品；支持指定套餐 ID，未配置时选择首个免费产品及免费套餐。
- 显式开启免费主机领取，提交后以官方已有主机状态核验成功；未知响应、付费套餐和选定产品缺失时失败闭合。
- 显式开启有限随机间隔库存轮询；保留原十分钟定时规则、间隔配置、登录重试和请求头配置。
- 每行一个账号，凭据隔离，逐账号执行，任意账号失败整体非零退出。
- 完全断网预演、完整时间轴日志、分阶段与账号统计、一条 TASK_SUMMARY JSON；青龙通知及全局开关。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `VORTEXA_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 https://www.vortexa.cloud 注册并登录。密码使用本人账号密码；Token 从开发者工具网络面板的 Authorization Bearer 或 /auth/login 响应 accessToken 获取；cookie 从官网 API 请求 Cookie 获取；refresh 使用 openbot_refresh Cookie 的值；fingerprint 从同一会话 x-fingerprint 请求头获取。不得公开这些凭据。建议使用此规范变量；未设置时兼容下列旧变量。
- 填写格式：每个非空行一个 JSON 对象，不使用任何符号分隔账号。支持 account/password、token、cookie、refresh；至少提供一组可用凭据。可选 fingerprint/userAgent 绑定同一账号；JSON 字符串保留密码中的分隔符。Cookie 仅填写请求头值，不包含 Cookie: 前缀；token 不含 Bearer 前缀。

### 可选参数

### `VORTEXA_LOGIN`

- 必填：否
- 敏感：是
- 获取或设置：官网注册时使用的账号和密码；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：旧格式每行 账号@密码；用户名在第一个 @ 分割，邮箱在完整邮箱后的 @ 分割，密码剩余内容完整保留。推荐规范 JSON。

### `VORTEXA_ACCOUNT_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：同 VORTEXA_LOGIN 的兼容别名；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：同 VORTEXA_LOGIN；两者同时设置时优先 VORTEXA_LOGIN。

### `VORTEXA_ACCOUNT`

- 必填：否
- 敏感：是
- 获取或设置：本人官网登录账号；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：每个非空行一个账号，配套 VORTEXA_PASSWORD，非空旧凭据变量行数必须相同。

### `VORTEXA_EMAIL`

- 必填：否
- 敏感：是
- 获取或设置：本人官网注册邮箱，VORTEXA_ACCOUNT 的兼容输入；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：每行一个邮箱，配套 VORTEXA_PASSWORD；优先级 ACCOUNT、EMAIL、USERNAME。

### `VORTEXA_USERNAME`

- 必填：否
- 敏感：是
- 获取或设置：本人官网注册用户名，VORTEXA_ACCOUNT 的兼容输入；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：每行一个用户名，配套 VORTEXA_PASSWORD。

### `VORTEXA_PASSWORD`

- 必填：否
- 敏感：是
- 获取或设置：本人官网账号密码；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：每个非空行一个密码，不能含换行；需要包含换行的凭据不支持。

### `VORTEXA_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：开发者工具中官网 API 请求 Authorization 的 Bearer 值，或登录响应 accessToken；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：每行一个访问 Token，不含 Bearer 前缀。

### `VORTEXA_ACCESS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：同 VORTEXA_TOKEN 的兼容别名；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：同 VORTEXA_TOKEN；优先使用 VORTEXA_TOKEN。

### `VORTEXA_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：开发者工具中官网 API 请求的 Cookie 值，包含 openbot_refresh 时可刷新访问凭据；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：每行一个账号完整 Cookie，不含请求头名称。

### `VORTEXA_REFRESH`

- 必填：否
- 敏感：是
- 获取或设置：浏览器官网会话 Cookie 中 openbot_refresh 的值；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：每行一个刷新凭据；仅未提供完整 Cookie 时组装为 openbot_refresh Cookie。

### `VORTEXA_FINGERPRINT`

- 必填：否
- 敏感：是
- 获取或设置：同一登录会话的 x-fingerprint 请求头；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：单行文本；默认每个账号独立随机生成。规范账号对象内字段优先。

### `VORTEXA_USER_AGENT`

- 必填：否
- 敏感：否
- 获取或设置：浏览器 API 请求 User-Agent 请求头；不需要填写时使用内置 Windows Chrome 请求头
- 填写格式：单行文本；规范账号对象内 userAgent 优先。

### `VORTEXA_LOGIN_FIELD`

- 必填：否
- 敏感：否
- 获取或设置：从官网 /auth/login 请求体确认账号字段名
- 填写格式：可选字母开头的字母、数字、下划线字段，不能是 password；默认邮箱使用 email，其余使用 username。

### `VORTEXA_API_BASE`

- 必填：否
- 敏感：否
- 获取或设置：仅依据官网开发者工具确认 API 地址；无依据不要更改
- 填写格式：默认 https://api.vortexa.cloud/api；只允许 HTTPS，无 URL 凭据、查询串或片段。

### `VORTEXA_ORIGIN`

- 必填：否
- 敏感：否
- 获取或设置：官网请求 Origin 头
- 填写格式：默认 https://www.vortexa.cloud；只允许 HTTPS。

### `VORTEXA_REFERER`

- 必填：否
- 敏感：否
- 获取或设置：官网免费主机页面地址
- 填写格式：默认 https://www.vortexa.cloud/free-hosting；只允许 HTTPS。

### `VORTEXA_PRODUCT_ID`

- 必填：否
- 敏感：否
- 获取或设置：运行 VORTEXA_LIST_PRODUCTS=1 从公开免费产品列表获取
- 填写格式：产品 ID；指定值不存在就失败，不自动更换产品；即使同时提供套餐 ID 也须核验免费。

### `VORTEXA_PLAN_ID`

- 必填：否
- 敏感：否
- 获取或设置：运行产品列表模式从免费套餐列表获取
- 填写格式：免费套餐 ID；必须属于所选产品，且 type 为 free 或明确价格为零。

### `VORTEXA_PRODUCT_SLUG`

- 必填：否
- 敏感：否
- 获取或设置：运行产品列表模式获取产品 slug
- 填写格式：不区分大小写精确匹配；优先级低于产品 ID。

### `VORTEXA_PRODUCT_NAME`

- 必填：否
- 敏感：否
- 获取或设置：运行产品列表模式获取产品名称
- 填写格式：不区分大小写子串匹配，如 node；优先级低于 ID、slug；无选择参数时保留首个免费产品默认选择。

### `VORTEXA_LIST_PRODUCTS`

- 必填：否
- 敏感：否
- 获取或设置：用户按需启用
- 填写格式：1/true/yes/on 开启；默认关闭；优先于领取和循环模式，账号凭据仍必须符合契约但不发送到产品接口。

### `VORTEXA_CLAIM`

- 必填：否
- 敏感：否
- 获取或设置：用户明确希望领取免费主机时启用
- 填写格式：1/true/yes/on 开启；默认关闭，只读取主机、库存、免费套餐；不直接领取付费套餐。

### `VORTEXA_LOOP`

- 必填：否
- 敏感：否
- 获取或设置：用户按需启用库存轮询
- 填写格式：1/true/yes/on 开启；默认关闭；在领取模式下最多扫描 VORTEXA_MAX_SCANS 次，已有主机或领取核验完成即停止。

### `VORTEXA_MAX_SCANS`

- 必填：否
- 敏感：否
- 获取或设置：按可接受的轮询时间配置
- 填写格式：1 至 30 的整数；循环默认 3 次，未开启循环只扫描一次；建议执行时间小于十分钟定时间隔。

### `VORTEXA_TIMEOUT_MS`

- 必填：否
- 敏感：否
- 获取或设置：按网络质量配置
- 填写格式：1000 至 120000 的整数毫秒；默认 30000，覆盖完整请求时长。

### `VORTEXA_CONFIRM_DELAY_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按服务开通延迟配置
- 填写格式：0 至 120 的整数秒；默认 5；领取后等待再确认官方状态，未确认则失败且不重复提交。

### `VORTEXA_INTERVAL_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按库存扫描需要配置
- 填写格式：1 至 300 的整数秒；旧最小间隔别名，默认 30。

### `VORTEXA_INTERVAL_MIN_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按库存扫描需要配置
- 填写格式：1 至 300 的整数秒；默认采用 INTERVAL_SECONDS 或 30。

### `VORTEXA_INTERVAL_MAX_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按库存扫描需要配置
- 填写格式：不小于最小间隔且不大于 300 的整数秒；默认最小间隔与 60 中较大者。

### `VORTEXA_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：本地或青龙测试时启用
- 填写格式：1/true/yes/on 开启；不访问任何业务网络，不执行领取或登录；通知也受断网保护。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：已安装青龙 sendNotify.js 的所在目录
- 填写格式：可选目录；其次探测 /ql/data/scripts 和 /ql/scripts；不下载辅助文件，不作为业务依赖。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认上架列表，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、scripts/相对路径、文件名或文件名通配符；* 表示全部，空值表示全部关闭。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个 JSON 账号对象；同一账号的配套凭据放在同一对象。旧变量按非空行对齐，不使用 &、@ 或其他符号分隔账号。逐账号隔离登录与 Cookie；任一账号失败时整体退出码为 1。

## 验证与兼容性

SHA-256 `8c4f8f8b8853243dc2c8d4615fc898e0c1c3c1543d959ece49c67c8f91bc4e1e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7f027fefd96fedf2`。

## 副作用与风险

- 使用密码或刷新 Cookie 登录时创建或续期服务端登录会话；更新的访问 Token 和 Cookie 仅保存在本次进程内，不写文件。
- 仅在 VORTEXA_CLAIM 开启且产品套餐明确免费时提交免费主机领取，创建账号免费主机服务。
- 启用通知时通过已有青龙 sendNotify.js 发送脱敏任务总结；预演通知受断网保护。

## 许可证与来源

上游 `lizhixu/ql-script-hub` / `vortexa_free_claim.js` / `ac591a320092dcaeaf236b7c2b6acfd28981e589`。
