# 顺丰快递积分任务

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/comeonbabyy1_qiandao_jiaob_sf.py`
- 青龙命令：`python3 scripts/comeonbabyy1_qiandao_jiaob_sf.py`
- 建议 Cron：`56 9 * * *`
- 发布哈希：`f13ab286e591493833fbdf86b36a3ed7b471d99859730e63fdb588376caf8991`
- 许可证：`MIT`

## 脚本功能

- 自动签到并领取签到礼包，报告连续天数、礼包名称和有效期
- 查询每日积分任务，区分非日常任务、已完成任务和待领奖任务
- 通过显式 taskCode 白名单完成每日任务，领取已确认可领取的积分奖励
- 逐行多账号配置、独立处理和汇总，任一账号失败时非零退出
- 按接口返回显示非敏感官方昵称、用户名、显示名称或公开标识，并隐藏凭据和手机号
- 内置 HTTP、MD5 签名和 SW8 追踪头生成，保持上游接口路径、POST 方法和主要请求字段
- 完全断网预演、时间轴分阶段日志、逐账号统计和单行 TASK_SUMMARY 汇总
- 按青龙通知开关与筛选规则发送脱敏结果，通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `SF_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人已登录的顺丰 App 积分福利页面，通过获授权的本机抓包读取 mcs-mimp-web.sf-express.com 请求的 Cookie、userId、deviceId、channel 和 User-Agent。cookies 与 user_id 为必需字段；device_id、channel、user_agent 按原请求填写。登录过期后重新获取，禁止分享。可将旧 token.json 中 sf.accounts 的每个对象分别序列化成一行填入本变量，无需保留原仓库或配置文件。
- 填写格式：每个非空行一个 JSON 对象，字段沿用 cookies、user_id、device_id、user_agent、channel、account_name；后四项可选，account_name 兼容读取但日志按账号序号和官方身份显示。JSON 字符串按标准转义，Cookie 内的分号、等号、&、@ 保持原样，禁止用这些字符分隔账号。

### 可选参数

### `SF_TASK_CODES`

- 必填：否
- 敏感：否
- 获取或设置：先在本人积分页面核对任务内容和完成条件，从 queryPointTaskAndSignFromES 的 taskTitleLevels 中取得确实允许自动完成的每日任务 taskCode。仅加入无消费、发文、分享、账户资料修改等风险的任务。
- 填写格式：逗号分隔的精确 taskCode 白名单，默认空；不支持通配符。仅对白名单中状态为 1 的日常任务请求完成，状态 2 只领取奖励，状态 3 视为已完成；未知状态失败。

### `SF_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置为 1 开启完全断网预演。
- 填写格式：1、true、yes、on 开启；0、false、no、off 关闭；默认 0。预演仅校验参数和生成计划，不访问服务或通知渠道。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要筛选通知脚本时，在青龙环境变量中配置。
- 填写格式：auto 模式下设置后替换默认范围；支持目录相对路径 script/sf/main.py、文件名、文件名通配符和目录标识 c1b75e3c541294ce，使用逗号、分号或空白分隔；* 匹配全部，空值禁用全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：仅当青龙 notify.py 不在默认路径时，填写青龙已安装通知模块所在目录。
- 填写格式：可选本机目录；依次尝试 import notify.send、本目录的 notify.py、/ql/data/scripts/notify.py、/ql/scripts/notify.py。通知不可用、失败或超过 30 秒均保留业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

SF_ACCOUNTS 每个非空行对应一个账号 JSON 对象，同一账号 Cookie、用户标识及可选设备、渠道和请求头放在同一对象中；账号独立执行，任一账号配置或业务失败时整体非零退出。

## 验证与兼容性

SHA-256 `f13ab286e591493833fbdf86b36a3ed7b471d99859730e63fdb588376caf8991`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c1b75e3c541294ce`。

## 副作用与风险

- 正式执行时签到并领取签到礼包
- 正式执行时为 SF_TASK_CODES 明确允许的日常任务提交完成记录
- 正式执行时领取已完成任务的积分奖励
- 通知启用时通过青龙已配置渠道发送脱敏结果摘要

## 许可证与来源

上游 `comeonbabyy1/qiandao-jiaob` / `script/sf/main.py` / `ce494881ab17ef23b5b9de9df30ea60567b3865c`。
