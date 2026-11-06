# zhcommerce每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/zhcommerce_signin.py`
- 青龙命令：`python3 scripts/zhcommerce_signin.py`
- 建议 Cron：`45 7 * * *`
- 发布哈希：`07b8971b7b90c7156274d7a009f2ae759d8e015c180b684b0d7c72a318ed8f8e`
- 许可证：`MIT`

## 脚本功能

- 每日按原计划执行 zhcommerce 微信小程序签到，保留原请求路径、请求头、正文、签名及版本参数。
- 识别 PUB-00000 签到成功和 MBR-00029 今日已签到，展示可用的奖励积分与连续签到天数。
- 支持逐行 JSON 多账号与完整旧版单账号变量。
- 展示官方返回的非敏感昵称、用户名、显示名称或公开 UID；仅出现敏感内容时抑制。
- 提供完全断网预演、按账号和阶段的脱敏日志、统计及单行 TASK_SUMMARY JSON。
- 所有运行结果生成脱敏通知摘要，通过青龙内置通知适配器发送；支持通知全局开关及任务选择器。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ZH_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人已登录的 zhcommerce 微信小程序中，通过本地调试代理查看每日签到 POST /api/v3/member/{appUid}/signs 请求。accessToken、deviceId、appUid、sid 取自查询参数，lat、lon、mallId 取自 JSON 请求体；必须属于同一账号和实际使用位置。凭据过期后重新登录获取，切勿分享请求或日志。
- 填写格式：每个非空行一个 JSON 对象，必填 accessToken、deviceId、appUid、sid、lat、lon；可选 mallId，默认 201。lat、lon 为有效经纬度数字，其余凭据为非空字符串；不使用 & 或 @ 分隔账号。配置此变量时优先使用它，不混入旧版变量。旧版单账号完整变量仍兼容。

### 可选参数

### `ZH_ACCESS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：在本人已登录的 zhcommerce 微信小程序中，通过本地调试代理查看每日签到 POST /api/v3/member/{appUid}/signs 请求。accessToken、deviceId、appUid、sid 取自查询参数，lat、lon、mallId 取自 JSON 请求体；必须属于同一账号和实际使用位置。凭据过期后重新登录获取，切勿分享请求或日志。
- 填写格式：旧版单账号兼容输入，对应 accessToken。仅未设置 ZH_ACCOUNTS 时生效；除 ZH_MALL_ID 默认 201 外，其余旧版字段均须完整配置。

### `ZH_DEVICE_ID`

- 必填：否
- 敏感：是
- 获取或设置：在本人已登录的 zhcommerce 微信小程序中，通过本地调试代理查看每日签到 POST /api/v3/member/{appUid}/signs 请求。accessToken、deviceId、appUid、sid 取自查询参数，lat、lon、mallId 取自 JSON 请求体；必须属于同一账号和实际使用位置。凭据过期后重新登录获取，切勿分享请求或日志。
- 填写格式：旧版单账号兼容输入，对应 deviceId。仅未设置 ZH_ACCOUNTS 时生效；除 ZH_MALL_ID 默认 201 外，其余旧版字段均须完整配置。

### `ZH_APP_UID`

- 必填：否
- 敏感：是
- 获取或设置：在本人已登录的 zhcommerce 微信小程序中，通过本地调试代理查看每日签到 POST /api/v3/member/{appUid}/signs 请求。accessToken、deviceId、appUid、sid 取自查询参数，lat、lon、mallId 取自 JSON 请求体；必须属于同一账号和实际使用位置。凭据过期后重新登录获取，切勿分享请求或日志。
- 填写格式：旧版单账号兼容输入，对应 appUid。仅未设置 ZH_ACCOUNTS 时生效；除 ZH_MALL_ID 默认 201 外，其余旧版字段均须完整配置。

### `ZH_SID`

- 必填：否
- 敏感：是
- 获取或设置：在本人已登录的 zhcommerce 微信小程序中，通过本地调试代理查看每日签到 POST /api/v3/member/{appUid}/signs 请求。accessToken、deviceId、appUid、sid 取自查询参数，lat、lon、mallId 取自 JSON 请求体；必须属于同一账号和实际使用位置。凭据过期后重新登录获取，切勿分享请求或日志。
- 填写格式：旧版单账号兼容输入，对应 sid。仅未设置 ZH_ACCOUNTS 时生效；除 ZH_MALL_ID 默认 201 外，其余旧版字段均须完整配置。

### `ZH_LAT`

- 必填：否
- 敏感：是
- 获取或设置：在本人已登录的 zhcommerce 微信小程序中，通过本地调试代理查看每日签到 POST /api/v3/member/{appUid}/signs 请求。accessToken、deviceId、appUid、sid 取自查询参数，lat、lon、mallId 取自 JSON 请求体；必须属于同一账号和实际使用位置。凭据过期后重新登录获取，切勿分享请求或日志。
- 填写格式：旧版单账号兼容输入，对应 lat。仅未设置 ZH_ACCOUNTS 时生效；除 ZH_MALL_ID 默认 201 外，其余旧版字段均须完整配置。

### `ZH_LON`

- 必填：否
- 敏感：是
- 获取或设置：在本人已登录的 zhcommerce 微信小程序中，通过本地调试代理查看每日签到 POST /api/v3/member/{appUid}/signs 请求。accessToken、deviceId、appUid、sid 取自查询参数，lat、lon、mallId 取自 JSON 请求体；必须属于同一账号和实际使用位置。凭据过期后重新登录获取，切勿分享请求或日志。
- 填写格式：旧版单账号兼容输入，对应 lon。仅未设置 ZH_ACCOUNTS 时生效；除 ZH_MALL_ID 默认 201 外，其余旧版字段均须完整配置。

### `ZH_MALL_ID`

- 必填：否
- 敏感：否
- 获取或设置：在本人已登录的 zhcommerce 微信小程序中，通过本地调试代理查看每日签到 POST /api/v3/member/{appUid}/signs 请求。accessToken、deviceId、appUid、sid 取自查询参数，lat、lon、mallId 取自 JSON 请求体；必须属于同一账号和实际使用位置。凭据过期后重新登录获取，切勿分享请求或日志。
- 填写格式：旧版单账号兼容输入，对应 mallId。仅未设置 ZH_ACCOUNTS 时生效；除 ZH_MALL_ID 默认 201 外，其余旧版字段均须完整配置。

### `ZH_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：1、true、yes、on 启用完全断网预演；默认关闭。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置通知任务选择器。
- 填写格式：auto 时生效；逗号、分号、空白或换行分隔，支持目录编号、脚本相对路径、文件名、文件名通配符，* 全选，空值禁用全部；设置后替换默认名单。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选填写现有青龙通知模块所在目录；不配置则自动查找内置模块及标准目录。
- 填写格式：包含 notify.py 或 sendNotify.js 的目录。发送失败或缺失不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个完整 JSON 账号；配套凭据保存在同一行，逐账号独立执行，任一账号配置或签到失败整体非零退出。旧版变量仅支持单账号。

## 验证与兼容性

SHA-256 `07b8971b7b90c7156274d7a009f2ae759d8e015c180b684b0d7c72a318ed8f8e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/cc47f2a2bfb54455`。

## 副作用与风险

- 正式模式提交每日签到，可能领取积分并增加连续签到天数。
- 通知启用且适配器可用时发送脱敏任务摘要。

## 许可证与来源

上游 `guopenglong/automation-scripts` / `zhcommerce/zhcommerce_signin.py` / `65931dcd9a3c37619b442bea4930df0dc44c57f2`。
