# 华润通微信签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/comeonbabyy1_qiandao_jiaob_huaruntong_wx.py`
- 青龙命令：`python3 scripts/comeonbabyy1_qiandao_jiaob_huaruntong_wx.py`
- 建议 Cron：`54 9 * * *`
- 发布哈希：`7c1bd8708b8bce8904d4bc077b9768dca30a24da8d58c02ba6577c7f6834ba20`
- 许可证：`MIT`

## 脚本功能

- 华润通微信端每日答题签到，保留 HMAC-MD5 签名、AES-CBC 加密和 RSA-OAEP 密钥封装
- 保留原签到接口全部配套参数及默认值，支持单行 JSON 原字段名兼容输入
- 每行一个账号独立执行，任一失败时返回非零退出码
- 显示官方返回的非敏感账号身份，提供分阶段日志、统计及单行 TASK_SUMMARY 汇总
- 按青龙通知开关和脚本列表发送脱敏总结，通知失败保留业务退出码
- 完全断网预演参数及加密契约，预演不宣称业务成功

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `HRT_WX_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：本人登录华润通微信端，在授权的本机调试环境查看 mid.huaruntong.cn/api/points/saveQuestionSignin 签到请求加密前的 token；网络封包中的 key、data 不是 token。配套参数从本人同一请求获取，无法读取时请勿猜测凭据。
- 填写格式：每个非空行一个账号；每行填 token 或单行 JSON 对象。JSON 必须包含 token，可包含 account_name、answerResult（整数，默认 1）、channelId（默认 APP）、merchantCode（默认 1641000001532）、storeCode（默认 qiandaosonjifen）、sysId（默认 T0000001）、transactionUuid（默认空）、inviteCode（默认空）和 user_agent。不要用 & 或 @ 分隔账号。account_name 保留兼容但不作为日志身份，优先显示官方公开身份。

### 可选参数

### `HRT_WX_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置，用于完全断网预演参数和加密契约。
- 填写格式：1、true、yes 或 on 启用；默认实跑。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：填写需要通知的脚本选择器；设置后替换默认选择列表，本脚本没有默认选中项。
- 填写格式：使用逗号、分号或空白分隔目录编号、脚本相对路径、文件名或文件名通配符；* 表示全部，空值表示不选择。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填写青龙通知模块所在目录；默认尝试导入 notify，再搜索 /ql/data/scripts 与 /ql/scripts。
- 填写格式：包含 notify.py 或 sendNotify.js 的本机目录；通知不可用或失败不会改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号；单行 token 或包含 token 与同账号配套参数的 JSON 对象。逐账号隔离执行，任一账号失败时整体非零退出。

## 验证与兼容性

SHA-256 `7c1bd8708b8bce8904d4bc077b9768dca30a24da8d58c02ba6577c7f6834ba20`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8d1f195e1b3e02a0`。

## 副作用与风险

- 向华润通提交本人每日签到及答题结果，可能获得积分
- 实跑且通知策略允许时调用青龙通知服务发送脱敏总结

## 许可证与来源

上游 `comeonbabyy1/qiandao-jiaob` / `script/huaruntong/huaruntong_wx/main.py` / `ce494881ab17ef23b5b9de9df30ea60567b3865c`。
