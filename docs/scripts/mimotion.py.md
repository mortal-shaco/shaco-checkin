# 小米运动账号验证与步数上传

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/mimotion.py`
- 青龙命令：`python3 scripts/mimotion.py`
- 建议 Cron：`46 0 * * *`
- 发布哈希：`065b1c6cd7be4d60da5332ca5d38de53830d899000d656717b839f243efaac3e`
- 许可证：`MIT`

## 脚本功能

- 手机号或邮箱及密码登录 Zepp Life，核验授权与完整登录凭据，显示官方非敏感账号身份。
- 显式开启后在设定的随机范围内修改本人当天运动记录的步数并上传，要求接口 code=0 且 message=success。
- 优先获取远程时间戳，失败使用本地毫秒时间；HTTP 表单编码、超时、响应大小限制及禁止凭据重定向。
- 多账号独立执行、失败非零退出、断网预演、脱敏分阶段日志、单行 TASK_SUMMARY 汇总及青龙通知。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `MIMOTION_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 Zepp Life 注册或绑定手机号、邮箱并设置登录密码；使用 Zepp Life 凭据，不是小米账号密码。在青龙环境变量中填写账号，切勿分享凭据。上传时从本人当天的 Zepp Life 运动同步请求取得 data_json 与 last_deviceid，先对 data_json 做 URL 解码，再放入同一账号 JSON 对象。
- 填写格式：每个非空行一个 手机号或邮箱|密码，仅在第一个 | 分割；也支持每行一个 JSON 对象，字段 phone、password，上传时另需 data_json、last_deviceid，可选 min_step、max_step。data_json 是仅含当天一条记录的数组或 JSON 字符串，必须有非空 data 数组和 summary.stp.ttl；summary 可为对象或 JSON 字符串。

### 可选参数

### `MIMOTION`

- 必填：否
- 敏感：是
- 获取或设置：可选旧版账号环境变量；仅在 MIMOTION_ACCOUNTS 为空时使用。将原配置中的 MIMOTION 账号数组复制为该环境变量，不再读取 config.json。
- 填写格式：JSON 数组；每个对象支持 phone、password、min_step、max_step；上传仍须本人 data_json、last_deviceid。

### `MIMOTION_ACTION`

- 必填：否
- 敏感：否
- 获取或设置：按需要设置；默认 login 仅验证账号，upload 显式授权修改本人当天步数。
- 填写格式：login 或 upload，默认 login。

### `MIMOTION_MIN_STEP`

- 必填：否
- 敏感：否
- 获取或设置：可选最小步数；只在明确开启上传时使用，账号 min_step 优先。
- 填写格式：整数，默认 10000；0≤最小值≤最大值≤100000。

### `MIMOTION_MAX_STEP`

- 必填：否
- 敏感：否
- 获取或设置：可选最大步数；只在明确开启上传时使用，账号 max_step 优先。
- 填写格式：整数，默认 19999；与最小步数构成含两端的随机范围。

### `MIMOTION_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：设为 1 启用完全断网预演，验证参数和执行计划，不登录、不上传；通知也禁止联网。
- 填写格式：1 启用；0、false、no、off 或空值关闭，默认 0。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；默认调用 notify.py，缺失、超时或发送失败仅记录，不覆盖业务退出码。
- 填写格式：默认 1；0、false、no、off 关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选青龙通知模块目录；自动优先导入 notify，再查该目录以及 /ql/data/scripts、/ql/scripts。
- 填写格式：包含 notify.py 的本地目录；不是业务脚本依赖。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，仅在首个 | 分割账号和密码，密码中的其它分隔符保留；上传参数同属该行 JSON 对象。每个账号独立执行，任一失败均非零退出。旧 MIMOTION 数组只作为兼容输入。

## 验证与兼容性

SHA-256 `065b1c6cd7be4d60da5332ca5d38de53830d899000d656717b839f243efaac3e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4b7d4969e07369fa`。

## 副作用与风险

- 正式登录会申请 Zepp 授权及登录令牌。
- 仅 MIMOTION_ACTION=upload 时上传本人提供的当天运动记录，修改 summary.stp.ttl；其它提供的记录字段保持原样，不合成心率或睡眠数据。
- 启用通知时调用青龙通知模块发送脱敏汇总，预演禁止联网。

## 许可证与来源

上游 `Sitoi/dailycheckin` / `dailycheckin/mimotion/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
