# 华润通Ole签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/ole.py`
- 青龙命令：`python3 scripts/ole.py`
- 建议 Cron：`6 1 1 1 1`
- 发布哈希：`62ae451d8de0b2ee0dd4d4ac2e200b89e345d80b7618c0fb27a7b1d6f518c201`
- 许可证：`MIT`

## 脚本功能

- Ole 微信小程序账号签到
- 保留原账号字段、门店与城市默认值及定时表达式
- 多账号独立执行与失败闭合退出
- 完全断网预演及参数检查
- 脱敏分阶段日志、账号统计与单行任务汇总
- 青龙通知摘要与全局开关；断网预演模拟通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `OLE_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人授权登录的 Ole 微信小程序中抓取 member_sign 请求；将 sessionId、Device-Name、unique、oleWxOpenId 请求头分别填入 session_id、device_name、unique、ole_wx_open_id。可同时取得 shopCode、cityId、User-Agent；不要向他人提供这些值。
- 填写格式：每个非空行一个 JSON 对象；四个必填字段均为非空字符串。可选 shop_code 默认 205368，city_id 默认 c_region_11122，user_agent 默认保留上游值。兼容 account_name 字段但不输出用户填写的标签，避免泄漏手机号。

### 可选参数

### `OLE_CONFIG_JSON`

- 必填：否
- 敏感：是
- 获取或设置：可将既有 token.json 内容复制到此变量，作为旧配置结构兼容输入；配置 OLE_ACCOUNTS 时优先使用后者。
- 填写格式：JSON 对象，结构为 huaruntong.ole.accounts 数组；数组内保留原账号字段。无需私有文件路径。

### `OLE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置，用于完全断网预演。
- 填写格式：1、true、yes、on 启用；默认 0。预演不代表真实业务成功。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置全局通知开关。
- 填写格式：默认 1；0、false、no、off 关闭。断网预演生成摘要并模拟投递，不运行通知模块。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：如青龙通知模块不在默认路径，将 notify.py 所在目录填入；无需配置即可尝试导入 notify 和青龙常见目录。
- 填写格式：可选本地目录路径，仅用于青龙通知；不可用或失败不会改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个完整 JSON 账号对象，同一账号凭据合并在一行；逐账号独立执行，任一失败时整体非零退出。

## 验证与兼容性

SHA-256 `62ae451d8de0b2ee0dd4d4ac2e200b89e345d80b7618c0fb27a7b1d6f518c201`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/89d9992e56504271`。

## 副作用与风险

- 正式模式向 Ole 提交会员签到，可能增加签到记录及奖励积分
- 正式模式按青龙配置发送任务通知

## 许可证与来源

上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/ole/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
