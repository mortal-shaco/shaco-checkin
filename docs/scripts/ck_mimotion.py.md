# 小米运动

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/ck_mimotion.py`
- 青龙命令：`python3 scripts/ck_mimotion.py`
- 建议 Cron：`1 0 * * *`
- 发布哈希：`04db959c4cfbfe05a52b98e738dfded8305111aaa467519530f03cd4bdad6513`
- 许可证：`MIT`

## 脚本功能

- 华米手机号密码登录、校验账号与应用令牌，显示官方返回的非敏感昵称、用户名或公开 UID。
- 显式上传本人当天模板并随机修改步数总量，保留 min_step/max_step 参数名及原默认范围。
- 每行一个账号，独立执行，失败闭合退出。
- 完全断网预演、分阶段脱敏日志、账号及子任务统计、单条 TASK_SUMMARY 记录。
- 正式运行尝试青龙通知，配置错误与部分失败同样汇总；预演仅显示通知内容。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `MIMOTION_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在 Zepp Life（原小米运动）注册中国大陆华米手机号账号并设置密码，使用 phone/password；不是小米账号密码。显式上传时，从本人获授权的 band_data.json 同步请求获取 last_deviceid 及解码后的 data_json 数组，将数组填入 band_data，不要分享账号数据。
- 填写格式：每个非空行一个 JSON 对象；phone 为中国大陆手机号字符串，password 为密码字符串，完整保留分隔符。可选 min_step/max_step 默认 10000/19999，范围 0 至 100000，最小值不超过最大值。可选 device_id 为登录设备 UUID，省略时本轮生成。上传须提供本人 last_deviceid 和仅含当天一条记录的 band_data 数组，summary 为包含 stp.ttl 的 JSON 字符串；可选 last_sync_data_time 默认 0。

### 可选参数

### `MIMOTION_ACTION`

- 必填：否
- 敏感：否
- 获取或设置：按需选择；默认只验证登录和应用令牌，显式 upload 才上传。上传前核对本人模板中的活动、睡眠和心率等记录。
- 填写格式：login 或 upload，默认 login。

### `MIMOTION_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：测试时设置为 1，完全断网，仅验证参数和请求规划，通知仅预览。
- 填写格式：1、true、yes、on 启用；默认 0。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：沿用青龙全局通知开关，默认启用。
- 填写格式：0、false、no、off 关闭；默认 1。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填写青龙 notify.py 所在目录；优先导入 notify，再检查此目录及青龙标准脚本目录；不可用时不改变业务退出码。
- 填写格式：目录路径，仅用于可选通知发现，不是业务依赖。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON 对象；同一账号凭据合并在 MIMOTION_ACCOUNTS，密码由 JSON 解析完整保留，不用 & 或 @ 分账号。逐账号独立处理，任一账号失败整体非零退出。

## 验证与兼容性

SHA-256 `04db959c4cfbfe05a52b98e738dfded8305111aaa467519530f03cd4bdad6513`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/04e92730d2cbeb73`。

## 副作用与风险

- 显式 upload 同步本人提供的当天健康记录并修改当天步数总量；模板中的活动、心率和睡眠等数据也一同上传。

## 许可证与来源

上游 `yuxian158/check` / `dailycheckin_scripts/ck_mimotion.py` / `723c834f121ff4eef2dec7afe521071a7efff1a9`。
