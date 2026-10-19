# 华润通微信版签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/huaruntong_wx.py`
- 青龙命令：`python3 scripts/huaruntong_wx.py`
- 建议 Cron：`18 1 1 1 1`
- 发布哈希：`a1a8a4e01bc45df4db9d474f094de35765952a50ef29e2479d26c7e2f0e70e00`
- 许可证：`MIT`

## 脚本功能

- 华润通微信版加密签到，仅以官方业务码 S0A00000 确认成功
- 兼容原签到请求全部可配置参数及默认值，保持原 cron
- 逐行多账号独立执行、参数校验和失败非零退出
- 展示官方返回的非敏感昵称、用户名、显示名称或公开身份
- 完全断网预演、逐阶段耗时和脱敏结构化统计
- 青龙通知汇总，通知不可用不影响业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `HRT_WX_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录华润通微信版官方页面，在本人授权的网络调试中查看 mid.huaruntong.cn/api/points/saveQuestionSignin 请求加密前的 token 和业务参数；请求体 key/data 是密文，不能直接当作 token。不得分享抓包内容。失效后重新登录获取。将原配置 huaruntong.huaruntong_wx.accounts 中每个对象复制为单独一行亦可，不读取原私有配置文件。
- 填写格式：每个非空行一个账号：可直接填写完整 token，也可填写含 token 字段的单行 JSON 对象。JSON 兼容 answerResult（整数，默认 1）、channelId（默认 APP）、merchantCode（默认 1641000001532）、storeCode（默认 qiandaosonjifen）、sysId（默认 T0000001）、transactionUuid 和 inviteCode（默认空字符串）、user_agent（默认原 iPhone 浏览器标识）、account_name。字符串字段使用 JSON 转义；不使用 &、@ 分隔账号，token 内这些字符保留。account_name 兼容输入但日志使用账号序号和官方公开身份。

### 可选参数

### `HRT_WX_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：青龙环境变量中自行设置。
- 填写格式：1、true、yes 或 on 启用断网预演，默认 0。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填写青龙现有 notify.py 或 sendNotify.js 所在目录。默认尝试导入 notify，再查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：本机目录路径；不下载或安装通知程序。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认上架列表，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、scripts/相对路径、文件名或文件名通配符；* 表示全部，空值表示全部关闭。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，配套参数放在同一行 JSON 对象中；逐账号独立处理，任一账号失败则整体非零退出。

## 验证与兼容性

SHA-256 `a1a8a4e01bc45df4db9d474f094de35765952a50ef29e2479d26c7e2f0e70e00`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/13902b7b1dd570d1`。

## 副作用与风险

- 正式运行提交签到与答题结果，可能获得签到积分
- 正式运行通过青龙通知组件发送脱敏任务汇总

## 许可证与来源

上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/huaruntong_wx/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
