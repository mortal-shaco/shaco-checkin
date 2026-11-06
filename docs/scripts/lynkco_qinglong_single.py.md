# 领克App每日签到分享

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/lynkco_qinglong_single.py`
- 青龙命令：`python3 scripts/lynkco_qinglong_single.py`
- 建议 Cron：`51 9 * * *`
- 发布哈希：`850e3773fea0dc4ecfa2d3c166f474ded8f8d12ed8dc8c80ce1488ee83f85c50`
- 许可证：`MIT`

## 脚本功能

- AppCode优先续期、HMAC签名兜底及静态令牌回退
- 今日签到状态查询、自动签到及签到后复查，已签到跳过
- 连续签到天数与签到卡查询，任务及分享前后能量体积分查询
- 五页动态文章查找及上游备用文章，可选按详情时间择新
- 文章分享两步链及完整三步链回退，严格核验分享积分增加
- 可选任务列表、成长值及官方身份查询，新增状态查询模式
- 多账号独立处理、官方非秘密身份展示、任一账号失败非零退出
- 青龙及可选Bark脱敏摘要通知，支持全局开关与选择清单，通知失败保留业务退出码
- 完全断网预演、分阶段日志及账号统计，兼容机器输出并追加单行TASK_SUMMARY
- 旧账号变量、显式只读JSON配置及签名参数兼容，无私有模块依赖

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `LYNKCO_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：从本人领克App登录或刷新请求获取centerTokenDto.token、refreshToken与同账号deviceId。
- 填写格式：每个非空行一个JSON对象；token或refreshToken至少一个，refreshToken必须配套deviceId，可同时提供token回退；凭据内其他分隔字符原样保留。

### `LYNKCO_APP_SECRETS`

- 必填：是
- 敏感：是
- 获取或设置：从本人合法获取的App配置和请求头获取原生签名参数，不提供内置密钥。
- 填写格式：JSON对象；nativeAppKey、nativeAppSecret必需，分享或续期需要glDevId；nativeAppCode可选供优先续期。兼容单项变量。

### 可选参数

### `LYNKCO_NATIVE_APP_KEY`

- 必填：否
- 敏感：是
- 获取或设置：从本人合法取得的App配置获取，兼容旧单项配置。
- 填写格式：字符串，覆盖JSON内nativeAppKey。

### `LYNKCO_NATIVE_APP_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：从本人合法取得的App配置获取，兼容旧单项配置。
- 填写格式：字符串，覆盖JSON内nativeAppSecret。

### `LYNKCO_NATIVE_APP_CODE`

- 必填：否
- 敏感：是
- 获取或设置：从本人App请求的Authorization头获取，兼容旧单项配置。
- 填写格式：AppCode字符串，不包含APPCODE前缀，覆盖JSON对应字段。

### `LYNKCO_NATIVE_GL_DEV_ID`

- 必填：否
- 敏感：是
- 获取或设置：从本人App请求头获取设备标识，兼容旧单项配置。
- 填写格式：字符串，覆盖JSON内glDevId。

### `LYNKCO_LOGIN_APP_CODE`

- 必填：否
- 敏感：是
- 获取或设置：从旧配置迁移时保留，定时任务不执行交互登录。
- 填写格式：字符串，兼容loginAppCode字段。

### `LYNKCO_CA_KEY`

- 必填：否
- 敏感：是
- 获取或设置：从本人App配置获取，兼容主来源变量。
- 填写格式：字符串，仅未配置nativeAppKey时使用。

### `LYNKCO_CA_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：从本人合法取得的App配置获取，兼容主来源变量。
- 填写格式：字符串，仅未配置nativeAppSecret时使用。

### `LYNKCO_APP_CODE`

- 必填：否
- 敏感：是
- 获取或设置：从本人App请求头获取，兼容主来源变量。
- 填写格式：字符串，仅未配置nativeAppCode时使用，不包含APPCODE前缀。

### `LYNKCO_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从本人App请求获取，建议改用规范账号变量。
- 填写格式：旧账号变量，每行一个访问令牌；存在LYNKCO_ACCOUNTS时忽略。

### `LYNKCO_REFRESH_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从本人App登录响应获取，建议改用规范账号变量。
- 填写格式：旧账号变量，每行一个刷新令牌，与设备标识按行配套。

### `LYNKCO_DEVICE_ID`

- 必填：否
- 敏感：是
- 获取或设置：从同账号App登录或刷新请求获取，建议改用规范账号变量。
- 填写格式：旧账号变量，每行一个设备标识，不广播到其他账号。

### `LYNKCO_ENV_FILE`

- 必填：否
- 敏感：是
- 获取或设置：仅迁移已有配置时显式填写；独立运行无需文件。
- 填写格式：只读JSON路径，secrets可提供签名参数；没有账号变量时可使用单个user对象，不执行Python文件，不写盘。

### `LYNKCO_DO_SHARE`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量设置分享开关。
- 填写格式：默认1，0关闭每日分享。只上报文章，不发布文本。

### `LYNKCO_SHARE_MODE`

- 必填：否
- 敏感：否
- 获取或设置：按本人分享流程选择。
- 填写格式：simple或full，默认simple；full需要内容编号，simple失败且有内容编号时回退完整三步链。

### `LYNKCO_ARTICLE_ID`

- 必填：否
- 敏感：否
- 获取或设置：从App文章分享链接的id参数获取。
- 填写格式：可选文章编号；不填先自动查找，失败使用上游备用文章。

### `LYNKCO_CONTENT_ID`

- 必填：否
- 敏感：否
- 获取或设置：从本人同一分享内容的请求中获取contentId。
- 填写格式：完整链所需内容编号。

### `LYNKCO_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置。
- 填写格式：大于0且不超过120秒，默认30。

### `LYNKCO_ENERGY_DELAY`

- 必填：否
- 敏感：否
- 获取或设置：按积分异步同步需要设置等待时长。
- 填写格式：0至120秒，默认5。

### `LYNKCO_TASK_MODE`

- 必填：否
- 敏感：否
- 获取或设置：按运行目的设置。
- 填写格式：daily或status，默认daily；status只查询积分、签到状态、连续天数、任务列表及成长值，但配置刷新令牌时仍会续期。

### `LYNKCO_QUERY_TASKS`

- 必填：否
- 敏感：否
- 获取或设置：需要查看任务列表时启用。
- 填写格式：默认0；1启用每日额外查询；status模式自动查询，不执行列表任务。

### `LYNKCO_QUERY_GROWTH`

- 必填：否
- 敏感：否
- 获取或设置：需要查看成长值时启用。
- 填写格式：默认0；1启用每日额外查询；status模式自动查询accountLevelVo.growth。

### `LYNKCO_FETCH_ACCOUNT_NAME`

- 必填：否
- 敏感：否
- 获取或设置：需要补查官方身份时启用。
- 填写格式：默认0；1启用/auth/user/info查询，失败导致该账号失败。

### `LYNKCO_LATEST_ARTICLE_LIMIT`

- 必填：否
- 敏感：否
- 获取或设置：需要按详情时间选取文章时设置。
- 填写格式：0至50整数；默认0保留五页首篇查找。正数限制详情查询篇数，详情失败保留信息流及备用链。

### `LYNKCO_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：测试时启用，正式任务关闭。
- 填写格式：1完全断网预演，默认0；检查配置、签名及阶段，不代表真实业务成功。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：选择需要通知的任务，设置后替换默认清单。
- 填写格式：逗号、分号、空白或换行分隔目录ID、脚本路径、文件名或通配符；*选全部，空值关闭全部；全局显式开关优先。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：填写青龙通知模块所在目录。
- 填写格式：可选目录，含notify.py或sendNotify.js；同时探测可导入notify和青龙标准目录。

### `LYNKCO_QL_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：兼容原有青龙通知分开关。
- 填写格式：默认1，0关闭青龙通知；仍受全局通知开关约束。

### `LYNKCO_BARK_KEY`

- 必填：否
- 敏感：是
- 获取或设置：从本人Bark客户端获取推送密钥，不用可留空。
- 填写格式：单个密钥，仅发送到固定api.day.app，预演禁止网络推送。

### `LYNKCO_BARK_ICON`

- 必填：否
- 敏感：否
- 获取或设置：自行提供非敏感图标地址。
- 填写格式：可选HTTPS图标地址。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号JSON对象，同账号token、refreshToken、deviceId合并保存；不以&或@分账号；旧变量按行配对；逐账号独立执行，任一失败整体非零退出。

## 验证与兼容性

SHA-256 `850e3773fea0dc4ecfa2d3c166f474ded8f8d12ed8dc8c80ce1488ee83f85c50`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c087eb48daa78349`。

## 副作用与风险

- 每日模式执行签到并领取服务端奖励，已签到时跳过
- 每日模式默认上报文章分享，服务端可能增加积分，可用LYNKCO_DO_SHARE关闭
- 配置刷新令牌时续期可能改变服务端登录状态，不写本地凭据文件
- 发送脱敏青龙通知及可选Bark推送；全局可关闭，预演禁止联网

## 许可证与来源

上游 `zhaosongbing/LynkCoHelper-QingLong` / `qinglong/lynkco_qinglong_single.py` / `7b9330aeae5e458f00de92b46bbd31bbf99c95aa`。
