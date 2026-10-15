# 多合一账号失效检测

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/sudojia_authcheck.js`
- 青龙命令：`node scripts/sudojia_authcheck.js`
- 建议 Cron：`10 12,21 * * *`
- 发布哈希：`cb0ac42844920cb1be7a54b04e2781ad0f330cda89176379e2f8353a87119a0c`
- 许可证：`GPL-3.0`

## 脚本功能

- 所有女生账号凭据有效性检查（兼容 ALL_GIRLS_TOKEN）
- 安慕希账号凭据有效性检查（兼容 AMX_TOKEN）
- 霸王茶姬账号凭据有效性检查（兼容 BW_TEA_TOKEN）
- 飞牛私有云账号凭据有效性检查（兼容 FN_NAS_COOKIE）
- 国乐酱酒账号凭据有效性检查（兼容 GYJ_TOKEN）
- 厚工坊账号凭据有效性检查（兼容 HGF_COOKIE）
- 海澜之家-游戏账号凭据有效性检查（兼容 HLZJ_UNID）
- 媓钻护肤品账号凭据有效性检查（兼容 HZHFP_TOKEN）
- 玩拍由我俱乐部账号凭据有效性检查（兼容 INSTAX_TOKEN）
- 金典有机生活+账号凭据有效性检查（兼容 JINDIAN_TOKEN）
- 嘉立创账号凭据有效性检查（兼容 JLC_TOKEN）
- 植白说官方商城账号凭据有效性检查（兼容 KOZBS_TOKEN）
- 开天工作室账号凭据有效性检查（兼容 KTGZS_TOKEN）
- 库街区账号凭据有效性检查（兼容 KURO_TOKEN）
- 老板电器服务微商城账号凭据有效性检查（兼容 LAOBAN_OPENID）
- 龙湖天街账号凭据有效性检查（兼容 LONG_FOR_TOKEN）
- 欣都龙城账号凭据有效性检查（兼容 MALLCOO_TOKEN）
- 馬伍旺饮料厂账号凭据有效性检查（兼容 MAWUW_TOKEN）
- 美的会员账号凭据有效性检查（兼容 MIDEA_COOKIE）
- 摩托范账号凭据有效性检查（兼容 MOTO_TOKEN）
- 南方航空账号凭据有效性检查（兼容 NFHK_COOKIE）
- 胖哥俩肉蟹煲账号凭据有效性检查（兼容 PANG_GE_TOKEN）
- 皮皮世界账号凭据有效性检查（兼容 PPX_COOKIE）
- 水费易签到账号凭据有效性检查（兼容 SHUI_FEI_COOKIE）
- 特步会员中心账号凭据有效性检查（兼容 TEBU_JSON）
- 贴吧签到账号凭据有效性检查（兼容 TIE_BA_COOKIE）
- 贴吧任务签到账号凭据有效性检查（兼容 TIE_BA_COOKIE）
- V2EX每日签到账号凭据有效性检查（兼容 V2EX_COOKIE）
- 心喜账号凭据有效性检查（兼容 XINXI_TOKEN）
- 兴攀农场账号凭据有效性检查（兼容 XPFARM_TOKEN）
- 智能电视账号凭据有效性检查（兼容 ZNDS_COOKIE）
- 甄稀冰淇淋账号凭据有效性检查（兼容 ZX_ICE_TOKEN）
- 完全断网参数预演
- 逐账号独立处理、失败及未验证非零退出
- 脱敏时间轴日志与青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `AUTH_CHECK_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在相应应用登录后，从下列兼容变量说明指定的原接口请求中获取本人凭据；只在青龙环境变量中保存，不发给他人。也可使用兼容变量代替本变量。
- 填写格式：每行一个 JSON 对象，service 为下列兼容变量名，credential 为该账号完整凭据；同一账号配套字段保存在同一个 credential 中。设置本变量时优先使用它，不再读取兼容账号变量。

### 可选参数

### `ALL_GIRLS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录所有女生，在本人 https://7.wawo.cc/api/account/wx/member/base 请求中获取authorization 请求头中 bearer 后的 token；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `AMX_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录安慕希，在本人 https://amxshop.yili.com/api/user/getUser 请求中获取accesstoken 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `BW_TEA_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录霸王茶姬，在本人 https://webapi2.qmai.cn/web/catering2-apiserver/crm/customer-center?appid=wxafec6f8422cb357b 请求中获取qm-user-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token

### `FN_NAS_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录飞牛私有云，在本人 https://club.fnnas.com 请求中获取完整 Cookie 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `GYJ_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录国乐酱酒，在本人 https://member.guoyuejiu.com/api/user/info 请求中获取Authorization 请求头完整值（保留认证前缀）；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `HGF_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录厚工坊，在本人 https://api.hgf1862.com/YUN//Game/2021/QianDao/QianDaoAjax_By28.aspx?op=now&vers= 请求中获取Cookie 中 user=SessionID= 后的会话值；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `HLZJ_UNID`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录海澜之家-游戏，在本人 https://gmdevpro.hlzjppgl.cn/server/api/authorized-login 请求中获取请求体 union_id；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `HZHFP_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录媓钻护肤品，在本人 https://servicewechat.com/wx3df7476c42cace5d/377/page-frame.html 请求中获取Authorization 请求头 Bearer 后的 token；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `INSTAX_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录玩拍由我俱乐部，在本人 https://instax.app.xcxd.net.cn/api/me 请求中获取Authorization 请求头 Bearer 后的 token；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token

### `JINDIAN_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录金典有机生活+，在本人 https://msmarket.msx.digitalyili.com/gateway/api/auth/account/user/info 请求中获取access-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `JLC_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录嘉立创，在本人 https://m.jlc.com/api/appPlatform/center/setting/selectPersonalInfo 请求中获取x-jlc-accesstoken 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `KOZBS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录植白说官方商城，在本人 https://www.kozbs.com/demo/wx/user/getUserIntegral 请求中获取x-dts-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `KTGZS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录开天工作室，在本人 https://api.box.vipinfinity.com/user 请求中获取Authorization 请求头完整值；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `KURO_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录库街区，在本人 https://api.kurobbs.com/gamer/widget/game3/refresh 请求中获取token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `LAOBAN_OPENID`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录老板电器服务微商城，在本人 https://vip.foxech.com/index.php/api/member/get_member_info 请求中获取请求体 openid；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `LONG_FOR_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录龙湖天街，在本人 https://gw2c-hw-open.longfor.com/riyuehu-miniapp-prod/service/ryh/user/info 请求中获取token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `MALLCOO_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录欣都龙城，在本人 https://m.mallcoo.cn/api/user/user/GetUserAndMallCard 请求中获取JSON 请求体 Header.Token；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `MAWUW_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录馬伍旺饮料厂，在本人 https://webapi.qmai.cn/web/catering/crm/customer-center?appid=wxc1381dc6f2213b72 请求中获取qm-user-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token

### `MIDEA_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录美的会员，在本人 https://mvip.midea.cn/next/mucuserinfo/getmucuserinfo 请求中获取完整 Cookie 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `MOTO_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录摩托范，在本人 https://api.58moto.com/user/center/info/v2/principal 请求中获取请求头 token 与请求体 uid；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：token#uid，只在首个 # 分割

### `NFHK_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录南方航空，在本人 https://wxapi.csair.com/marketing-tools/activity/join?type=APPTYPE&chanel=ss&lang=zh 请求中获取Cookie 中 sign_user_token 的值（须与 TOKEN、cs1246643sso 同属该账号）；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `PANG_GE_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录胖哥俩肉蟹煲，在本人 https://servicewechat.com/wxe61905cae01a6c7d/67/page-frame.html 请求中获取token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `PPX_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录皮皮世界，在本人 https://api.pipix.com/bds/user/user_profile/ 请求中获取Cookie 中 sessionid 的值；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `SHUI_FEI_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录水费易签到，在本人 https://m.ipaiyun.cn/PersonalCenter/PersonalCenter/GetShopMemberDetail 请求中获取请求头 Cookie 与请求体 memberId；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：Cookie#memberId，只在首个 # 分割

### `TEBU_JSON`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录特步会员中心，在本人 https://servicewechat.com/wx12e1cb3b09a0e6f0/121/page-frame.html 请求中获取完整认证请求头（JSON 对象）；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：一行一个认证请求头 JSON 对象

### `TIE_BA_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录贴吧签到，在本人 https://tieba.baidu.com/dc/common/tbs 请求中获取完整 Cookie（普通接口也接受单独 BDUSS；任务接口需要 CUID）；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `V2EX_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录V2EX每日签到，在本人 https://www.v2ex.com 请求中获取完整 Cookie 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `XINXI_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录心喜，在本人 https://api.xinc818.com/mini/user 请求中获取sso 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `XPFARM_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录兴攀农场，在本人 https://p.xpfarm.cn/treemp/user.PersonalCenter/getInfo 请求中获取authorization 请求头完整值；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `ZNDS_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录智能电视，在本人 https://www.znds.com/ 请求中获取完整 Cookie 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `ZX_ICE_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：登录甄稀冰淇淋，在本人 https://msmarket.msx.digitalyili.com/gateway/api/auth/account/user/info 请求中获取access-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：每行一个账号的完整凭据，不使用 & 或 @ 分隔账号

### `ENABLE_CHECK_TOKEN`

- 必填：否
- 敏感：否
- 获取或设置：手动设置为 true 才进行在线检查；预演无需开启
- 填写格式：true 开启；默认关闭

### `AUTH_CHECK_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：手动设置为 1
- 填写格式：1 为断网预演；默认关闭

### `AUTH_CHECK_ALLOW_MUTATIONS`

- 必填：否
- 敏感：否
- 获取或设置：仅在理解登录、刷新、同步和活动参与风险后开启；缺少成功证据的三项检查仍拒绝执行
- 填写格式：true 显式允许；默认关闭

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：使用青龙全局通知开关
- 填写格式：默认 1；0、false、no、off 关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，使用青龙已有通知模块所在目录，不安装或下载模块
- 填写格式：含 sendNotify.js 的本地目录

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每行一个账号。统一变量为一行一个 JSON 对象，配套凭据在同一个 credential 字段中；也兼容原变量按行输入。贴吧同一账号分别检查两种接口，统计按账号检查项计数。

## 验证与兼容性

SHA-256 `cb0ac42844920cb1be7a54b04e2781ad0f330cda89176379e2f8353a87119a0c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/505cfecf6964c372`。

## 副作用与风险

- 显式允许时，海澜之家游戏登录可能创建会话；已移除默认邀请人绑定
- 显式允许时，老板电器用户接口可能同步账号；请求已设置不需要同步
- 通过青龙通知模块发送脱敏汇总；断网预演仅生成通知摘要

## 许可证与来源

上游 `sudojia/AutoTaskScript` / `src/other/sudojia_authCheck.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
