# 鸿星尔克签到与积分查询

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/comeonbabyy1_qiandao_jiaob_erke.py`
- 青龙命令：`python3 scripts/comeonbabyy1_qiandao_jiaob_erke.py`
- 建议 Cron：`48 9 * * *`
- 发布哈希：`9bb43b95b8f489661910a12a4d4c2848d2747e7086aa16cf3a4c98825c5f9196`
- 许可证：`MIT`

## 脚本功能

- 查询积分明细第一页（每页 5 条），显示累计、冻结、可用积分和接口提供的记录总数
- 执行会员签到，业务码 0000 表示成功、1001 表示今日已签到
- 保留原请求 URL、方法、签名、企业请求头及五项账号字段，不依赖原仓库模块
- 逐行多账号独立处理；查询失败仍尝试签到，任一步失败则账号和整体失败
- 官方响应包含昵称、用户名、显示名或公开 UID 时展示公开身份，隐藏凭据和设备标识
- 提供完全断网预演、分阶段计时、账号和任务统计以及唯一 TASK_SUMMARY JSON 记录
- 按照全局开关和名单使用青龙通知模块发送脱敏统计；通知失败保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ERKE_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录自己的鸿星尔克微信小程序，在合法授权的网络调试中查看 integral_record.json 或 sign/member_sign.json 请求体。将 memberId、enterpriseId、unionid、openid、wxOpenid 分别填入 member_id、enterprise_id、unionid、openid、wx_openid；值须来自同一账号，不要分享抓包内容。
- 填写格式：每个非空行一个紧凑 JSON 对象；上述五个字段为非空字符串。可选 account_name（仅兼容保存，不作为可信官方身份输出）、user_agent（自定义请求头）。保留上游字段名，替代原私有 config/token.json 的 erke.accounts 配置；不使用 & 或 @ 分隔账号。

### 可选参数

### `ERKE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：手动设置；开启后不发送业务请求或通知。
- 填写格式：1/true/yes/on 开启；0/false/no/off 关闭，默认 0；其他值按配置错误失败且不联网。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要自动模式发送时加入本脚本目录编号或文件名，或使用 *。
- 填写格式：逗号、分号、空白或换行分隔；支持目录编号 8f2a9a5ae3fed5d4、原路径 script/erke/main.py、文件名及文件名通配符。设置后替换默认名单；空值关闭全部，当前默认不在名单。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填写青龙已有 notify.py 所在目录；不要求安装私有项目。
- 填写格式：本地通知模块目录。依次尝试 import notify.send、此目录、/ql/data/scripts、/ql/scripts；通知输出被捕获，最多每次等待 20 秒，失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON 对象，配套凭据放在同一对象内；逐账号独立运行，任一账号配置、查询或签到失败则整体非零退出。

## 验证与兼容性

SHA-256 `9bb43b95b8f489661910a12a4d4c2848d2747e7086aa16cf3a4c98825c5f9196`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8f2a9a5ae3fed5d4`。

## 副作用与风险

- 正式运行时执行会员签到，可能增加积分及签到记录
- 通知启用时发送脱敏任务结果

## 许可证与来源

上游 `comeonbabyy1/qiandao-jiaob` / `script/erke/main.py` / `ce494881ab17ef23b5b9de9df30ea60567b3865c`。
