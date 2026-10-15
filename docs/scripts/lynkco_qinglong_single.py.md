# 领克App每日签到分享

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/lynkco_qinglong_single.py`
- 青龙命令：`python3 scripts/lynkco_qinglong_single.py`
- 建议 Cron：`1 2 * * *`
- 发布哈希：`1a1e794187c7a4a3fe295d5e753ee9e8e5ee85e4f9532ed11736b5a8e74e84ee`
- 许可证：`MIT`

## 脚本功能

- AppCode优先续期、HMAC签名兜底及静态令牌回退
- 今日签到状态查询、自动签到和签到后复查，已签到时跳过
- 连续签到天数和签到卡查询
- 任务前后能量体积分查询
- 五页动态文章查找及上游备用文章
- 可选文章分享两步链及完整三步链回退，核验分享前后积分变化
- 多账号独立处理、官方非秘密身份展示、任何账号失败非零退出
- 青龙及可选Bark脱敏通知，通知失败保留业务退出码
- 完全断网预演、分阶段日志和单行结构化总结
- 旧账号变量及显式只读本地配置兼容

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `LYNKCO_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人领克App合法抓取登录或刷新请求；从响应data.centerTokenDto取token或refreshToken，从同一账号刷新请求取deviceId。静态令牌通常约30分钟，刷新令牌通常约30天，以实际服务端结果为准。
- 填写格式：每个非空行一个JSON对象；token可单独使用，refreshToken必须配套deviceId，可同时配置token作续期失败回退；不以&、@分账号。

### `LYNKCO_APP_SECRETS`

- 必填：是
- 敏感：是
- 获取或设置：从本人合法取得的App配置或授权抓包获取网关签名密钥与gl_dev_id，不内置他人密钥或设备标识。旧独立变量可兼容替代对应字段。
- 填写格式：JSON对象：nativeAppKey、nativeAppSecret必需；分享或续期需glDevId；nativeAppCode用于优先AppCode续期，缺失时回退HMAC；loginAppCode仅兼容保存。

### 可选参数

### `LYNKCO_REFRESH_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容旧输入，从本人App登录响应或刷新请求取得；设置LYNKCO_ACCOUNTS后忽略旧账号变量。
- 填写格式：每行一个刷新令牌，与设备标识按行配对。

### `LYNKCO_DEVICE_ID`

- 必填：否
- 敏感：是
- 获取或设置：兼容旧输入，从本人App登录响应或刷新请求取得；设置LYNKCO_ACCOUNTS后忽略旧账号变量。
- 填写格式：每行一个同账号deviceId，不广播单个设备标识。

### `LYNKCO_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容旧输入，从本人App登录响应或刷新请求取得；设置LYNKCO_ACCOUNTS后忽略旧账号变量。
- 填写格式：每行一个静态令牌，按行配对回退；可单独使用，兼容bearer无空格前缀。

### `LYNKCO_NATIVE_APP_KEY`

- 必填：否
- 敏感：是
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：单个字符串，对应nativeAppKey；不分账号。

### `LYNKCO_NATIVE_APP_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：单个字符串，对应nativeAppSecret；不分账号。

### `LYNKCO_NATIVE_APP_CODE`

- 必填：否
- 敏感：是
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：单个字符串，对应nativeAppCode；不分账号。

### `LYNKCO_LOGIN_APP_CODE`

- 必填：否
- 敏感：是
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：单个字符串，对应loginAppCode；不分账号。

### `LYNKCO_NATIVE_GL_DEV_ID`

- 必填：否
- 敏感：是
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：单个字符串，对应glDevId；不分账号。

### `LYNKCO_DO_SHARE`

- 必填：否
- 敏感：否
- 获取或设置：按需要设置，保留原默认1。
- 填写格式：1签到并分享；0、false、no、off关闭分享。

### `LYNKCO_SHARE_MODE`

- 必填：否
- 敏感：否
- 获取或设置：按需要选择原有分享链。
- 填写格式：默认simple两步链；full完整三步链，必须设置LYNKCO_CONTENT_ID。

### `LYNKCO_CONTENT_ID`

- 必填：否
- 敏感：否
- 获取或设置：从本人App文章分享请求的contentId取得，用于完整链或两步失败回退。
- 填写格式：单个文章内容编号，不是账号凭据。

### `LYNKCO_ARTICLE_ID`

- 必填：否
- 敏感：否
- 获取或设置：从App文章页面获取articleId；不设置则保留五页动态查找和上游备用文章。
- 填写格式：单个文章编号，不是账号凭据。

### `LYNKCO_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置。
- 填写格式：请求超时秒数，默认30，范围大于0且不超过120。

### `LYNKCO_ENERGY_DELAY`

- 必填：否
- 敏感：否
- 获取或设置：按积分异步到账情况设置。
- 填写格式：积分查询等待秒数，默认5，范围0至120。

### `LYNKCO_ENV_FILE`

- 必填：否
- 敏感：是
- 获取或设置：显式兼容已有配置，不依赖外部仓库；仅只读，不回写。
- 填写格式：可选JSON文件路径，包含secrets、user；只有无账号环境输入时才使用单账号user。

### `LYNKCO_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：无网络预演时设1。
- 填写格式：默认0；1完全断网，不发送请求，不验证真实业务成功。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙全局通知开关，默认1。
- 填写格式：0、false、no、off关闭全部通知，其余开启；通知失败不改变业务退出码。

### `LYNKCO_QL_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：兼容上游青龙通知开关。
- 填写格式：默认1；0、false、no、off关闭青龙渠道，Bark仍受全局开关控制。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙已有notify.py或sendNotify.js所在目录；未设置仍探测标准路径及可导入notify模块。
- 填写格式：可选目录；预演只尝试禁止联网的Python通知，不启动Node通知。

### `LYNKCO_BARK_KEY`

- 必填：否
- 敏感：是
- 获取或设置：从本人Bark客户端取得推送Key，留空则不发送Bark。
- 填写格式：单个推送Key，仅向固定Bark服务发送脱敏总结。

### `LYNKCO_BARK_ICON`

- 必填：否
- 敏感：否
- 获取或设置：自行配置通知图标地址，可留空。
- 填写格式：可选图标URL。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号JSON对象，配套刷新令牌和设备标识合并保存；旧变量仅换行按行配对，互不广播，不用&或@分账号；独立处理，任何账号失败整体非零退出。

## 验证与兼容性

SHA-256 `1a1e794187c7a4a3fe295d5e753ee9e8e5ee85e4f9532ed11736b5a8e74e84ee`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c087eb48daa78349`。

## 副作用与风险

- 每日签到并领取服务端奖励
- 默认上报文章分享并可能增加能量体积分，可用LYNKCO_DO_SHARE关闭
- 使用刷新令牌续期，服务端可能更新登录令牌状态；不写本地凭据文件
- 发送脱敏青龙通知及可选Bark推送；预演不发送网络通知

## 许可证与来源

上游 `zhaosongbing/LynkCoHelper-QingLong` / `qinglong/lynkco_qinglong_single.py` / `7b9330aeae5e458f00de92b46bbd31bbf99c95aa`。
