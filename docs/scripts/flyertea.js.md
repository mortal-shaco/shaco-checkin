# 飞客茶馆签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/flyertea.js`
- 青龙命令：`node scripts/flyertea.js`
- 建议 Cron：`18 10 * * *`
- 发布哈希：`ee0d3db5d5505cd70ce51829b46b9fd662e5a07351b1d36423bcff3c9855e435`
- 许可证：`GPL-3.0-only`

## 脚本功能

- 每日飞客茶馆签到，保留原 GET 接口、固定客户端头和查询参数语义
- 识别明确业务成功及当天只能签到一次的已完成状态
- 组合配置同一账号 Cookie 和查询参数，兼容旧环境变量单账号输入
- 每行一个账号，独立处理与失败汇总
- 展示官方返回的非敏感用户名、昵称、显示名称和公开 UID
- 完全断网预演，分阶段时间轴、账号与子任务统计、单行 TASK_SUMMARY 汇总
- 按全局开关与脚本选择器发送青龙脱敏汇总，通知故障不改变业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `FLYERTEA_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录飞客 App，在本人授权的 HTTPS 抓包中手动签到。查找 www.flyert.com/plugin.php?id=k_misign:sign&operation=qiandao 请求，复制完整 Cookie，并从查询串取得 version、appkey、appversion、formhash、token。用 URLSearchParams 等方式解码查询值一次，填入 params 对象。过期后重新登录采集；不要公开抓包或凭据。
- 填写格式：每个非空行一个 JSON 对象：cookie 为完整 Cookie 字符串，params 为包含 version、appkey、appversion、formhash、token 的对象，字段为非空字符串或数字。使用标准 JSON 序列化，不用 & 或 @ 分隔账号。优先于旧变量；设为空时报告配置错误。

### 可选参数

### `chavy_cookie_flyertea`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游同名存储键；从本人签到请求复制完整 Cookie。建议迁移至 FLYERTEA_ACCOUNTS。
- 填写格式：仅未设置 FLYERTEA_ACCOUNTS 时使用；单账号完整 Cookie，必须配合旧 token 变量。

### `chavy_token_flyertea`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游采集结果的参数 JSON；不要运行会打印凭据的旧采集脚本，改为手动提取。
- 填写格式：单行 JSON 对象，包含 version、appkey、appversion、formhash、token，使用已解码值；与 chavy_cookie_flyertea 属于同一账号。

### `FLYERTEA_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置为 1 进行预演。
- 填写格式：1、true、yes、on 启用完全断网预演，其余值为正式执行；不调用签到接口或通知模块。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙配置通知脚本选择器。
- 填写格式：逗号、分号或空白分隔，支持 c48b00b2cb36fe09、flyertea/flyertea.js、checkin/flyertea.js、flyertea.js、当前脚本文件名及含 * 的通配符；* 选择全部，空值禁用全部；显式全局开关优先。默认无选中项。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：如通知模块不在标准位置，填写青龙 sendNotify.js 所在目录。
- 填写格式：可选目录；随后查找 /ql/data/scripts/sendNotify.js、/ql/scripts/sendNotify.js。青龙模块只用于通知，签到逻辑不依赖此文件。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

FLYERTEA_ACCOUNTS 每个非空行一个账号 JSON，Cookie 与配套参数写入同一对象。逐账号独立执行，任一账号配置错误或签到失败则整体非零退出。旧变量仅兼容单账号。

## 验证与兼容性

SHA-256 `ee0d3db5d5505cd70ce51829b46b9fd662e5a07351b1d36423bcff3c9855e435`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c48b00b2cb36fe09`。

## 副作用与风险

- 正式执行向飞客提交每日签到，可能获得平台签到奖励
- 通知启用且脚本被选中时，通过青龙通知模块发送脱敏汇总

## 许可证与来源

上游 `chavyleung/scripts` / `flyertea/flyertea.js` / `bfab3c906f3d5d126e9094f15730e025f7f32128`。
