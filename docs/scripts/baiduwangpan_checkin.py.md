# 百度网盘签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/baiduwangpan_checkin.py`
- 青龙命令：`python3 scripts/baiduwangpan_checkin.py`
- 建议 Cron：`27 2 * * *`
- 发布哈希：`b9e5cc63e71a13413e7b7b36fe51b58bdcbbb22d6fc9d509f042029beb6f5ef8`
- 许可证：`MIT`

## 脚本功能

- 每日百度网盘会员签到，明确验证积分或已完成状态
- 获取并提交每日会员成长问题答案
- 读取并报告脱敏用户名、会员等级、成长值和会员类型
- 逐行多账号独立处理与结构化 JSON 汇总
- 完全断网的配置预演
- 成功、部分失败、失败、配置错误和预演状态的青龙脱敏汇总通知
- 兼容 BAIDUWP_COOKIE 与 BAIDUWP_DRY_RUN 旧变量；BAIDU_COOKIE 优先
- BAIDUWP_TASKS 可选择 signin、quiz、info，默认全执行，旧账号在签到后保留 3 秒请求间隔
- 旧 baiduwp.py 的通知选择器 ID 与路径仍可匹配

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `BAIDU_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：登录 https://pan.baidu.com/ 后打开浏览器开发者工具的 Network 面板，刷新页面，选择一个 pan.baidu.com 请求，复制 Request Headers 中完整的 Cookie 值。
- 填写格式：每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头

### 可选参数

### `BAIDUWANGPAN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：设为 1 可仅验证配置，不访问网络且不改变账号状态。
- 填写格式：1/true/yes/on 启用

### `BAIDUWANGPAN_DELAY_MAX`

- 必填：否
- 敏感：否
- 获取或设置：可选的账号间最大随机等待秒数，默认 0（不等待）。
- 填写格式：非负整数

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：如青龙 notify.py 不在标准位置，可设为其所在目录。
- 填写格式：包含 notify.py 的目录路径

### `BAIDUWP_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：与 BAIDU_COOKIE 相同；原 baiduwp.py 的环境变量可直接沿用。
- 填写格式：每个非空行一个完整 Cookie；BAIDU_COOKIE 非空时优先读取新变量。

### `BAIDUWP_TASKS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中指定需要执行的会员任务。
- 填写格式：逗号分隔 signin、quiz、info；默认全部执行，重复项只执行一次。

### `BAIDUWP_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：沿用原 baiduwp.py 的断网预演开关。
- 填写格式：1、true、yes 或 on 启用完全断网预演。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认上架列表，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、scripts/相对路径、文件名或文件名通配符；* 表示全部，空值表示全部关闭。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

BAIDU_COOKIE 中每个非空行是一个独立账号；依次处理，任一账号失败时进程整体非零退出。

## 验证与兼容性

SHA-256 `b9e5cc63e71a13413e7b7b36fe51b58bdcbbb22d6fc9d509f042029beb6f5ef8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d9230b69d9462c7c`。

## 副作用与风险

- 为每个已配置的百度网盘账号执行每日会员签到
- 为每个已配置的百度网盘账号提交每日会员问题答案
- 在通知开启且青龙通知模块可用时发送一条脱敏任务汇总通知

## 许可证与来源

上游 `agluo/ql-script-hub` / `baiduwangpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
