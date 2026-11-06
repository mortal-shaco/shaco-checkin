# 蔚来APP每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/weilai_auto_checkin.js`
- 青龙命令：`node scripts/weilai_auto_checkin.js`
- 建议 Cron：`8 9 * * *`
- 发布哈希：`01f7385d9e950b0ea4e3322ebd037dfcecddfcc55c80a13d4f496173232a67ff`
- 许可证：`MIT`

## 脚本功能

- 使用 Authorization 调用蔚来网关每日签到接口，识别 result_code=success 成功与 data.checked_in=true 今日已签。
- 展示连续签到天数、累计签到天数、签到时间与官方 tip 提示；字段缺失时不强行伪造。
- 官方返回非敏感昵称、用户名、显示名称或公开 UID 时直接展示，便于核对账号。
- 支持每行一个账号及可选备注前缀；兼容 WEILAI_AUTHORIZATION、weilai 历史变量名。
- 网络或业务失败可按配置重试；账号失败隔离并汇总退出状态。
- 按青龙全局开关与脚本名单发送脱敏通知，通知失败保留业务退出码。
- 完全断网预演：校验参数、模拟阶段与通知摘要，不发起业务或通知网络请求。
- 提供中文时间轴日志、编号阶段、耗时、逐账号与全局统计，以及唯一单行 TASK_SUMMARY JSON。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `WEILAI_TOKEN`

- 必填：是
- 敏感：是
- 获取或设置：使用本人蔚来账号，抓包蔚来 APP、app.nio.com 或 gateway-front-external.nio.com 请求头中的 Authorization；也可登录 https://www.nio.cn/ 后从浏览器请求头复制。勿使用他人凭据或日志中的敏感信息。青龙环境无法使用 Surge 拦截自动抓 Token，需手工配置。
- 填写格式：每个非空行一个账号。可写完整「Bearer …」或仅写 Bearer 后的 token（脚本自动补全前缀）。可选备注前缀「备注|token」，只在首个竖线处拆分。不使用 & 或 @ 分隔账号。

### 可选参数

### `WEILAI_AUTHORIZATION`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当未设置 WEILAI_TOKEN 时读取；获取方式与 WEILAI_TOKEN 相同。
- 填写格式：与 WEILAI_TOKEN 相同；每行一个 Authorization。

### `weilai`

- 必填：否
- 敏感：是
- 获取或设置：兼容历史变量名：仅当 WEILAI_TOKEN 与 WEILAI_AUTHORIZATION 均未设置时读取；获取方式与 WEILAI_TOKEN 相同。
- 填写格式：与 WEILAI_TOKEN 相同；每行一个 Authorization 或裸 token。

### `WEILAI_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要断网验证配置时手动设置；正式执行时删除或设为 0。
- 填写格式：1、true、yes、on 表示完全断网预演；其他值或未设置表示正式执行。预演不请求签到接口、不投递真实通知。

### `WEILAI_TIMEOUT_MS`

- 必填：否
- 敏感：否
- 获取或设置：需要调整单次 HTTP 超时时间时手动设置。
- 填写格式：1000 至 60000 的整数毫秒；缺省或非法值使用 15000。

### `WEILAI_MAX_RETRIES`

- 必填：否
- 敏感：否
- 获取或设置：需要调整网络或业务失败重试次数时手动设置。
- 填写格式：0 至 5 的整数；缺省或非法值使用 3。重试间隔约 2 秒。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙通知名单中填入 276c7c90b90de432、实际脚本文件名或 scripts 相对路径；未设置时默认对本任务发送通知。
- 填写格式：逗号、分号、空白或换行分隔的选择器；支持 * 与 ? 通配；* 表示全部；显式空值关闭全部青龙通知。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知工具不在默认目录时，填写本机 sendNotify.js 或 notify.py 所在目录。
- 填写格式：本地目录路径。依次尝试指定目录与 /ql/data/scripts、/ql/scripts 下的 sendNotify.js，再尝试 notify.py；通知失败只记录脱敏状态。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

WEILAI_TOKEN（或兼容别名）每个非空行一个账号；可选备注仅按第一个竖线分割。账号逐个独立签到与统计，任一账号失败则整体非零退出，其余账号继续执行。

## 验证与兼容性

SHA-256 `01f7385d9e950b0ea4e3322ebd037dfcecddfcc55c80a13d4f496173232a67ff`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/276c7c90b90de432`。

## 副作用与风险

- 正式运行时向蔚来签到接口提交每日签到，可能更新账号签到状态与天数统计。
- 启用通知且非预演时，通过青龙 notify 发送脱敏账号统计。

## 许可证与来源

上游 `zzhCloud/weilai-auto-checkin` / `weilai-auto-checkin.js` / `1c836570c573f19cc595ace7f4f2fbbfa7aeef37`。
