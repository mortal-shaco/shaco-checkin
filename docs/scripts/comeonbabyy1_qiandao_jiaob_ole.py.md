# Ole精品超市签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/comeonbabyy1_qiandao_jiaob_ole.py`
- 青龙命令：`python3 scripts/comeonbabyy1_qiandao_jiaob_ole.py`
- 建议 Cron：`53 9 * * *`
- 发布哈希：`ed68d7c3321e55570e12f80a8ee61a5982a61b5e3dae7edcfbc4ab5d1970576e`
- 许可证：`MIT`

## 脚本功能

- 每日多账号签到，保留原 POST 地址、请求头、门店和城市默认参数。
- 每个账号可独立配置用户代理、门店和城市，兼容原账号对象字段。
- 仅在响应明确给出布尔 success=true 且无 error 或内层业务失败时确认签到成功，未知响应失败闭合。
- 显示官方返回的非敏感昵称、用户名、显示名称或公开 UID，屏蔽凭据、手机号和设备值。
- 断网预演、带时间戳的分阶段日志、账号统计和唯一 TASK_SUMMARY JSON。
- 青龙通知汇总和通知开关，通知不可用时保留业务退出码。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `OLE_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录自己的 Ole 微信小程序，通过本机授权抓包查看签到请求 /vgdt_app_api/v1/vgdt-fea-app-member/front_api/member_sign。将请求头 sessionId、Device-Name、unique、oleWxOpenId 分别填入 session_id、device_name、unique、ole_wx_open_id。shopCode、cityId、User-Agent 可填入对应可选字段。会话失效后重新登录获取，不要分享抓包记录。
- 填写格式：每个非空行一个完整 JSON 对象。必填非空字符串 session_id、device_name、unique、ole_wx_open_id；可选字符串 shop_code 默认 205368、city_id 默认 c_region_11122、user_agent 默认保留上游值。兼容原账号对象 account_name 字段但不将其作为官方身份输出。JSON 内凭据完整保留，不使用 & 或 @ 分隔账号。

### 可选参数

### `OLE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：手动设为 1 启用断网预演。
- 填写格式：1、true、yes、on 启用；默认实际签到。预演仅验证配置，不证明真实业务成功，通知只生成汇总并模拟投递。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选设置通知脚本名单；未设置时本脚本默认通知。
- 填写格式：auto 模式使用名单；逗号、分号或空白分隔目录编号、脚本相对路径、文件名或文件名通配符；* 选择全部，空值禁用全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：仅当青龙通知文件不在标准位置时设置其所在目录。
- 填写格式：包含 notify.py 或 sendNotify.js 的目录；同时支持导入 notify.send 以及 /ql/data/scripts、/ql/scripts 标准位置。通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每行一个完整账号 JSON 对象，忽略空行；各账号独立处理，任一账号配置或签到失败时整体非零退出。

## 验证与兼容性

SHA-256 `ed68d7c3321e55570e12f80a8ee61a5982a61b5e3dae7edcfbc4ab5d1970576e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/298cb5cdd1a60602`。

## 副作用与风险

- 向 Ole 接口提交账号签到，可能领取签到奖励。
- 实际运行时按通知开关通过青龙配置渠道发送脱敏汇总通知。

## 许可证与来源

上游 `comeonbabyy1/qiandao-jiaob` / `script/huaruntong/ole/main.py` / `ce494881ab17ef23b5b9de9df30ea60567b3865c`。
