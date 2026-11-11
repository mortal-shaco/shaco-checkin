# 昆明医科大学健康登记

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_eddc6997.py`
- 青龙命令：`python3 scripts/task_eddc6997.py`
- 建议 Cron：`49 10 * * *`
- 发布哈希：`7ece42c030dae0eaff34f5e7245c0a653990aa9fd7e4e85e120c33ad9fb13884`
- 许可证：`MIT`

## 脚本功能

- 独立实现学校网页登录、会话管理与防重复提交字段读取，无需上游仓库、用户文件或预装应用。
- 默认检查当天健康登记状态，待登记、登录失败、窗口限制和接口变化均非零退出。
- 显式启用后使用本人当天完整真实表单申报，核验身份及六项答案一致性，提交后再次读取并确认当日已登记。
- 每行一个账号，独立执行并汇总失败，密码中的后续分隔符保留。
- 显示学校返回的非敏感姓名，屏蔽凭据、手机号、地址、证件和原始响应。
- 完整断网预演、分阶段计时日志、逐账号统计及单行 TASK_SUMMARY JSON。
- 实际执行各类结果均按全局开关和脚本选择器尝试青龙脱敏通知。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `EPIDEMIC_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：使用本人昆明医科大学学生疫情防控平台学号与密码，先在学校平台人工确认可以登录。切勿将凭据放入日志或通知。
- 填写格式：每个非空行一个账号，格式为学号|密码，仅在第一个 | 处分割，密码中的后续 | 保持原样。不使用 & 或 @ 分隔账号。

### 可选参数

### `EPIDEMIC_ACTION`

- 必填：否
- 敏感：否
- 获取或设置：默认 check 登录并检查当天登记状态。确需提交本人真实健康申报时设置 submit，并填写 EPIDEMIC_REPORTS。
- 填写格式：check 或 submit，默认 check。当天待登记返回非零。

### `EPIDEMIC_REPORTS`

- 必填：否
- 敏感：是
- 获取或设置：仅 submit 模式需要。当天登录学校平台，在浏览器开发者工具网络面板取得本人核实后的 Report/Index 完整表单，将键和值转换为字符串。包含身份、地址、六项真实健康答案、PZData 及计数字段，应保密保存。不得采用上游硬编码健康答案。按账号非空行顺序构造数组，每项有 date 和 form。脚本核验日期、身份和答案一致性，并使用当前页面 ReSubmiteFlag。
- 填写格式：JSON 数组，每账号一项。date 为当天北京时间 YYYY-MM-DD，form 为完整字符串键值对象。必需字段为 City、CityName、ClassName、CollegeNo、ComeWhere、County、CountyName、FaCity、FaCityName、FaComeWhere、FaCounty、FaCountyName、FaProvince、FaProvinceName、GetAreaUrl、IdCard、MoveTel、Name、Other、PZData、Province、ProvinceName、ReSubmiteFlag、Sex、SpeGrade、SpeType、SpecialtyName、StudentId、blackCount、checkboxCount、radioCount、radio_1、radio_2、radio_3、radio_4、radio_5、radio_6、text_1。

### `EPIDEMIC_USER_AGENT`

- 必填：否
- 敏感：否
- 获取或设置：可从本人浏览器请求头获取 User-Agent，无需原仓库 User-Agent 文件。
- 填写格式：单行浏览器标识，默认 Mozilla/5.0。

### `EPIDEMIC_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线验收时设为 1，只校验参数并生成模拟摘要，学校请求、申报与通知外发全部跳过。
- 填写格式：1、true、yes、on 启用，0、false、no、off 关闭，默认 0。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选通知选择器，设置后替换默认选中行为。支持目录 ID、脚本路径、文件名和文件名通配符。
- 填写格式：逗号、分号或空白分隔，* 选择全部，空字符串关闭全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知模块位于自定义目录时，填写含 notify.py 的目录。也支持 import notify.send 和标准青龙脚本目录。
- 填写格式：本机目录路径，可不填。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

EPIDEMIC_ACCOUNTS 每个非空行一个账号，仅在第一个 | 处分割学号和密码。各账号独立会话与执行，任一失败则进程非零退出。EPIDEMIC_REPORTS 数组顺序与账号非空行对应。

## 验证与兼容性

SHA-256 `7ece42c030dae0eaff34f5e7245c0a653990aa9fd7e4e85e120c33ad9fb13884`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/eddc6997bb5dba67`。

## 副作用与风险

- 登录时在学校服务建立本人会话。
- 仅显式设置 submit 且提供当天真实完整表单时，提交健康登记。
- 实际运行通知启用时，通过青龙通知模块向配置渠道发送脱敏任务摘要。

## 许可证与来源

上游 `2657753129/Epidemic` / `main.py` / `17829c1563f57560b16ef79a7e683e7ded14e513`。
