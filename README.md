# shaco-checkin

通用签到类青龙脚本发布仓库。脚本经来源、许可证和基础检查后自动发布；真实账号人工核验后标记为已检查或上架。公开说明与本地「脚本管理」使用同一套状态：`待检查` / `已检查` / `上架`。

当前公开脚本 **204** 个：待检查 **199** · 已检查 **1** · 上架 **4**。详细参数、获取方法和副作用见 [`docs/scripts/`](docs/scripts/)。

## 脚本状态总览

| 管理状态 | 数量 | 含义 |
| --- | --- | --- |
| 待检查 | 199 | 已发布，但尚未完成当前版本的参数配置与本地运行核验 |
| 已检查 | 1 | 必填参数齐备且已有当前版本本地运行记录，尚未点击上架 |
| 上架 | 4 | 维护者确认保留的当前版本 |

### 待检查脚本

以下脚本可订阅，但维护者尚未完成人工核验；使用前请自行确认参数与风险。

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron | 管理状态 | 详单 |
| --- | --- | --- | --- | --- | --- |
| 139云盘云朵任务 | `scripts/139_yunduo.py` | `python3 scripts/139_yunduo.py` | `0 9 * * *` | 待检查 | [139_yunduo.py.md](docs/scripts/139_yunduo.py.md) |
| 2cycdx自动签到 | `scripts/2cycdx.py` | `python3 scripts/2cycdx.py` | `0 8 * * *` | 待检查 | [2cycdx.py.md](docs/scripts/2cycdx.py.md) |
| 51CTO博客每日签到 | `scripts/51cto_sign.js` | `node scripts/51cto_sign.js` | `0 8 * * *` | 待检查 | [51cto_sign.js.md](docs/scripts/51cto_sign.js.md) |
| 吾爱破解每日签到 | `scripts/52pojie.js` | `node scripts/52pojie.js` | `0 9 * * *` | 待检查 | [52pojie.js.md](docs/scripts/52pojie.js.md) |
| 华润通999答题 | `scripts/999.py` | `python3 scripts/999.py` | `1 1 1 1 1` | 待检查 | [999.py.md](docs/scripts/999.py.md) |
| AcFun每日任务 | `scripts/acfun.py` | `python3 scripts/acfun.py` | `0 8 * * *` | 待检查 | [acfun.py.md](docs/scripts/acfun.py.md) |
| AgentRouter签到 | `scripts/agentrouter.py` | `python3 scripts/agentrouter.py` | `20 9 * * *` | 待检查 | [agentrouter.py.md](docs/scripts/agentrouter.py.md) |
| 机场签到（速鹰666） | `scripts/airport.py` | `python3 scripts/airport.py` | `0 0 * * *` | 待检查 | [airport.py.md](docs/scripts/airport.py.md) |
| AkileCloud 签到与保活 | `scripts/akile_checkin.py` | `python3 scripts/akile_checkin.py` | `0 22 * * *` | 待检查 | [akile_checkin.py.md](docs/scripts/akile_checkin.py.md) |
| 阿里云社区 | `scripts/aliyun_web.js` | `node scripts/aliyun_web.js` | `0 7,13 * * *` | 待检查 | [aliyun_web.js.md](docs/scripts/aliyun_web.js.md) |
| 阿里云盘每日签到 | `scripts/aliyundrive_checkin.js` | `node scripts/aliyundrive_checkin.js` | `0 8 * * *` | 待检查 | [aliyundrive_checkin.js.md](docs/scripts/aliyundrive_checkin.js.md) |
| 阿里云盘签到 | `scripts/aliyunpan_checkin.py` | `python3 scripts/aliyunpan_checkin.py` | `3 11 * * *` | 待检查 | [aliyunpan_checkin.py.md](docs/scripts/aliyunpan_checkin.py.md) |
| 奥拉星每日任务与积分 | `scripts/aolaxing.py` | `python3 scripts/aolaxing.py` | `0 8 * * *` | 待检查 | [aolaxing.py.md](docs/scripts/aolaxing.py.md) |
| Hax 与 Woiden 可开通区域监控 | `scripts/api_hax.py` | `python3 scripts/api_hax.py` | `21 */6 * * *` | 待检查 | [api_hax.py.md](docs/scripts/api_hax.py.md) |
| 明日方舟寻访公告 | `scripts/arknightsbanner.py` | `python3 scripts/arknightsbanner.py` | `0 10 * * *` | 待检查 | [arknightsbanner.py.md](docs/scripts/arknightsbanner.py.md) |
| 艾特校园圈 | `scripts/atxyq.py` | `python3 scripts/atxyq.py` | `9 10,23 * * *` | 待检查 | [atxyq.py.md](docs/scripts/atxyq.py.md) |
| 上海杨浦商城定时抢购 | `scripts/auto_buy.py` | `python3 scripts/auto_buy.py` | `0 0 10 * * *` | 待检查 | [auto_buy.py.md](docs/scripts/auto_buy.py.md) |
| AutoClaw 国内版每日签到 | `scripts/autoclaw_cn_daily.py` | `python3 scripts/autoclaw_cn_daily.py` | `15 8 * * *` | 待检查 | [autoclaw_cn_daily.py.md](docs/scripts/autoclaw_cn_daily.py.md) |
| 阿里云盘签到与奖励领取 | `scripts/autosignin.js` | `node scripts/autosignin.js` | `0 9 * * *` | 待检查 | [autosignin.js.md](docs/scripts/autosignin.js.md) |
| E-Hentai 自动签到 | `scripts/autosignin.py` | `python3 scripts/autosignin.py` | `1 */6 * * *` | 待检查 | [autosignin.py.md](docs/scripts/autosignin.py.md) |
| 百度站点提交 | `scripts/baidu.py` | `python3 scripts/baidu.py` | `0 9 * * *` | 待检查 | [baidu.py.md](docs/scripts/baidu.py.md) |
| 百度网盘会员成长值 | `scripts/baiduwp.py` | `python3 scripts/baiduwp.py` | `0 8 * * *` | 待检查 | [baiduwp.py.md](docs/scripts/baiduwp.py.md) |
| B站每日任务 | `scripts/bilibili.py` | `python3 scripts/bilibili.py` | `0 0 * * *` | 待检查 | [bilibili.py.md](docs/scripts/bilibili.py.md) |
| 百事乐元抽奖 | `scripts/bsly_draw.py` | `python3 scripts/bsly_draw.py` | `0 9 * * *` | 待检查 | [bsly_draw.py.md](docs/scripts/bsly_draw.py.md) |
| 布谷TV每日签到 | `scripts/bugutv.py` | `python3 scripts/bugutv.py` | `0 8 * * *` | 待检查 | [bugutv.py.md](docs/scripts/bugutv.py.md) |
| 霸王茶姬签到 | `scripts/bwcj.py` | `python3 scripts/bwcj.py` | `0 9,18 * * *` | 待检查 | [bwcj.py.md](docs/scripts/bwcj.py.md) |
| 菜玩社区每日签到 | `scripts/caigamer.js` | `node scripts/caigamer.js` | `0 20 11 * * *` | 待检查 | [caigamer.js.md](docs/scripts/caigamer.js.md) |
| 成都地铁签到 | `scripts/cdrail.py` | `python3 scripts/cdrail.py` | `0 9 * * *` | 待检查 | [cdrail.py.md](docs/scripts/cdrail.py.md) |
| 网易云游戏每日签到 | `scripts/cg163_autocheckin.py` | `python3 scripts/cg163_autocheckin.py` | `0 8 * * *` | 待检查 | [cg163_autocheckin.py.md](docs/scripts/cg163_autocheckin.py.md) |
| 雪佛兰APP签到 | `scripts/chevrolet.js` | `node scripts/chevrolet.js` | `0 8 * * *` | 待检查 | [chevrolet.js.md](docs/scripts/chevrolet.js.md) |
| 咔叽网单签到 | `scripts/ck_2nzz.py` | `python3 scripts/ck_2nzz.py` | `30 8 * * *` | 待检查 | [ck_2nzz.py.md](docs/scripts/ck_2nzz.py.md) |
| AcFun每日签到与可选互动 | `scripts/ck_acfun.py` | `python3 scripts/ck_acfun.py` | `31 7 * * *` | 待检查 | [ck_acfun.py.md](docs/scripts/ck_acfun.py.md) |
| 机场签到 | `scripts/ck_airport.py` | `python3 scripts/ck_airport.py` | `20 10 * * *` | 待检查 | [ck_airport.py.md](docs/scripts/ck_airport.py.md) |
| 爱企查每日任务 | `scripts/ck_aqc.js` | `node scripts/ck_aqc.js` | `37 0-23/8 * * *` | 待检查 | [ck_aqc.js.md](docs/scripts/ck_aqc.js.md) |
| 百度搜索资源平台 | `scripts/ck_baidu_url_submit.py` | `python3 scripts/ck_baidu_url_submit.py` | `32 7 * * *` | 待检查 | [ck_baidu_url_submit.py.md](docs/scripts/ck_baidu_url_submit.py.md) |
| Bilibili 每日任务 | `scripts/ck_bilibili.py` | `python3 scripts/ck_bilibili.py` | `30 8 * * *` | 待检查 | [ck_bilibili.py.md](docs/scripts/ck_bilibili.py.md) |
| CCAVA每日签到 | `scripts/ck_ccava.py` | `python3 scripts/ck_ccava.py` | `55 18 * * *` | 待检查 | [ck_ccava.py.md](docs/scripts/ck_ccava.py.md) |
| CSDN签到与可选抽奖 | `scripts/ck_csdn.py` | `python3 scripts/ck_csdn.py` | `30 10 * * *` | 待检查 | [ck_csdn.py.md](docs/scripts/ck_csdn.py.md) |
| 网易蜗牛读书 | `scripts/ck_du163.js` | `node scripts/ck_du163.js` | `52 9 * * *` | 待检查 | [ck_du163.js.md](docs/scripts/ck_du163.js.md) |
| 多看阅读 | `scripts/ck_duokan.py` | `python3 scripts/ck_duokan.py` | `30 20 * * *` | 待检查 | [ck_duokan.py.md](docs/scripts/ck_duokan.py.md) |
| 时光相册每日签到 | `scripts/ck_everphoto.py` | `python3 scripts/ck_everphoto.py` | `3 22 * * *` | 待检查 | [ck_everphoto.py.md](docs/scripts/ck_everphoto.py.md) |
| Fa米家每日签到与发米粒查询 | `scripts/ck_fmapp.py` | `python3 scripts/ck_fmapp.py` | `30 14 * * *` | 待检查 | [ck_fmapp.py.md](docs/scripts/ck_fmapp.py.md) |
| FreeNom 域名续期维护 | `scripts/ck_freenom.py` | `python3 scripts/ck_freenom.py` | `25 7 */10 * *` | 待检查 | [ck_freenom.py.md](docs/scripts/ck_freenom.py.md) |
| 网易云游戏每日签到 | `scripts/ck_game163.py` | `python3 scripts/ck_game163.py` | `20 8 * * *` | 待检查 | [ck_game163.py.md](docs/scripts/ck_game163.py.md) |
| 魅族社区签到 | `scripts/ck_meizu.py` | `python3 scripts/ck_meizu.py` | `0 9 * * *` | 待检查 | [ck_meizu.py.md](docs/scripts/ck_meizu.py.md) |
| 芒果TV每日签到 | `scripts/ck_mgtv.py` | `python3 scripts/ck_mgtv.py` | `15 8 * * *` | 待检查 | [ck_mgtv.py.md](docs/scripts/ck_mgtv.py.md) |
| 小米运动 | `scripts/ck_mimotion.py` | `python3 scripts/ck_mimotion.py` | `0 20 * * *` | 待检查 | [ck_mimotion.py.md](docs/scripts/ck_mimotion.py.md) |
| 一加手机社区官方论坛 | `scripts/ck_oneplusbbs.py` | `python3 scripts/ck_oneplusbbs.py` | `0 8 * * *` | 待检查 | [ck_oneplusbbs.py.md](docs/scripts/ck_oneplusbbs.py.md) |
| CodeArts 每日福利领取 | `scripts/codearts_daily.py` | `python3 scripts/codearts_daily.py` | `15 8 * * *` | 待检查 | [codearts_daily.py.md](docs/scripts/codearts_daily.py.md) |
| ComicAI 每日签到 | `scripts/comicai_ai_cookie.py` | `python3 scripts/comicai_ai_cookie.py` | `0 9 * * *` | 待检查 | [comicai_ai_cookie.py.md](docs/scripts/comicai_ai_cookie.py.md) |
| 创想云国内站签到 | `scripts/crealitycloud_checkin.py` | `python3 scripts/crealitycloud_checkin.py` | `0 9 * * *` | 待检查 | [crealitycloud_checkin.py.md](docs/scripts/crealitycloud_checkin.py.md) |
| 大潮App签到阅读 | `scripts/dachao.py` | `python3 scripts/dachao.py` | `30 10,14,18 * * *` | 待检查 | [dachao.py.md](docs/scripts/dachao.py.md) |
| 大海资源站每日签到 | `scripts/dahai.js` | `node scripts/dahai.js` | `0 30 11 * * *` | 待检查 | [dahai.js.md](docs/scripts/dahai.js.md) |
| WPS天天领福利（可选任务中心） | `scripts/daily_benefits.py` | `python3 scripts/daily_benefits.py` | `1 1 1 1 1` | 待检查 | [daily_benefits.py.md](docs/scripts/daily_benefits.py.md) |
| 中国日报 | `scripts/dailynewscn.js` | `node scripts/dailynewscn.js` | `0 15 9 * * *` | 待检查 | [dailynewscn.js.md](docs/scripts/dailynewscn.js.md) |
| DDNSTO七天免费续费 | `scripts/ddnsto.py` | `python3 scripts/ddnsto.py` | `30 9 * * *` | 待检查 | [ddnsto.py.md](docs/scripts/ddnsto.py.md) |
| DeepFlood 签到 | `scripts/deepflood_checkin.py` | `python3 scripts/deepflood_checkin.py` | `33 14 * * *` | 待检查 | [deepflood_checkin.py.md](docs/scripts/deepflood_checkin.py.md) |
| 杜蕾斯会员中心 | `scripts/durex.py` | `python3 scripts/durex.py` | `9 9 * * *` | 待检查 | [durex.py.md](docs/scripts/durex.py.md) |
| 恩山论坛签到 | `scripts/enshan_checkin.py` | `python3 scripts/enshan_checkin.py` | `39 12 * * *` | 待检查 | [enshan_checkin.py.md](docs/scripts/enshan_checkin.py.md) |
| Epic免费游戏 | `scripts/epicfreegames.py` | `python3 scripts/epicfreegames.py` | `0 8 * * 6` | 待检查 | [epicfreegames.py.md](docs/scripts/epicfreegames.py.md) |
| 鸿星尔克签到 | `scripts/erke.py` | `python3 scripts/erke.py` | `1 1 1 1 1` | 待检查 | [erke.py.md](docs/scripts/erke.py.md) |
| 森空岛自动签到 | `scripts/f1owkang_qingskyland_skyland.py` | `python3 scripts/f1owkang_qingskyland_skyland.py` | `15 8 * * *` | 待检查 | [f1owkang_qingskyland_skyland.py.md](docs/scripts/f1owkang_qingskyland_skyland.py.md) |
| 飞牛Nas论坛签到 | `scripts/fnnasclub.py` | `python3 scripts/fnnasclub.py` | `0 8 * * *` | 待检查 | [fnnasclub.py.md](docs/scripts/fnnasclub.py.md) |
| Discuz 论坛日常维护 | `scripts/forum_download.py` | `python3 scripts/forum_download.py` | `20 8 * * *` | 待检查 | [forum_download.py.md](docs/scripts/forum_download.py.md) |
| 废文网签到 | `scripts/fwxs_checkin.js` | `node scripts/fwxs_checkin.js` | `5 8 * * *` | 待检查 | [fwxs_checkin.js.md](docs/scripts/fwxs_checkin.js.md) |
| 芬享汇每日签到 | `scripts/fxh.js` | `node scripts/fxh.js` | `0 8 * * *` | 待检查 | [fxh.js.md](docs/scripts/fxh.js.md) |
| 阴阳师官网视频与原画 | `scripts/get_yys_cgvideo.py` | `python3 scripts/get_yys_cgvideo.py` | `0 9 * * 0` | 待检查 | [get_yys_cgvideo.py.md](docs/scripts/get_yys_cgvideo.py.md) |
| 阴阳师官网原画与CG素材 | `scripts/get_yys_imagelinks.py` | `python3 scripts/get_yys_imagelinks.py` | `0 9 * * 0` | 待检查 | [get_yys_imagelinks.py.md](docs/scripts/get_yys_imagelinks.py.md) |
| HelloGitHub月刊提醒 | `scripts/hellogithub.py` | `python3 scripts/hellogithub.py` | `0 8 1 * *` | 待检查 | [hellogithub.py.md](docs/scripts/hellogithub.py.md) |
| HiFiTi与HiFiHi签到 | `scripts/hifiti_checkin.py` | `python3 scripts/hifiti_checkin.py` | `30 6 * * *` | 待检查 | [hifiti_checkin.py.md](docs/scripts/hifiti_checkin.py.md) |
| 活力伊利 | `scripts/hlyl.py` | `python3 scripts/hlyl.py` | `0 8 * * *` | 待检查 | [hlyl.py.md](docs/scripts/hlyl.py.md) |
| 沪上阿姨签到 | `scripts/hsay.py` | `python3 scripts/hsay.py` | `0 9,18 * * *` | 待检查 | [hsay.py.md](docs/scripts/hsay.py.md) |
| 华润通微信版签到 | `scripts/huaruntong_wx.py` | `python3 scripts/huaruntong_wx.py` | `1 1 1 1 1` | 待检查 | [huaruntong_wx.py.md](docs/scripts/huaruntong_wx.py.md) |
| 好游快爆游戏签到 | `scripts/hykb_gamesign.js` | `node scripts/hykb_gamesign.js` | `15 8 * * *` | 待检查 | [hykb_gamesign.js.md](docs/scripts/hykb_gamesign.js.md) |
| ikuuu 签到 | `scripts/ikuuu_checkin.py` | `python3 scripts/ikuuu_checkin.py` | `0 21 * * *` | 待检查 | [ikuuu_checkin.py.md](docs/scripts/ikuuu_checkin.py.md) |
| i茅台申购与耐力 | `scripts/imaotai.py` | `python3 scripts/imaotai.py` | `5 9 * * *` | 待检查 | [imaotai.py.md](docs/scripts/imaotai.py.md) |
| Pixiv 收藏图片下载 | `scripts/index.js` | `node scripts/index.js` | `0 3 * * *` | 待检查 | [index.js.md](docs/scripts/index.js.md) |
| 爱奇艺签到 | `scripts/iqiyi_checkin.py` | `python3 scripts/iqiyi_checkin.py` | `5 10 * * *` | 待检查 | [iqiyi_checkin.py.md](docs/scripts/iqiyi_checkin.py.md) |
| 机场面板每日签到 | `scripts/jc_checkin.py` | `python3 scripts/jc_checkin.py` | `0 8 * * *` | 待检查 | [jc_checkin.py.md](docs/scripts/jc_checkin.py.md) |
| jcqd 多站签到 | `scripts/jcqd.py` | `python3 scripts/jcqd.py` | `0 9 * * *` | 待检查 | [jcqd.py.md](docs/scripts/jcqd.py.md) |
| 精易论坛签到 | `scripts/jingyiluntan_sign.py` | `python3 scripts/jingyiluntan_sign.py` | `0 8 * * *` | 待检查 | [jingyiluntan_sign.py.md](docs/scripts/jingyiluntan_sign.py.md) |
| 杰士邦安心福利社 | `scripts/jissbon.py` | `python3 scripts/jissbon.py` | `9 9 * * *` | 待检查 | [jissbon.py.md](docs/scripts/jissbon.py.md) |
| 劲友家日常任务 | `scripts/jyj.py` | `python3 scripts/jyj.py` | `0 8 * * *` | 待检查 | [jyj.py.md](docs/scripts/jyj.py.md) |
| 看雪论坛签到 | `scripts/kanxue.js` | `node scripts/kanxue.js` | `0 35 11 * * *` | 待检查 | [kanxue.js.md](docs/scripts/kanxue.js.md) |
| 全民K歌签到与奖励 | `scripts/kgqq.py` | `python3 scripts/kgqq.py` | `0 9 * * *` | 待检查 | [kgqq.py.md](docs/scripts/kgqq.py.md) |
| 科技玩家签到 | `scripts/kjwj.py` | `python3 scripts/kjwj.py` | `30 7 * * *` | 待检查 | [kjwj.py.md](docs/scripts/kjwj.py.md) |
| KukuAI 每日积分 | `scripts/kuku_daily.py` | `python3 scripts/kuku_daily.py` | `0 8 * * *` | 待检查 | [kuku_daily.py.md](docs/scripts/kuku_daily.py.md) |
| 鸣潮·库街区 每日签到 | `scripts/kurobbs_sign.py` | `python3 scripts/kurobbs_sign.py` | `3 0 * * *` | 待检查 | [kurobbs_sign.py.md](docs/scripts/kurobbs_sign.py.md) |
| LINUX DO 登录与浏览统计 | `scripts/l.py` | `python3 scripts/l.py` | `5 */5 * * *` | 待检查 | [l.py.md](docs/scripts/l.py.md) |
| Leaflow 签到 | `scripts/leaflow_checkin_pyleaflow_checkin.py` | `python3 scripts/leaflow_checkin_pyleaflow_checkin.py` | `34 18 * * *` | 待检查 | [leaflow_checkin_pyleaflow_checkin.py.md](docs/scripts/leaflow_checkin_pyleaflow_checkin.py.md) |
| 咔叽网单每日签到 | `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py` | `python3 scripts/littlewuh_qinglongbox_dailycheckin_scripts.py` | `30 8 * * *` | 待检查 | [littlewuh_qinglongbox_dailycheckin_scripts.py.md](docs/scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md) |
| NodeSeek 签到与收益统计 | `scripts/lizhixu_ql_script_hub_nodeseek.py` | `python3 scripts/lizhixu_ql_script_hub_nodeseek.py` | `23 4 * * *` | 待检查 | [lizhixu_ql_script_hub_nodeseek.py.md](docs/scripts/lizhixu_ql_script_hub_nodeseek.py.md) |
| 有道云笔记签到 | `scripts/lizhixu_ql_script_hub_youdao.py` | `python3 scripts/lizhixu_ql_script_hub_youdao.py` | `01 5 * * *` | 待检查 | [lizhixu_ql_script_hub_youdao.py.md](docs/scripts/lizhixu_ql_script_hub_youdao.py.md) |
| LobsterAI 每日签到 | `scripts/lobsterai_checkin.py` | `python3 scripts/lobsterai_checkin.py` | `0 9 * * *` | 待检查 | [lobsterai_checkin.py.md](docs/scripts/lobsterai_checkin.py.md) |
| Loomy 每日积分与新手任务 | `scripts/loomy_daily.py` | `python3 scripts/loomy_daily.py` | `0 8 * * *` | 待检查 | [loomy_daily.py.md](docs/scripts/loomy_daily.py.md) |
| 领克App每日签到分享 | `scripts/lynkco_qinglong_single.py` | `python3 scripts/lynkco_qinglong_single.py` | `8 8 * * *` | 待检查 | [lynkco_qinglong_single.py.md](docs/scripts/lynkco_qinglong_single.py.md) |
| Wallhaven最新壁纸下载 | `scripts/main.py` | `python3 scripts/main.py` | `0 8 * * *` | 待检查 | [main.py.md](docs/scripts/main.py.md) |
| 米饭APP日常维护 | `scripts/mifan_optimized.py` | `python3 scripts/mifan_optimized.py` | `0 9 * * *` | 待检查 | [mifan_optimized.py.md](docs/scripts/mifan_optimized.py.md) |
| 小米运动账号验证与步数上传 | `scripts/mimotion.py` | `python3 scripts/mimotion.py` | `0 20 * * *` | 待检查 | [mimotion.py.md](docs/scripts/mimotion.py.md) |
| 网易云全能打卡 | `scripts/netease_task.py` | `python3 scripts/netease_task.py` | `30 9 * * *` | 待检查 | [netease_task.py.md](docs/scripts/netease_task.py.md) |
| NGA 论坛签到 | `scripts/nga_checkin.py` | `python3 scripts/nga_checkin.py` | `1 17 * * *` | 待检查 | [nga_checkin.py.md](docs/scripts/nga_checkin.py.md) |
| NodeSeek签到 | `scripts/nodeseek.py` | `python3 scripts/nodeseek.py` | `0 0 * * *` | 待检查 | [nodeseek.py.md](docs/scripts/nodeseek.py.md) |
| NodeSeek 论坛签到 | `scripts/nodeseek_checkin.py` | `python3 scripts/nodeseek_checkin.py` | `23 14 * * *` | 待检查 | [nodeseek_checkin.py.md](docs/scripts/nodeseek_checkin.py.md) |
| 塔吉多（异环）自动签到 | `scripts/nte.py` | `python3 scripts/nte.py` | `0 8 * * *` | 待检查 | [nte.py.md](docs/scripts/nte.py.md) |
| OfficeAce 果办每日奖励 | `scripts/officeace_daily.py` | `python3 scripts/officeace_daily.py` | `0 9 * * *` | 待检查 | [officeace_daily.py.md](docs/scripts/officeace_daily.py.md) |
| 华润通Ole签到 | `scripts/ole.py` | `python3 scripts/ole.py` | `1 1 1 1 1` | 待检查 | [ole.py.md](docs/scripts/ole.py.md) |
| PassNAT 签到 | `scripts/passnat_checkin.py` | `python3 scripts/passnat_checkin.py` | `18 0 * * *` | 待检查 | [passnat_checkin.py.md](docs/scripts/passnat_checkin.py.md) |
| PSNINE 每日祈祷 | `scripts/psnine.py` | `python3 scripts/psnine.py` | `0 8 * * *` | 待检查 | [psnine.py.md](docs/scripts/psnine.py.md) |
| PT 多站签到（SafeLine 兼容维护版） | `scripts/pt_sign_v5.js` | `node scripts/pt_sign_v5.js` | `0 8 * * *` | 待检查 | [pt_sign_v5.js.md](docs/scripts/pt_sign_v5.js.md) |
| Qoder每日签到 | `scripts/qoder_airscript.js` | `node scripts/qoder_airscript.js` | `17 8 * * *` | 待检查 | [qoder_airscript.js.md](docs/scripts/qoder_airscript.js.md) |
| 夸克网盘每日签到 | `scripts/quark_signin.py` | `python3 scripts/quark_signin.py` | `13 18 * * *` | 待检查 | [quark_signin.py.md](docs/scripts/quark_signin.py.md) |
| 小浣熊每日积分 | `scripts/raccoon_daily.py` | `python3 scripts/raccoon_daily.py` | `0 9 * * *` | 待检查 | [raccoon_daily.py.md](docs/scripts/raccoon_daily.py.md) |
| 雨云服务器签到 | `scripts/rainyun.py` | `python3 scripts/rainyun.py` | `0 2 * * *` | 待检查 | [rainyun.py.md](docs/scripts/rainyun.py.md) |
| Rousi 签到 | `scripts/rousi_checkin.js` | `node scripts/rousi_checkin.js` | `0 9 * * *` | 待检查 | [rousi_checkin.js.md](docs/scripts/rousi_checkin.js.md) |
| 顺丰快递积分任务 | `scripts/sf.py` | `python3 scripts/sf.py` | `1 1 1 1 1` | 待检查 | [sf.py.md](docs/scripts/sf.py.md) |
| 顺丰速运签到 | `scripts/sfsu_checkin.py` | `python3 scripts/sfsu_checkin.py` | `9 15 * * *` | 待检查 | [sfsu_checkin.py.md](docs/scripts/sfsu_checkin.py.md) |
| 申工社每日任务 | `scripts/sgs.py` | `python3 scripts/sgs.py` | `0 8 * * *` | 待检查 | [sgs.py.md](docs/scripts/sgs.py.md) |
| 书亦烧仙草签到 | `scripts/shuyi.py` | `python3 scripts/shuyi.py` | `0 9 * * *` | 待检查 | [shuyi.py.md](docs/scripts/shuyi.py.md) |
| 看雪论坛签到 | `scripts/sign_in.py` | `python3 scripts/sign_in.py` | `1 1 1 1 1` | 待检查 | [sign_in.py.md](docs/scripts/sign_in.py.md) |
| 森空岛每日任务 | `scripts/skland_daily.py` | `python3 scripts/skland_daily.py` | `0 8 * * *` | 待检查 | [skland_daily.py.md](docs/scripts/skland_daily.py.md) |
| 森空岛双游戏签到 | `scripts/skland_demo.py` | `python3 scripts/skland_demo.py` | `0 8 * * *` | 待检查 | [skland_demo.py.md](docs/scripts/skland_demo.py.md) |
| 森空岛签到 | `scripts/skyland.py` | `python3 scripts/skyland.py` | `0 8 * * *` | 待检查 | [skyland.py.md](docs/scripts/skyland.py.md) |
| 什么值得买签到 | `scripts/smzdm_checkin.js` | `node scripts/smzdm_checkin.js` | `31 8 * * *` | 待检查 | [smzdm_checkin.js.md](docs/scripts/smzdm_checkin.js.md) |
| SSL证书检查 | `scripts/ssl_cert_check.py` | `python3 scripts/ssl_cert_check.py` | `0 0 * * *` | 待检查 | [ssl_cert_check.py.md](docs/scripts/ssl_cert_check.py.md) |
| 33台词每日签到 | `scripts/sudojia_33agilestudio.js` | `node scripts/sudojia_33agilestudio.js` | `1 11 * * *` | 待检查 | [sudojia_33agilestudio.js.md](docs/scripts/sudojia_33agilestudio.js.md) |
| 所有女生会员签到 | `scripts/sudojia_allgirls.js` | `node scripts/sudojia_allgirls.js` | `19 16 * * *` | 待检查 | [sudojia_allgirls.js.md](docs/scripts/sudojia_allgirls.js.md) |
| 安慕希每日签到 | `scripts/sudojia_amx.js` | `node scripts/sudojia_amx.js` | `33 14 * * *` | 待检查 | [sudojia_amx.js.md](docs/scripts/sudojia_amx.js.md) |
| 多合一账号失效检测 | `scripts/sudojia_authcheck.js` | `node scripts/sudojia_authcheck.js` | `10 12,21 * * *` | 待检查 | [sudojia_authcheck.js.md](docs/scripts/sudojia_authcheck.js.md) |
| 香蕉视频每日任务 | `scripts/sudojia_bananavideo.js` | `node scripts/sudojia_bananavideo.js` | `10 1 * * *` | 待检查 | [sudojia_bananavideo.js.md](docs/scripts/sudojia_bananavideo.js.md) |
| 贝因美每日签到 | `scripts/sudojia_beiyinmei.js` | `node scripts/sudojia_beiyinmei.js` | `19 11 * * *` | 待检查 | [sudojia_beiyinmei.js.md](docs/scripts/sudojia_beiyinmei.js.md) |
| 植物星球 | `scripts/sudojia_botanystar.js` | `node scripts/sudojia_botanystar.js` | `32 13 * * *` | 待检查 | [sudojia_botanystar.js.md](docs/scripts/sudojia_botanystar.js.md) |
| 霸王茶姬每日签到与积分提醒 | `scripts/sudojia_bwtea.js` | `node scripts/sudojia_bwtea.js` | `22 11 * * *` | 待检查 | [sudojia_bwtea.js.md](docs/scripts/sudojia_bwtea.js.md) |
| 七彩虹商城 | `scripts/sudojia_colorful_mall.js` | `node scripts/sudojia_colorful_mall.js` | `14 12 * * *` | 待检查 | [sudojia_colorful_mall.js.md](docs/scripts/sudojia_colorful_mall.js.md) |
| 飞蚂蚁旧衣回收 | `scripts/sudojia_flyant.js` | `node scripts/sudojia_flyant.js` | `0 6 * * *` | 待检查 | [sudojia_flyant.js.md](docs/scripts/sudojia_flyant.js.md) |
| 飞牛私有云签到 | `scripts/sudojia_fnnas.js` | `node scripts/sudojia_fnnas.js` | `10 0 * * *` | 待检查 | [sudojia_fnnas.js.md](docs/scripts/sudojia_fnnas.js.md) |
| 厚工坊签到与任务 | `scripts/sudojia_hgf.js` | `node scripts/sudojia_hgf.js` | `33 5 * * *` | 待检查 | [sudojia_hgf.js.md](docs/scripts/sudojia_hgf.js.md) |
| 海澜之家-游戏 | `scripts/sudojia_hlzj_game.js` | `node scripts/sudojia_hlzj_game.js` | `39 8,15,20 * * *` | 待检查 | [sudojia_hlzj_game.js.md](docs/scripts/sudojia_hlzj_game.js.md) |
| 媓钻护肤品 | `scripts/sudojia_hzhfp.js` | `node scripts/sudojia_hzhfp.js` | `29 11 * * *` | 待检查 | [sudojia_hzhfp.js.md](docs/scripts/sudojia_hzhfp.js.md) |
| 玩拍由我俱乐部 | `scripts/sudojia_instax.js` | `node scripts/sudojia_instax.js` | `41 9 * * *` | 待检查 | [sudojia_instax.js.md](docs/scripts/sudojia_instax.js.md) |
| 江淮卡友 | `scripts/sudojia_jhcard.js` | `node scripts/sudojia_jhcard.js` | `55 5 * * *` | 待检查 | [sudojia_jhcard.js.md](docs/scripts/sudojia_jhcard.js.md) |
| 多娇江山 | `scripts/sudojia_jiangshan.js` | `node scripts/sudojia_jiangshan.js` | `26 9 * * *` | 待检查 | [sudojia_jiangshan.js.md](docs/scripts/sudojia_jiangshan.js.md) |
| 金典有机生活+ | `scripts/sudojia_jindian.js` | `node scripts/sudojia_jindian.js` | `56 7 * * *` | 待检查 | [sudojia_jindian.js.md](docs/scripts/sudojia_jindian.js.md) |
| 嘉立创硬件开源平台 | `scripts/sudojia_jlc_yj.js` | `node scripts/sudojia_jlc_yj.js` | `44 5 * * *` | 待检查 | [sudojia_jlc_yj.js.md](docs/scripts/sudojia_jlc_yj.js.md) |
| 稀土掘金每日签到 | `scripts/sudojia_juejin.js` | `node scripts/sudojia_juejin.js` | `5 10 * * *` | 待检查 | [sudojia_juejin.js.md](docs/scripts/sudojia_juejin.js.md) |
| 植白说官方商城 | `scripts/sudojia_kozbs.js` | `node scripts/sudojia_kozbs.js` | `18 9 * * *` | 待检查 | [sudojia_kozbs.js.md](docs/scripts/sudojia_kozbs.js.md) |
| 开天工作室 | `scripts/sudojia_ktgzs.js` | `node scripts/sudojia_ktgzs.js` | `33 9 * * *` | 待检查 | [sudojia_ktgzs.js.md](docs/scripts/sudojia_ktgzs.js.md) |
| 顾家家居签到 | `scripts/sudojia_kukahome.js` | `node scripts/sudojia_kukahome.js` | `5 10 * * *` | 待检查 | [sudojia_kukahome.js.md](docs/scripts/sudojia_kukahome.js.md) |
| 库街区每日签到 | `scripts/sudojia_kuro.js` | `node scripts/sudojia_kuro.js` | `22 8 * * *` | 待检查 | [sudojia_kuro.js.md](docs/scripts/sudojia_kuro.js.md) |
| 老板电器服务微商城 | `scripts/sudojia_laoban.js` | `node scripts/sudojia_laoban.js` | `15 9 * * *` | 待检查 | [sudojia_laoban.js.md](docs/scripts/sudojia_laoban.js.md) |
| 龙湖天街 | `scripts/sudojia_longfor.js` | `node scripts/sudojia_longfor.js` | `39 8 * * *` | 待检查 | [sudojia_longfor.js.md](docs/scripts/sudojia_longfor.js.md) |
| 欣都龙城每日签到 | `scripts/sudojia_mallcoo.js` | `node scripts/sudojia_mallcoo.js` | `48 10 * * *` | 待检查 | [sudojia_mallcoo.js.md](docs/scripts/sudojia_mallcoo.js.md) |
| 馬伍旺饮料厂 | `scripts/sudojia_mawuwang.js` | `node scripts/sudojia_mawuwang.js` | `48 6 * * *` | 待检查 | [sudojia_mawuwang.js.md](docs/scripts/sudojia_mawuwang.js.md) |
| 美的会员 | `scripts/sudojia_midea.js` | `node scripts/sudojia_midea.js` | `33 11 * * *` | 待检查 | [sudojia_midea.js.md](docs/scripts/sudojia_midea.js.md) |
| 蜜雪冰城每日签到 | `scripts/sudojia_mxbc.js` | `node scripts/sudojia_mxbc.js` | `28 10 * * *` | 待检查 | [sudojia_mxbc.js.md](docs/scripts/sudojia_mxbc.js.md) |
| 奈雪点单 | `scripts/sudojia_naixue.js` | `node scripts/sudojia_naixue.js` | `36 9 * * *` | 待检查 | [sudojia_naixue.js.md](docs/scripts/sudojia_naixue.js.md) |
| 雀巢会员 | `scripts/sudojia_nestle.js` | `node scripts/sudojia_nestle.js` | `28 8 * * *` | 待检查 | [sudojia_nestle.js.md](docs/scripts/sudojia_nestle.js.md) |
| 南方航空 | `scripts/sudojia_nfhk.js` | `node scripts/sudojia_nfhk.js` | `49 11 * * *` | 待检查 | [sudojia_nfhk.js.md](docs/scripts/sudojia_nfhk.js.md) |
| OPPO商城每日签到与任务领奖 | `scripts/sudojia_opposhop.js` | `node scripts/sudojia_opposhop.js` | `25 12 * * *` | 待检查 | [sudojia_opposhop.js.md](docs/scripts/sudojia_opposhop.js.md) |
| 胖哥俩肉蟹煲 | `scripts/sudojia_pangge.js` | `node scripts/sudojia_pangge.js` | `19 6 * * *` | 待检查 | [sudojia_pangge.js.md](docs/scripts/sudojia_pangge.js.md) |
| 爷爷不泡茶 | `scripts/sudojia_paotea.js` | `node scripts/sudojia_paotea.js` | `30 9 * * *` | 待检查 | [sudojia_paotea.js.md](docs/scripts/sudojia_paotea.js.md) |
| 上海杨浦 | `scripts/sudojia_shmedia.js` | `node scripts/sudojia_shmedia.js` | `33 7 * * *` | 待检查 | [sudojia_shmedia.js.md](docs/scripts/sudojia_shmedia.js.md) |
| 水费易签到 | `scripts/sudojia_shuifei.js` | `node scripts/sudojia_shuifei.js` | `3 9 * * *` | 待检查 | [sudojia_shuifei.js.md](docs/scripts/sudojia_shuifei.js.md) |
| SSPANEL面板签到 | `scripts/sudojia_sspanel.js` | `node scripts/sudojia_sspanel.js` | `35 9 * * *` | 待检查 | [sudojia_sspanel.js.md](docs/scripts/sudojia_sspanel.js.md) |
| 星妈优选 | `scripts/sudojia_starmom.js` | `node scripts/sudojia_starmom.js` | `39 2 * * *` | 待检查 | [sudojia_starmom.js.md](docs/scripts/sudojia_starmom.js.md) |
| 特步会员中心 | `scripts/sudojia_tebu.js` | `node scripts/sudojia_tebu.js` | `26 10 * * *` | 待检查 | [sudojia_tebu.js.md](docs/scripts/sudojia_tebu.js.md) |
| TILTA影像城 | `scripts/sudojia_tilta.js` | `node scripts/sudojia_tilta.js` | `5 10 * * *` | 待检查 | [sudojia_tilta.js.md](docs/scripts/sudojia_tilta.js.md) |
| 图虫每日签到 | `scripts/sudojia_tuchong.js` | `node scripts/sudojia_tuchong.js` | `38 5 * * *` | 待检查 | [sudojia_tuchong.js.md](docs/scripts/sudojia_tuchong.js.md) |
| V2EX每日签到 | `scripts/sudojia_v2ex.js` | `node scripts/sudojia_v2ex.js` | `0 9 * * *` | 待检查 | [sudojia_v2ex.js.md](docs/scripts/sudojia_v2ex.js.md) |
| 薇诺娜专柜商城 | `scripts/sudojia_wnna.js` | `node scripts/sudojia_wnna.js` | `39 9 * * *` | 待检查 | [sudojia_wnna.js.md](docs/scripts/sudojia_wnna.js.md) |
| 新湖南每日签到 | `scripts/sudojia_xhn.js` | `node scripts/sudojia_xhn.js` | `51 4 * * *` | 待检查 | [sudojia_xhn.js.md](docs/scripts/sudojia_xhn.js.md) |
| 享玩游戏APP | `scripts/sudojia_xiangwan.js` | `node scripts/sudojia_xiangwan.js` | `33 0 * * *` | 待检查 | [sudojia_xiangwan.js.md](docs/scripts/sudojia_xiangwan.js.md) |
| 小米社区-小程序 | `scripts/sudojia_xiaomi_community.js` | `node scripts/sudojia_xiaomi_community.js` | `48 9 * * *` | 待检查 | [sudojia_xiaomi_community.js.md](docs/scripts/sudojia_xiaomi_community.js.md) |
| 心喜签到 | `scripts/sudojia_xinxi.js` | `node scripts/sudojia_xinxi.js` | `43 12 * * *` | 待检查 | [sudojia_xinxi.js.md](docs/scripts/sudojia_xinxi.js.md) |
| 兴攀农场 | `scripts/sudojia_xpfarm.js` | `node scripts/sudojia_xpfarm.js` | `50 11,18 * * *` | 待检查 | [sudojia_xpfarm.js.md](docs/scripts/sudojia_xpfarm.js.md) |
| 智能电视签到 | `scripts/sudojia_znds.js` | `node scripts/sudojia_znds.js` | `5 11 * * *` | 待检查 | [sudojia_znds.js.md](docs/scripts/sudojia_znds.js.md) |
| 甄稀冰淇淋每日签到 | `scripts/sudojia_zxice.js` | `node scripts/sudojia_zxice.js` | `22 15 * * *` | 待检查 | [sudojia_zxice.js.md](docs/scripts/sudojia_zxice.js.md) |
| 微博超话签到 | `scripts/supertopicsign.py` | `python3 scripts/supertopicsign.py` | `0 8 * * *` | 待检查 | [supertopicsign.py.md](docs/scripts/supertopicsign.py.md) |
| 所有女生会员服务中心积分版 | `scripts/synspoint.py` | `python3 scripts/synspoint.py` | `8 8,12 * * *` | 待检查 | [synspoint.py.md](docs/scripts/synspoint.py.md) |
| 阿里云盘签到 | `scripts/task_ef2d3863.js` | `node scripts/task_ef2d3863.js` | `0 9,22 * * *` | 待检查 | [task_ef2d3863.js.md](docs/scripts/task_ef2d3863.js.md) |
| 腾讯视频签到 | `scripts/tencent_video_checkin.py` | `python3 scripts/tencent_video_checkin.py` | `45 9 * * *` | 待检查 | [tencent_video_checkin.py.md](docs/scripts/tencent_video_checkin.py.md) |
| 塔吉多每日任务 | `scripts/tjd_daily.py` | `python3 scripts/tjd_daily.py` | `30 9 * * *` | 待检查 | [tjd_daily.py.md](docs/scripts/tjd_daily.py.md) |
| Trae 每日签到与积分查询 | `scripts/trae_checkin.py` | `python3 scripts/trae_checkin.py` | `7,23,37 * * * *` | 待检查 | [trae_checkin.py.md](docs/scripts/trae_checkin.py.md) |
| 塔斯汀汉堡签到 | `scripts/tsthb_checkin.py` | `python3 scripts/tsthb_checkin.py` | `55 9 * * *` | 待检查 | [tsthb_checkin.py.md](docs/scripts/tsthb_checkin.py.md) |
| 天翼云盘签到 | `scripts/ty_netdisk_checkin.py` | `python3 scripts/ty_netdisk_checkin.py` | `1 16 * * *` | 待检查 | [ty_netdisk_checkin.py.md](docs/scripts/ty_netdisk_checkin.py.md) |
| 统一茄皇集市抽奖 | `scripts/tyqhdraw.py` | `python3 scripts/tyqhdraw.py` | `0 0 0 * * *` | 待检查 | [tyqhdraw.py.md](docs/scripts/tyqhdraw.py.md) |
| 掌瓦每日商店推送 | `scripts/valorantstore.py` | `python3 scripts/valorantstore.py` | `15 8 * * *` | 待检查 | [valorantstore.py.md](docs/scripts/valorantstore.py.md) |
| Vortexa 免费主机检查与领取 | `scripts/vortexa_free_claim.js` | `node scripts/vortexa_free_claim.js` | `1,11,21,31,41,51 * * * *` | 待检查 | [vortexa_free_claim.js.md](docs/scripts/vortexa_free_claim.js.md) |
| 望潮阅读有礼 | `scripts/wangchao.py` | `python3 scripts/wangchao.py` | `2 8 * * *` | 待检查 | [wangchao.py.md](docs/scripts/wangchao.py.md) |
| 华润通文体未来荟签到 | `scripts/wentiweilaihui.py` | `python3 scripts/wentiweilaihui.py` | `1 1 1 1 1` | 待检查 | [wentiweilaihui.py.md](docs/scripts/wentiweilaihui.py.md) |
| WorkBuddy签到 | `scripts/workbuddy.py` | `python3 scripts/workbuddy.py` | `30 8 * * *` | 待检查 | [workbuddy.py.md](docs/scripts/workbuddy.py.md) |
| WorkBuddy 国内版日常维护 | `scripts/workbuddy_daily.py` | `python3 scripts/workbuddy_daily.py` | `0 7,12 * * *` | 待检查 | [workbuddy_daily.py.md](docs/scripts/workbuddy_daily.py.md) |
| WPS打卡活动信息 | `scripts/wps_clock_in.py` | `python3 scripts/wps_clock_in.py` | `10 9 * * *` | 待检查 | [wps_clock_in.py.md](docs/scripts/wps_clock_in.py.md) |
| 网易云游戏自动签到 | `scripts/wyycg.py` | `python3 scripts/wyycg.py` | `0 8 * * *` | 待检查 | [wyycg.py.md](docs/scripts/wyycg.py.md) |
| 益禾堂手机点单 | `scripts/yht.py` | `python3 scripts/yht.py` | `8 6 * * *` | 待检查 | [yht.py.md](docs/scripts/yht.py.md) |
| 有道云笔记每日空间奖励 | `scripts/youdao.py` | `python3 scripts/youdao.py` | `0 8 * * *` | 待检查 | [youdao.py.md](docs/scripts/youdao.py.md) |
| 阴阳师绘卷时间获取 | `scripts/yyshuijuantime.py` | `python3 scripts/yyshuijuantime.py` | `0 0 * * *` | 待检查 | [yyshuijuantime.py.md](docs/scripts/yyshuijuantime.py.md) |
| ZCode 国内版领套餐 | `scripts/zcode_cn_daily.py` | `python3 scripts/zcode_cn_daily.py` | `0 9 * * *` | 待检查 | [zcode_cn_daily.py.md](docs/scripts/zcode_cn_daily.py.md) |
| Zippo会员中心 | `scripts/zippo.py` | `python3 scripts/zippo.py` | `9 9 * * *` | 待检查 | [zippo.py.md](docs/scripts/zippo.py.md) |
| Zodgame签到与广告任务 | `scripts/zodgame_test.py` | `python3 scripts/zodgame_test.py` | `0 8 * * *` | 待检查 | [zodgame_test.py.md](docs/scripts/zodgame_test.py.md) |

### 已检查脚本

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron | 管理状态 | 详单 |
| --- | --- | --- | --- | --- | --- |
| 摩托范每日签到 | `scripts/sudojia_moto.js` | `node scripts/sudojia_moto.js` | `33 3 * * *` | 已检查 | [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md) |

### 上架脚本

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron | 管理状态 | 详单 |
| --- | --- | --- | --- | --- | --- |
| 百度网盘签到 | `scripts/baiduwangpan_checkin.py` | `python3 scripts/baiduwangpan_checkin.py` | `0 9 * * *` | 上架 | [baiduwangpan_checkin.py.md](docs/scripts/baiduwangpan_checkin.py.md) |
| 春风动力签到 | `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `17 8 * * *` | 上架 | [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md) |
| 快手奖励任务 | `scripts/kuaishou_reward_status.py` | `python3 scripts/kuaishou_reward_status.py` | `38 8,14,20 * * *` | 上架 | [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md) |
| 百度贴吧签到 | `scripts/tieba_checkin.py` | `python3 scripts/tieba_checkin.py` | `23 8 * * *` | 上架 | [tieba_checkin.py.md](docs/scripts/tieba_checkin.py.md) |

## 青龙面板安装

进入青龙面板 → 订阅管理 → 新建订阅，按下方“订阅配置”填写，开启“自动添加任务”和“自动删除任务”，再手工运行一次订阅。青龙会根据每个脚本顶部的 `name:` / `cron:` 元数据自动创建业务任务和“本仓库依赖安装”任务；首次订阅后先运行一次依赖安装任务。也可以在脚本管理中按原路径上传单个脚本，再按“定时任务”表创建任务。

## 订阅配置

```text
名称：mortal-shaco 通用签到
类型：公开仓库
地址：https://github.com/mortal-shaco/shaco-checkin.git
分支：main
定时类型：crontab
定时规则：17 4 * * *
白名单：^scripts/.*\.(js|py|sh)$
黑名单：(^|/)(tests?|docs?|validation|shared|__pycache__)(/|$)|(^|/)(README|CHANGELOG|LICENSE)(\.|$)|(^|/)[._]
```

## 建议订阅周期

建议每天北京时间 04:17 同步：`17 4 * * *`。订阅更新与业务任务执行是两套 Cron；业务时间见下方任务表。

## 黑白名单设置

采用固定的目录级规则，不再逐个枚举脚本：白名单只同步 `scripts/` 下的 `js`、`py`、`sh` 文件，因此以后新增业务脚本无需修改订阅。黑名单进一步排除文档、测试、脱敏验证材料、`shared/` 公共组件、缓存、隐藏文件和下划线开头的辅助文件。非任务组件必须放入 `shared/`，不得放在 `scripts/`；`scripts/` 中的任务必须带青龙可识别的 `name:` / `cron:` 元数据。若面板显示“文件后缀”，填写 `js py sh`。`docs/` 仅供阅读，不会进入青龙任务同步。

## 定时任务

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron | 管理状态 | 详单 |
| --- | --- | --- | --- | --- | --- |
| 依赖安装 | `scripts/install_dependencies.sh` | `task scripts/install_dependencies.sh` | `23 4 * * 1` | 维护任务 | — |
| 139云盘云朵任务 | `scripts/139_yunduo.py` | `python3 scripts/139_yunduo.py` | `0 9 * * *` | 待检查 | [139_yunduo.py.md](docs/scripts/139_yunduo.py.md) |
| 2cycdx自动签到 | `scripts/2cycdx.py` | `python3 scripts/2cycdx.py` | `0 8 * * *` | 待检查 | [2cycdx.py.md](docs/scripts/2cycdx.py.md) |
| 51CTO博客每日签到 | `scripts/51cto_sign.js` | `node scripts/51cto_sign.js` | `0 8 * * *` | 待检查 | [51cto_sign.js.md](docs/scripts/51cto_sign.js.md) |
| 吾爱破解每日签到 | `scripts/52pojie.js` | `node scripts/52pojie.js` | `0 9 * * *` | 待检查 | [52pojie.js.md](docs/scripts/52pojie.js.md) |
| 华润通999答题 | `scripts/999.py` | `python3 scripts/999.py` | `1 1 1 1 1` | 待检查 | [999.py.md](docs/scripts/999.py.md) |
| AcFun每日任务 | `scripts/acfun.py` | `python3 scripts/acfun.py` | `0 8 * * *` | 待检查 | [acfun.py.md](docs/scripts/acfun.py.md) |
| AgentRouter签到 | `scripts/agentrouter.py` | `python3 scripts/agentrouter.py` | `20 9 * * *` | 待检查 | [agentrouter.py.md](docs/scripts/agentrouter.py.md) |
| 机场签到（速鹰666） | `scripts/airport.py` | `python3 scripts/airport.py` | `0 0 * * *` | 待检查 | [airport.py.md](docs/scripts/airport.py.md) |
| AkileCloud 签到与保活 | `scripts/akile_checkin.py` | `python3 scripts/akile_checkin.py` | `0 22 * * *` | 待检查 | [akile_checkin.py.md](docs/scripts/akile_checkin.py.md) |
| 阿里云社区 | `scripts/aliyun_web.js` | `node scripts/aliyun_web.js` | `0 7,13 * * *` | 待检查 | [aliyun_web.js.md](docs/scripts/aliyun_web.js.md) |
| 阿里云盘每日签到 | `scripts/aliyundrive_checkin.js` | `node scripts/aliyundrive_checkin.js` | `0 8 * * *` | 待检查 | [aliyundrive_checkin.js.md](docs/scripts/aliyundrive_checkin.js.md) |
| 阿里云盘签到 | `scripts/aliyunpan_checkin.py` | `python3 scripts/aliyunpan_checkin.py` | `3 11 * * *` | 待检查 | [aliyunpan_checkin.py.md](docs/scripts/aliyunpan_checkin.py.md) |
| 奥拉星每日任务与积分 | `scripts/aolaxing.py` | `python3 scripts/aolaxing.py` | `0 8 * * *` | 待检查 | [aolaxing.py.md](docs/scripts/aolaxing.py.md) |
| Hax 与 Woiden 可开通区域监控 | `scripts/api_hax.py` | `python3 scripts/api_hax.py` | `21 */6 * * *` | 待检查 | [api_hax.py.md](docs/scripts/api_hax.py.md) |
| 明日方舟寻访公告 | `scripts/arknightsbanner.py` | `python3 scripts/arknightsbanner.py` | `0 10 * * *` | 待检查 | [arknightsbanner.py.md](docs/scripts/arknightsbanner.py.md) |
| 艾特校园圈 | `scripts/atxyq.py` | `python3 scripts/atxyq.py` | `9 10,23 * * *` | 待检查 | [atxyq.py.md](docs/scripts/atxyq.py.md) |
| 上海杨浦商城定时抢购 | `scripts/auto_buy.py` | `python3 scripts/auto_buy.py` | `0 0 10 * * *` | 待检查 | [auto_buy.py.md](docs/scripts/auto_buy.py.md) |
| AutoClaw 国内版每日签到 | `scripts/autoclaw_cn_daily.py` | `python3 scripts/autoclaw_cn_daily.py` | `15 8 * * *` | 待检查 | [autoclaw_cn_daily.py.md](docs/scripts/autoclaw_cn_daily.py.md) |
| 阿里云盘签到与奖励领取 | `scripts/autosignin.js` | `node scripts/autosignin.js` | `0 9 * * *` | 待检查 | [autosignin.js.md](docs/scripts/autosignin.js.md) |
| E-Hentai 自动签到 | `scripts/autosignin.py` | `python3 scripts/autosignin.py` | `1 */6 * * *` | 待检查 | [autosignin.py.md](docs/scripts/autosignin.py.md) |
| 百度站点提交 | `scripts/baidu.py` | `python3 scripts/baidu.py` | `0 9 * * *` | 待检查 | [baidu.py.md](docs/scripts/baidu.py.md) |
| 百度网盘签到 | `scripts/baiduwangpan_checkin.py` | `python3 scripts/baiduwangpan_checkin.py` | `0 9 * * *` | 上架 | [baiduwangpan_checkin.py.md](docs/scripts/baiduwangpan_checkin.py.md) |
| 百度网盘会员成长值 | `scripts/baiduwp.py` | `python3 scripts/baiduwp.py` | `0 8 * * *` | 待检查 | [baiduwp.py.md](docs/scripts/baiduwp.py.md) |
| B站每日任务 | `scripts/bilibili.py` | `python3 scripts/bilibili.py` | `0 0 * * *` | 待检查 | [bilibili.py.md](docs/scripts/bilibili.py.md) |
| 百事乐元抽奖 | `scripts/bsly_draw.py` | `python3 scripts/bsly_draw.py` | `0 9 * * *` | 待检查 | [bsly_draw.py.md](docs/scripts/bsly_draw.py.md) |
| 布谷TV每日签到 | `scripts/bugutv.py` | `python3 scripts/bugutv.py` | `0 8 * * *` | 待检查 | [bugutv.py.md](docs/scripts/bugutv.py.md) |
| 霸王茶姬签到 | `scripts/bwcj.py` | `python3 scripts/bwcj.py` | `0 9,18 * * *` | 待检查 | [bwcj.py.md](docs/scripts/bwcj.py.md) |
| 菜玩社区每日签到 | `scripts/caigamer.js` | `node scripts/caigamer.js` | `0 20 11 * * *` | 待检查 | [caigamer.js.md](docs/scripts/caigamer.js.md) |
| 成都地铁签到 | `scripts/cdrail.py` | `python3 scripts/cdrail.py` | `0 9 * * *` | 待检查 | [cdrail.py.md](docs/scripts/cdrail.py.md) |
| 春风动力签到 | `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `17 8 * * *` | 上架 | [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md) |
| 网易云游戏每日签到 | `scripts/cg163_autocheckin.py` | `python3 scripts/cg163_autocheckin.py` | `0 8 * * *` | 待检查 | [cg163_autocheckin.py.md](docs/scripts/cg163_autocheckin.py.md) |
| 雪佛兰APP签到 | `scripts/chevrolet.js` | `node scripts/chevrolet.js` | `0 8 * * *` | 待检查 | [chevrolet.js.md](docs/scripts/chevrolet.js.md) |
| 咔叽网单签到 | `scripts/ck_2nzz.py` | `python3 scripts/ck_2nzz.py` | `30 8 * * *` | 待检查 | [ck_2nzz.py.md](docs/scripts/ck_2nzz.py.md) |
| AcFun每日签到与可选互动 | `scripts/ck_acfun.py` | `python3 scripts/ck_acfun.py` | `31 7 * * *` | 待检查 | [ck_acfun.py.md](docs/scripts/ck_acfun.py.md) |
| 机场签到 | `scripts/ck_airport.py` | `python3 scripts/ck_airport.py` | `20 10 * * *` | 待检查 | [ck_airport.py.md](docs/scripts/ck_airport.py.md) |
| 爱企查每日任务 | `scripts/ck_aqc.js` | `node scripts/ck_aqc.js` | `37 0-23/8 * * *` | 待检查 | [ck_aqc.js.md](docs/scripts/ck_aqc.js.md) |
| 百度搜索资源平台 | `scripts/ck_baidu_url_submit.py` | `python3 scripts/ck_baidu_url_submit.py` | `32 7 * * *` | 待检查 | [ck_baidu_url_submit.py.md](docs/scripts/ck_baidu_url_submit.py.md) |
| Bilibili 每日任务 | `scripts/ck_bilibili.py` | `python3 scripts/ck_bilibili.py` | `30 8 * * *` | 待检查 | [ck_bilibili.py.md](docs/scripts/ck_bilibili.py.md) |
| CCAVA每日签到 | `scripts/ck_ccava.py` | `python3 scripts/ck_ccava.py` | `55 18 * * *` | 待检查 | [ck_ccava.py.md](docs/scripts/ck_ccava.py.md) |
| CSDN签到与可选抽奖 | `scripts/ck_csdn.py` | `python3 scripts/ck_csdn.py` | `30 10 * * *` | 待检查 | [ck_csdn.py.md](docs/scripts/ck_csdn.py.md) |
| 网易蜗牛读书 | `scripts/ck_du163.js` | `node scripts/ck_du163.js` | `52 9 * * *` | 待检查 | [ck_du163.js.md](docs/scripts/ck_du163.js.md) |
| 多看阅读 | `scripts/ck_duokan.py` | `python3 scripts/ck_duokan.py` | `30 20 * * *` | 待检查 | [ck_duokan.py.md](docs/scripts/ck_duokan.py.md) |
| 时光相册每日签到 | `scripts/ck_everphoto.py` | `python3 scripts/ck_everphoto.py` | `3 22 * * *` | 待检查 | [ck_everphoto.py.md](docs/scripts/ck_everphoto.py.md) |
| Fa米家每日签到与发米粒查询 | `scripts/ck_fmapp.py` | `python3 scripts/ck_fmapp.py` | `30 14 * * *` | 待检查 | [ck_fmapp.py.md](docs/scripts/ck_fmapp.py.md) |
| FreeNom 域名续期维护 | `scripts/ck_freenom.py` | `python3 scripts/ck_freenom.py` | `25 7 */10 * *` | 待检查 | [ck_freenom.py.md](docs/scripts/ck_freenom.py.md) |
| 网易云游戏每日签到 | `scripts/ck_game163.py` | `python3 scripts/ck_game163.py` | `20 8 * * *` | 待检查 | [ck_game163.py.md](docs/scripts/ck_game163.py.md) |
| 魅族社区签到 | `scripts/ck_meizu.py` | `python3 scripts/ck_meizu.py` | `0 9 * * *` | 待检查 | [ck_meizu.py.md](docs/scripts/ck_meizu.py.md) |
| 芒果TV每日签到 | `scripts/ck_mgtv.py` | `python3 scripts/ck_mgtv.py` | `15 8 * * *` | 待检查 | [ck_mgtv.py.md](docs/scripts/ck_mgtv.py.md) |
| 小米运动 | `scripts/ck_mimotion.py` | `python3 scripts/ck_mimotion.py` | `0 20 * * *` | 待检查 | [ck_mimotion.py.md](docs/scripts/ck_mimotion.py.md) |
| 一加手机社区官方论坛 | `scripts/ck_oneplusbbs.py` | `python3 scripts/ck_oneplusbbs.py` | `0 8 * * *` | 待检查 | [ck_oneplusbbs.py.md](docs/scripts/ck_oneplusbbs.py.md) |
| CodeArts 每日福利领取 | `scripts/codearts_daily.py` | `python3 scripts/codearts_daily.py` | `15 8 * * *` | 待检查 | [codearts_daily.py.md](docs/scripts/codearts_daily.py.md) |
| ComicAI 每日签到 | `scripts/comicai_ai_cookie.py` | `python3 scripts/comicai_ai_cookie.py` | `0 9 * * *` | 待检查 | [comicai_ai_cookie.py.md](docs/scripts/comicai_ai_cookie.py.md) |
| 创想云国内站签到 | `scripts/crealitycloud_checkin.py` | `python3 scripts/crealitycloud_checkin.py` | `0 9 * * *` | 待检查 | [crealitycloud_checkin.py.md](docs/scripts/crealitycloud_checkin.py.md) |
| 大潮App签到阅读 | `scripts/dachao.py` | `python3 scripts/dachao.py` | `30 10,14,18 * * *` | 待检查 | [dachao.py.md](docs/scripts/dachao.py.md) |
| 大海资源站每日签到 | `scripts/dahai.js` | `node scripts/dahai.js` | `0 30 11 * * *` | 待检查 | [dahai.js.md](docs/scripts/dahai.js.md) |
| WPS天天领福利（可选任务中心） | `scripts/daily_benefits.py` | `python3 scripts/daily_benefits.py` | `1 1 1 1 1` | 待检查 | [daily_benefits.py.md](docs/scripts/daily_benefits.py.md) |
| 中国日报 | `scripts/dailynewscn.js` | `node scripts/dailynewscn.js` | `0 15 9 * * *` | 待检查 | [dailynewscn.js.md](docs/scripts/dailynewscn.js.md) |
| DDNSTO七天免费续费 | `scripts/ddnsto.py` | `python3 scripts/ddnsto.py` | `30 9 * * *` | 待检查 | [ddnsto.py.md](docs/scripts/ddnsto.py.md) |
| DeepFlood 签到 | `scripts/deepflood_checkin.py` | `python3 scripts/deepflood_checkin.py` | `33 14 * * *` | 待检查 | [deepflood_checkin.py.md](docs/scripts/deepflood_checkin.py.md) |
| 杜蕾斯会员中心 | `scripts/durex.py` | `python3 scripts/durex.py` | `9 9 * * *` | 待检查 | [durex.py.md](docs/scripts/durex.py.md) |
| 恩山论坛签到 | `scripts/enshan_checkin.py` | `python3 scripts/enshan_checkin.py` | `39 12 * * *` | 待检查 | [enshan_checkin.py.md](docs/scripts/enshan_checkin.py.md) |
| Epic免费游戏 | `scripts/epicfreegames.py` | `python3 scripts/epicfreegames.py` | `0 8 * * 6` | 待检查 | [epicfreegames.py.md](docs/scripts/epicfreegames.py.md) |
| 鸿星尔克签到 | `scripts/erke.py` | `python3 scripts/erke.py` | `1 1 1 1 1` | 待检查 | [erke.py.md](docs/scripts/erke.py.md) |
| 森空岛自动签到 | `scripts/f1owkang_qingskyland_skyland.py` | `python3 scripts/f1owkang_qingskyland_skyland.py` | `15 8 * * *` | 待检查 | [f1owkang_qingskyland_skyland.py.md](docs/scripts/f1owkang_qingskyland_skyland.py.md) |
| 飞牛Nas论坛签到 | `scripts/fnnasclub.py` | `python3 scripts/fnnasclub.py` | `0 8 * * *` | 待检查 | [fnnasclub.py.md](docs/scripts/fnnasclub.py.md) |
| Discuz 论坛日常维护 | `scripts/forum_download.py` | `python3 scripts/forum_download.py` | `20 8 * * *` | 待检查 | [forum_download.py.md](docs/scripts/forum_download.py.md) |
| 废文网签到 | `scripts/fwxs_checkin.js` | `node scripts/fwxs_checkin.js` | `5 8 * * *` | 待检查 | [fwxs_checkin.js.md](docs/scripts/fwxs_checkin.js.md) |
| 芬享汇每日签到 | `scripts/fxh.js` | `node scripts/fxh.js` | `0 8 * * *` | 待检查 | [fxh.js.md](docs/scripts/fxh.js.md) |
| 阴阳师官网视频与原画 | `scripts/get_yys_cgvideo.py` | `python3 scripts/get_yys_cgvideo.py` | `0 9 * * 0` | 待检查 | [get_yys_cgvideo.py.md](docs/scripts/get_yys_cgvideo.py.md) |
| 阴阳师官网原画与CG素材 | `scripts/get_yys_imagelinks.py` | `python3 scripts/get_yys_imagelinks.py` | `0 9 * * 0` | 待检查 | [get_yys_imagelinks.py.md](docs/scripts/get_yys_imagelinks.py.md) |
| HelloGitHub月刊提醒 | `scripts/hellogithub.py` | `python3 scripts/hellogithub.py` | `0 8 1 * *` | 待检查 | [hellogithub.py.md](docs/scripts/hellogithub.py.md) |
| HiFiTi与HiFiHi签到 | `scripts/hifiti_checkin.py` | `python3 scripts/hifiti_checkin.py` | `30 6 * * *` | 待检查 | [hifiti_checkin.py.md](docs/scripts/hifiti_checkin.py.md) |
| 活力伊利 | `scripts/hlyl.py` | `python3 scripts/hlyl.py` | `0 8 * * *` | 待检查 | [hlyl.py.md](docs/scripts/hlyl.py.md) |
| 沪上阿姨签到 | `scripts/hsay.py` | `python3 scripts/hsay.py` | `0 9,18 * * *` | 待检查 | [hsay.py.md](docs/scripts/hsay.py.md) |
| 华润通微信版签到 | `scripts/huaruntong_wx.py` | `python3 scripts/huaruntong_wx.py` | `1 1 1 1 1` | 待检查 | [huaruntong_wx.py.md](docs/scripts/huaruntong_wx.py.md) |
| 好游快爆游戏签到 | `scripts/hykb_gamesign.js` | `node scripts/hykb_gamesign.js` | `15 8 * * *` | 待检查 | [hykb_gamesign.js.md](docs/scripts/hykb_gamesign.js.md) |
| ikuuu 签到 | `scripts/ikuuu_checkin.py` | `python3 scripts/ikuuu_checkin.py` | `0 21 * * *` | 待检查 | [ikuuu_checkin.py.md](docs/scripts/ikuuu_checkin.py.md) |
| i茅台申购与耐力 | `scripts/imaotai.py` | `python3 scripts/imaotai.py` | `5 9 * * *` | 待检查 | [imaotai.py.md](docs/scripts/imaotai.py.md) |
| Pixiv 收藏图片下载 | `scripts/index.js` | `node scripts/index.js` | `0 3 * * *` | 待检查 | [index.js.md](docs/scripts/index.js.md) |
| 爱奇艺签到 | `scripts/iqiyi_checkin.py` | `python3 scripts/iqiyi_checkin.py` | `5 10 * * *` | 待检查 | [iqiyi_checkin.py.md](docs/scripts/iqiyi_checkin.py.md) |
| 机场面板每日签到 | `scripts/jc_checkin.py` | `python3 scripts/jc_checkin.py` | `0 8 * * *` | 待检查 | [jc_checkin.py.md](docs/scripts/jc_checkin.py.md) |
| jcqd 多站签到 | `scripts/jcqd.py` | `python3 scripts/jcqd.py` | `0 9 * * *` | 待检查 | [jcqd.py.md](docs/scripts/jcqd.py.md) |
| 精易论坛签到 | `scripts/jingyiluntan_sign.py` | `python3 scripts/jingyiluntan_sign.py` | `0 8 * * *` | 待检查 | [jingyiluntan_sign.py.md](docs/scripts/jingyiluntan_sign.py.md) |
| 杰士邦安心福利社 | `scripts/jissbon.py` | `python3 scripts/jissbon.py` | `9 9 * * *` | 待检查 | [jissbon.py.md](docs/scripts/jissbon.py.md) |
| 劲友家日常任务 | `scripts/jyj.py` | `python3 scripts/jyj.py` | `0 8 * * *` | 待检查 | [jyj.py.md](docs/scripts/jyj.py.md) |
| 看雪论坛签到 | `scripts/kanxue.js` | `node scripts/kanxue.js` | `0 35 11 * * *` | 待检查 | [kanxue.js.md](docs/scripts/kanxue.js.md) |
| 全民K歌签到与奖励 | `scripts/kgqq.py` | `python3 scripts/kgqq.py` | `0 9 * * *` | 待检查 | [kgqq.py.md](docs/scripts/kgqq.py.md) |
| 科技玩家签到 | `scripts/kjwj.py` | `python3 scripts/kjwj.py` | `30 7 * * *` | 待检查 | [kjwj.py.md](docs/scripts/kjwj.py.md) |
| 快手奖励任务 | `scripts/kuaishou_reward_status.py` | `python3 scripts/kuaishou_reward_status.py` | `38 8,14,20 * * *` | 上架 | [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md) |
| KukuAI 每日积分 | `scripts/kuku_daily.py` | `python3 scripts/kuku_daily.py` | `0 8 * * *` | 待检查 | [kuku_daily.py.md](docs/scripts/kuku_daily.py.md) |
| 鸣潮·库街区 每日签到 | `scripts/kurobbs_sign.py` | `python3 scripts/kurobbs_sign.py` | `3 0 * * *` | 待检查 | [kurobbs_sign.py.md](docs/scripts/kurobbs_sign.py.md) |
| LINUX DO 登录与浏览统计 | `scripts/l.py` | `python3 scripts/l.py` | `5 */5 * * *` | 待检查 | [l.py.md](docs/scripts/l.py.md) |
| Leaflow 签到 | `scripts/leaflow_checkin_pyleaflow_checkin.py` | `python3 scripts/leaflow_checkin_pyleaflow_checkin.py` | `34 18 * * *` | 待检查 | [leaflow_checkin_pyleaflow_checkin.py.md](docs/scripts/leaflow_checkin_pyleaflow_checkin.py.md) |
| 咔叽网单每日签到 | `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py` | `python3 scripts/littlewuh_qinglongbox_dailycheckin_scripts.py` | `30 8 * * *` | 待检查 | [littlewuh_qinglongbox_dailycheckin_scripts.py.md](docs/scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md) |
| NodeSeek 签到与收益统计 | `scripts/lizhixu_ql_script_hub_nodeseek.py` | `python3 scripts/lizhixu_ql_script_hub_nodeseek.py` | `23 4 * * *` | 待检查 | [lizhixu_ql_script_hub_nodeseek.py.md](docs/scripts/lizhixu_ql_script_hub_nodeseek.py.md) |
| 有道云笔记签到 | `scripts/lizhixu_ql_script_hub_youdao.py` | `python3 scripts/lizhixu_ql_script_hub_youdao.py` | `01 5 * * *` | 待检查 | [lizhixu_ql_script_hub_youdao.py.md](docs/scripts/lizhixu_ql_script_hub_youdao.py.md) |
| LobsterAI 每日签到 | `scripts/lobsterai_checkin.py` | `python3 scripts/lobsterai_checkin.py` | `0 9 * * *` | 待检查 | [lobsterai_checkin.py.md](docs/scripts/lobsterai_checkin.py.md) |
| Loomy 每日积分与新手任务 | `scripts/loomy_daily.py` | `python3 scripts/loomy_daily.py` | `0 8 * * *` | 待检查 | [loomy_daily.py.md](docs/scripts/loomy_daily.py.md) |
| 领克App每日签到分享 | `scripts/lynkco_qinglong_single.py` | `python3 scripts/lynkco_qinglong_single.py` | `8 8 * * *` | 待检查 | [lynkco_qinglong_single.py.md](docs/scripts/lynkco_qinglong_single.py.md) |
| Wallhaven最新壁纸下载 | `scripts/main.py` | `python3 scripts/main.py` | `0 8 * * *` | 待检查 | [main.py.md](docs/scripts/main.py.md) |
| 米饭APP日常维护 | `scripts/mifan_optimized.py` | `python3 scripts/mifan_optimized.py` | `0 9 * * *` | 待检查 | [mifan_optimized.py.md](docs/scripts/mifan_optimized.py.md) |
| 小米运动账号验证与步数上传 | `scripts/mimotion.py` | `python3 scripts/mimotion.py` | `0 20 * * *` | 待检查 | [mimotion.py.md](docs/scripts/mimotion.py.md) |
| 网易云全能打卡 | `scripts/netease_task.py` | `python3 scripts/netease_task.py` | `30 9 * * *` | 待检查 | [netease_task.py.md](docs/scripts/netease_task.py.md) |
| NGA 论坛签到 | `scripts/nga_checkin.py` | `python3 scripts/nga_checkin.py` | `1 17 * * *` | 待检查 | [nga_checkin.py.md](docs/scripts/nga_checkin.py.md) |
| NodeSeek签到 | `scripts/nodeseek.py` | `python3 scripts/nodeseek.py` | `0 0 * * *` | 待检查 | [nodeseek.py.md](docs/scripts/nodeseek.py.md) |
| NodeSeek 论坛签到 | `scripts/nodeseek_checkin.py` | `python3 scripts/nodeseek_checkin.py` | `23 14 * * *` | 待检查 | [nodeseek_checkin.py.md](docs/scripts/nodeseek_checkin.py.md) |
| 塔吉多（异环）自动签到 | `scripts/nte.py` | `python3 scripts/nte.py` | `0 8 * * *` | 待检查 | [nte.py.md](docs/scripts/nte.py.md) |
| OfficeAce 果办每日奖励 | `scripts/officeace_daily.py` | `python3 scripts/officeace_daily.py` | `0 9 * * *` | 待检查 | [officeace_daily.py.md](docs/scripts/officeace_daily.py.md) |
| 华润通Ole签到 | `scripts/ole.py` | `python3 scripts/ole.py` | `1 1 1 1 1` | 待检查 | [ole.py.md](docs/scripts/ole.py.md) |
| PassNAT 签到 | `scripts/passnat_checkin.py` | `python3 scripts/passnat_checkin.py` | `18 0 * * *` | 待检查 | [passnat_checkin.py.md](docs/scripts/passnat_checkin.py.md) |
| PSNINE 每日祈祷 | `scripts/psnine.py` | `python3 scripts/psnine.py` | `0 8 * * *` | 待检查 | [psnine.py.md](docs/scripts/psnine.py.md) |
| PT 多站签到（SafeLine 兼容维护版） | `scripts/pt_sign_v5.js` | `node scripts/pt_sign_v5.js` | `0 8 * * *` | 待检查 | [pt_sign_v5.js.md](docs/scripts/pt_sign_v5.js.md) |
| Qoder每日签到 | `scripts/qoder_airscript.js` | `node scripts/qoder_airscript.js` | `17 8 * * *` | 待检查 | [qoder_airscript.js.md](docs/scripts/qoder_airscript.js.md) |
| 夸克网盘每日签到 | `scripts/quark_signin.py` | `python3 scripts/quark_signin.py` | `13 18 * * *` | 待检查 | [quark_signin.py.md](docs/scripts/quark_signin.py.md) |
| 小浣熊每日积分 | `scripts/raccoon_daily.py` | `python3 scripts/raccoon_daily.py` | `0 9 * * *` | 待检查 | [raccoon_daily.py.md](docs/scripts/raccoon_daily.py.md) |
| 雨云服务器签到 | `scripts/rainyun.py` | `python3 scripts/rainyun.py` | `0 2 * * *` | 待检查 | [rainyun.py.md](docs/scripts/rainyun.py.md) |
| Rousi 签到 | `scripts/rousi_checkin.js` | `node scripts/rousi_checkin.js` | `0 9 * * *` | 待检查 | [rousi_checkin.js.md](docs/scripts/rousi_checkin.js.md) |
| 顺丰快递积分任务 | `scripts/sf.py` | `python3 scripts/sf.py` | `1 1 1 1 1` | 待检查 | [sf.py.md](docs/scripts/sf.py.md) |
| 顺丰速运签到 | `scripts/sfsu_checkin.py` | `python3 scripts/sfsu_checkin.py` | `9 15 * * *` | 待检查 | [sfsu_checkin.py.md](docs/scripts/sfsu_checkin.py.md) |
| 申工社每日任务 | `scripts/sgs.py` | `python3 scripts/sgs.py` | `0 8 * * *` | 待检查 | [sgs.py.md](docs/scripts/sgs.py.md) |
| 书亦烧仙草签到 | `scripts/shuyi.py` | `python3 scripts/shuyi.py` | `0 9 * * *` | 待检查 | [shuyi.py.md](docs/scripts/shuyi.py.md) |
| 看雪论坛签到 | `scripts/sign_in.py` | `python3 scripts/sign_in.py` | `1 1 1 1 1` | 待检查 | [sign_in.py.md](docs/scripts/sign_in.py.md) |
| 森空岛每日任务 | `scripts/skland_daily.py` | `python3 scripts/skland_daily.py` | `0 8 * * *` | 待检查 | [skland_daily.py.md](docs/scripts/skland_daily.py.md) |
| 森空岛双游戏签到 | `scripts/skland_demo.py` | `python3 scripts/skland_demo.py` | `0 8 * * *` | 待检查 | [skland_demo.py.md](docs/scripts/skland_demo.py.md) |
| 森空岛签到 | `scripts/skyland.py` | `python3 scripts/skyland.py` | `0 8 * * *` | 待检查 | [skyland.py.md](docs/scripts/skyland.py.md) |
| 什么值得买签到 | `scripts/smzdm_checkin.js` | `node scripts/smzdm_checkin.js` | `31 8 * * *` | 待检查 | [smzdm_checkin.js.md](docs/scripts/smzdm_checkin.js.md) |
| SSL证书检查 | `scripts/ssl_cert_check.py` | `python3 scripts/ssl_cert_check.py` | `0 0 * * *` | 待检查 | [ssl_cert_check.py.md](docs/scripts/ssl_cert_check.py.md) |
| 33台词每日签到 | `scripts/sudojia_33agilestudio.js` | `node scripts/sudojia_33agilestudio.js` | `1 11 * * *` | 待检查 | [sudojia_33agilestudio.js.md](docs/scripts/sudojia_33agilestudio.js.md) |
| 所有女生会员签到 | `scripts/sudojia_allgirls.js` | `node scripts/sudojia_allgirls.js` | `19 16 * * *` | 待检查 | [sudojia_allgirls.js.md](docs/scripts/sudojia_allgirls.js.md) |
| 安慕希每日签到 | `scripts/sudojia_amx.js` | `node scripts/sudojia_amx.js` | `33 14 * * *` | 待检查 | [sudojia_amx.js.md](docs/scripts/sudojia_amx.js.md) |
| 多合一账号失效检测 | `scripts/sudojia_authcheck.js` | `node scripts/sudojia_authcheck.js` | `10 12,21 * * *` | 待检查 | [sudojia_authcheck.js.md](docs/scripts/sudojia_authcheck.js.md) |
| 香蕉视频每日任务 | `scripts/sudojia_bananavideo.js` | `node scripts/sudojia_bananavideo.js` | `10 1 * * *` | 待检查 | [sudojia_bananavideo.js.md](docs/scripts/sudojia_bananavideo.js.md) |
| 贝因美每日签到 | `scripts/sudojia_beiyinmei.js` | `node scripts/sudojia_beiyinmei.js` | `19 11 * * *` | 待检查 | [sudojia_beiyinmei.js.md](docs/scripts/sudojia_beiyinmei.js.md) |
| 植物星球 | `scripts/sudojia_botanystar.js` | `node scripts/sudojia_botanystar.js` | `32 13 * * *` | 待检查 | [sudojia_botanystar.js.md](docs/scripts/sudojia_botanystar.js.md) |
| 霸王茶姬每日签到与积分提醒 | `scripts/sudojia_bwtea.js` | `node scripts/sudojia_bwtea.js` | `22 11 * * *` | 待检查 | [sudojia_bwtea.js.md](docs/scripts/sudojia_bwtea.js.md) |
| 七彩虹商城 | `scripts/sudojia_colorful_mall.js` | `node scripts/sudojia_colorful_mall.js` | `14 12 * * *` | 待检查 | [sudojia_colorful_mall.js.md](docs/scripts/sudojia_colorful_mall.js.md) |
| 飞蚂蚁旧衣回收 | `scripts/sudojia_flyant.js` | `node scripts/sudojia_flyant.js` | `0 6 * * *` | 待检查 | [sudojia_flyant.js.md](docs/scripts/sudojia_flyant.js.md) |
| 飞牛私有云签到 | `scripts/sudojia_fnnas.js` | `node scripts/sudojia_fnnas.js` | `10 0 * * *` | 待检查 | [sudojia_fnnas.js.md](docs/scripts/sudojia_fnnas.js.md) |
| 厚工坊签到与任务 | `scripts/sudojia_hgf.js` | `node scripts/sudojia_hgf.js` | `33 5 * * *` | 待检查 | [sudojia_hgf.js.md](docs/scripts/sudojia_hgf.js.md) |
| 海澜之家-游戏 | `scripts/sudojia_hlzj_game.js` | `node scripts/sudojia_hlzj_game.js` | `39 8,15,20 * * *` | 待检查 | [sudojia_hlzj_game.js.md](docs/scripts/sudojia_hlzj_game.js.md) |
| 媓钻护肤品 | `scripts/sudojia_hzhfp.js` | `node scripts/sudojia_hzhfp.js` | `29 11 * * *` | 待检查 | [sudojia_hzhfp.js.md](docs/scripts/sudojia_hzhfp.js.md) |
| 玩拍由我俱乐部 | `scripts/sudojia_instax.js` | `node scripts/sudojia_instax.js` | `41 9 * * *` | 待检查 | [sudojia_instax.js.md](docs/scripts/sudojia_instax.js.md) |
| 江淮卡友 | `scripts/sudojia_jhcard.js` | `node scripts/sudojia_jhcard.js` | `55 5 * * *` | 待检查 | [sudojia_jhcard.js.md](docs/scripts/sudojia_jhcard.js.md) |
| 多娇江山 | `scripts/sudojia_jiangshan.js` | `node scripts/sudojia_jiangshan.js` | `26 9 * * *` | 待检查 | [sudojia_jiangshan.js.md](docs/scripts/sudojia_jiangshan.js.md) |
| 金典有机生活+ | `scripts/sudojia_jindian.js` | `node scripts/sudojia_jindian.js` | `56 7 * * *` | 待检查 | [sudojia_jindian.js.md](docs/scripts/sudojia_jindian.js.md) |
| 嘉立创硬件开源平台 | `scripts/sudojia_jlc_yj.js` | `node scripts/sudojia_jlc_yj.js` | `44 5 * * *` | 待检查 | [sudojia_jlc_yj.js.md](docs/scripts/sudojia_jlc_yj.js.md) |
| 稀土掘金每日签到 | `scripts/sudojia_juejin.js` | `node scripts/sudojia_juejin.js` | `5 10 * * *` | 待检查 | [sudojia_juejin.js.md](docs/scripts/sudojia_juejin.js.md) |
| 植白说官方商城 | `scripts/sudojia_kozbs.js` | `node scripts/sudojia_kozbs.js` | `18 9 * * *` | 待检查 | [sudojia_kozbs.js.md](docs/scripts/sudojia_kozbs.js.md) |
| 开天工作室 | `scripts/sudojia_ktgzs.js` | `node scripts/sudojia_ktgzs.js` | `33 9 * * *` | 待检查 | [sudojia_ktgzs.js.md](docs/scripts/sudojia_ktgzs.js.md) |
| 顾家家居签到 | `scripts/sudojia_kukahome.js` | `node scripts/sudojia_kukahome.js` | `5 10 * * *` | 待检查 | [sudojia_kukahome.js.md](docs/scripts/sudojia_kukahome.js.md) |
| 库街区每日签到 | `scripts/sudojia_kuro.js` | `node scripts/sudojia_kuro.js` | `22 8 * * *` | 待检查 | [sudojia_kuro.js.md](docs/scripts/sudojia_kuro.js.md) |
| 老板电器服务微商城 | `scripts/sudojia_laoban.js` | `node scripts/sudojia_laoban.js` | `15 9 * * *` | 待检查 | [sudojia_laoban.js.md](docs/scripts/sudojia_laoban.js.md) |
| 龙湖天街 | `scripts/sudojia_longfor.js` | `node scripts/sudojia_longfor.js` | `39 8 * * *` | 待检查 | [sudojia_longfor.js.md](docs/scripts/sudojia_longfor.js.md) |
| 欣都龙城每日签到 | `scripts/sudojia_mallcoo.js` | `node scripts/sudojia_mallcoo.js` | `48 10 * * *` | 待检查 | [sudojia_mallcoo.js.md](docs/scripts/sudojia_mallcoo.js.md) |
| 馬伍旺饮料厂 | `scripts/sudojia_mawuwang.js` | `node scripts/sudojia_mawuwang.js` | `48 6 * * *` | 待检查 | [sudojia_mawuwang.js.md](docs/scripts/sudojia_mawuwang.js.md) |
| 美的会员 | `scripts/sudojia_midea.js` | `node scripts/sudojia_midea.js` | `33 11 * * *` | 待检查 | [sudojia_midea.js.md](docs/scripts/sudojia_midea.js.md) |
| 摩托范每日签到 | `scripts/sudojia_moto.js` | `node scripts/sudojia_moto.js` | `33 3 * * *` | 已检查 | [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md) |
| 蜜雪冰城每日签到 | `scripts/sudojia_mxbc.js` | `node scripts/sudojia_mxbc.js` | `28 10 * * *` | 待检查 | [sudojia_mxbc.js.md](docs/scripts/sudojia_mxbc.js.md) |
| 奈雪点单 | `scripts/sudojia_naixue.js` | `node scripts/sudojia_naixue.js` | `36 9 * * *` | 待检查 | [sudojia_naixue.js.md](docs/scripts/sudojia_naixue.js.md) |
| 雀巢会员 | `scripts/sudojia_nestle.js` | `node scripts/sudojia_nestle.js` | `28 8 * * *` | 待检查 | [sudojia_nestle.js.md](docs/scripts/sudojia_nestle.js.md) |
| 南方航空 | `scripts/sudojia_nfhk.js` | `node scripts/sudojia_nfhk.js` | `49 11 * * *` | 待检查 | [sudojia_nfhk.js.md](docs/scripts/sudojia_nfhk.js.md) |
| OPPO商城每日签到与任务领奖 | `scripts/sudojia_opposhop.js` | `node scripts/sudojia_opposhop.js` | `25 12 * * *` | 待检查 | [sudojia_opposhop.js.md](docs/scripts/sudojia_opposhop.js.md) |
| 胖哥俩肉蟹煲 | `scripts/sudojia_pangge.js` | `node scripts/sudojia_pangge.js` | `19 6 * * *` | 待检查 | [sudojia_pangge.js.md](docs/scripts/sudojia_pangge.js.md) |
| 爷爷不泡茶 | `scripts/sudojia_paotea.js` | `node scripts/sudojia_paotea.js` | `30 9 * * *` | 待检查 | [sudojia_paotea.js.md](docs/scripts/sudojia_paotea.js.md) |
| 上海杨浦 | `scripts/sudojia_shmedia.js` | `node scripts/sudojia_shmedia.js` | `33 7 * * *` | 待检查 | [sudojia_shmedia.js.md](docs/scripts/sudojia_shmedia.js.md) |
| 水费易签到 | `scripts/sudojia_shuifei.js` | `node scripts/sudojia_shuifei.js` | `3 9 * * *` | 待检查 | [sudojia_shuifei.js.md](docs/scripts/sudojia_shuifei.js.md) |
| SSPANEL面板签到 | `scripts/sudojia_sspanel.js` | `node scripts/sudojia_sspanel.js` | `35 9 * * *` | 待检查 | [sudojia_sspanel.js.md](docs/scripts/sudojia_sspanel.js.md) |
| 星妈优选 | `scripts/sudojia_starmom.js` | `node scripts/sudojia_starmom.js` | `39 2 * * *` | 待检查 | [sudojia_starmom.js.md](docs/scripts/sudojia_starmom.js.md) |
| 特步会员中心 | `scripts/sudojia_tebu.js` | `node scripts/sudojia_tebu.js` | `26 10 * * *` | 待检查 | [sudojia_tebu.js.md](docs/scripts/sudojia_tebu.js.md) |
| TILTA影像城 | `scripts/sudojia_tilta.js` | `node scripts/sudojia_tilta.js` | `5 10 * * *` | 待检查 | [sudojia_tilta.js.md](docs/scripts/sudojia_tilta.js.md) |
| 图虫每日签到 | `scripts/sudojia_tuchong.js` | `node scripts/sudojia_tuchong.js` | `38 5 * * *` | 待检查 | [sudojia_tuchong.js.md](docs/scripts/sudojia_tuchong.js.md) |
| V2EX每日签到 | `scripts/sudojia_v2ex.js` | `node scripts/sudojia_v2ex.js` | `0 9 * * *` | 待检查 | [sudojia_v2ex.js.md](docs/scripts/sudojia_v2ex.js.md) |
| 薇诺娜专柜商城 | `scripts/sudojia_wnna.js` | `node scripts/sudojia_wnna.js` | `39 9 * * *` | 待检查 | [sudojia_wnna.js.md](docs/scripts/sudojia_wnna.js.md) |
| 新湖南每日签到 | `scripts/sudojia_xhn.js` | `node scripts/sudojia_xhn.js` | `51 4 * * *` | 待检查 | [sudojia_xhn.js.md](docs/scripts/sudojia_xhn.js.md) |
| 享玩游戏APP | `scripts/sudojia_xiangwan.js` | `node scripts/sudojia_xiangwan.js` | `33 0 * * *` | 待检查 | [sudojia_xiangwan.js.md](docs/scripts/sudojia_xiangwan.js.md) |
| 小米社区-小程序 | `scripts/sudojia_xiaomi_community.js` | `node scripts/sudojia_xiaomi_community.js` | `48 9 * * *` | 待检查 | [sudojia_xiaomi_community.js.md](docs/scripts/sudojia_xiaomi_community.js.md) |
| 心喜签到 | `scripts/sudojia_xinxi.js` | `node scripts/sudojia_xinxi.js` | `43 12 * * *` | 待检查 | [sudojia_xinxi.js.md](docs/scripts/sudojia_xinxi.js.md) |
| 兴攀农场 | `scripts/sudojia_xpfarm.js` | `node scripts/sudojia_xpfarm.js` | `50 11,18 * * *` | 待检查 | [sudojia_xpfarm.js.md](docs/scripts/sudojia_xpfarm.js.md) |
| 智能电视签到 | `scripts/sudojia_znds.js` | `node scripts/sudojia_znds.js` | `5 11 * * *` | 待检查 | [sudojia_znds.js.md](docs/scripts/sudojia_znds.js.md) |
| 甄稀冰淇淋每日签到 | `scripts/sudojia_zxice.js` | `node scripts/sudojia_zxice.js` | `22 15 * * *` | 待检查 | [sudojia_zxice.js.md](docs/scripts/sudojia_zxice.js.md) |
| 微博超话签到 | `scripts/supertopicsign.py` | `python3 scripts/supertopicsign.py` | `0 8 * * *` | 待检查 | [supertopicsign.py.md](docs/scripts/supertopicsign.py.md) |
| 所有女生会员服务中心积分版 | `scripts/synspoint.py` | `python3 scripts/synspoint.py` | `8 8,12 * * *` | 待检查 | [synspoint.py.md](docs/scripts/synspoint.py.md) |
| 阿里云盘签到 | `scripts/task_ef2d3863.js` | `node scripts/task_ef2d3863.js` | `0 9,22 * * *` | 待检查 | [task_ef2d3863.js.md](docs/scripts/task_ef2d3863.js.md) |
| 腾讯视频签到 | `scripts/tencent_video_checkin.py` | `python3 scripts/tencent_video_checkin.py` | `45 9 * * *` | 待检查 | [tencent_video_checkin.py.md](docs/scripts/tencent_video_checkin.py.md) |
| 百度贴吧签到 | `scripts/tieba_checkin.py` | `python3 scripts/tieba_checkin.py` | `23 8 * * *` | 上架 | [tieba_checkin.py.md](docs/scripts/tieba_checkin.py.md) |
| 塔吉多每日任务 | `scripts/tjd_daily.py` | `python3 scripts/tjd_daily.py` | `30 9 * * *` | 待检查 | [tjd_daily.py.md](docs/scripts/tjd_daily.py.md) |
| Trae 每日签到与积分查询 | `scripts/trae_checkin.py` | `python3 scripts/trae_checkin.py` | `7,23,37 * * * *` | 待检查 | [trae_checkin.py.md](docs/scripts/trae_checkin.py.md) |
| 塔斯汀汉堡签到 | `scripts/tsthb_checkin.py` | `python3 scripts/tsthb_checkin.py` | `55 9 * * *` | 待检查 | [tsthb_checkin.py.md](docs/scripts/tsthb_checkin.py.md) |
| 天翼云盘签到 | `scripts/ty_netdisk_checkin.py` | `python3 scripts/ty_netdisk_checkin.py` | `1 16 * * *` | 待检查 | [ty_netdisk_checkin.py.md](docs/scripts/ty_netdisk_checkin.py.md) |
| 统一茄皇集市抽奖 | `scripts/tyqhdraw.py` | `python3 scripts/tyqhdraw.py` | `0 0 0 * * *` | 待检查 | [tyqhdraw.py.md](docs/scripts/tyqhdraw.py.md) |
| 掌瓦每日商店推送 | `scripts/valorantstore.py` | `python3 scripts/valorantstore.py` | `15 8 * * *` | 待检查 | [valorantstore.py.md](docs/scripts/valorantstore.py.md) |
| Vortexa 免费主机检查与领取 | `scripts/vortexa_free_claim.js` | `node scripts/vortexa_free_claim.js` | `1,11,21,31,41,51 * * * *` | 待检查 | [vortexa_free_claim.js.md](docs/scripts/vortexa_free_claim.js.md) |
| 望潮阅读有礼 | `scripts/wangchao.py` | `python3 scripts/wangchao.py` | `2 8 * * *` | 待检查 | [wangchao.py.md](docs/scripts/wangchao.py.md) |
| 华润通文体未来荟签到 | `scripts/wentiweilaihui.py` | `python3 scripts/wentiweilaihui.py` | `1 1 1 1 1` | 待检查 | [wentiweilaihui.py.md](docs/scripts/wentiweilaihui.py.md) |
| WorkBuddy签到 | `scripts/workbuddy.py` | `python3 scripts/workbuddy.py` | `30 8 * * *` | 待检查 | [workbuddy.py.md](docs/scripts/workbuddy.py.md) |
| WorkBuddy 国内版日常维护 | `scripts/workbuddy_daily.py` | `python3 scripts/workbuddy_daily.py` | `0 7,12 * * *` | 待检查 | [workbuddy_daily.py.md](docs/scripts/workbuddy_daily.py.md) |
| WPS打卡活动信息 | `scripts/wps_clock_in.py` | `python3 scripts/wps_clock_in.py` | `10 9 * * *` | 待检查 | [wps_clock_in.py.md](docs/scripts/wps_clock_in.py.md) |
| 网易云游戏自动签到 | `scripts/wyycg.py` | `python3 scripts/wyycg.py` | `0 8 * * *` | 待检查 | [wyycg.py.md](docs/scripts/wyycg.py.md) |
| 益禾堂手机点单 | `scripts/yht.py` | `python3 scripts/yht.py` | `8 6 * * *` | 待检查 | [yht.py.md](docs/scripts/yht.py.md) |
| 有道云笔记每日空间奖励 | `scripts/youdao.py` | `python3 scripts/youdao.py` | `0 8 * * *` | 待检查 | [youdao.py.md](docs/scripts/youdao.py.md) |
| 阴阳师绘卷时间获取 | `scripts/yyshuijuantime.py` | `python3 scripts/yyshuijuantime.py` | `0 0 * * *` | 待检查 | [yyshuijuantime.py.md](docs/scripts/yyshuijuantime.py.md) |
| ZCode 国内版领套餐 | `scripts/zcode_cn_daily.py` | `python3 scripts/zcode_cn_daily.py` | `0 9 * * *` | 待检查 | [zcode_cn_daily.py.md](docs/scripts/zcode_cn_daily.py.md) |
| Zippo会员中心 | `scripts/zippo.py` | `python3 scripts/zippo.py` | `9 9 * * *` | 待检查 | [zippo.py.md](docs/scripts/zippo.py.md) |
| Zodgame签到与广告任务 | `scripts/zodgame_test.py` | `python3 scripts/zodgame_test.py` | `0 8 * * *` | 待检查 | [zodgame_test.py.md](docs/scripts/zodgame_test.py.md) |

依赖安装任务会读取本仓库的 `requirements.txt`、`package-lock.json` 或 `package.json`；没有额外依赖时安全退出，不会执行远程安装脚本。

## 脚本功能

完整功能列表写在各脚本详单。下面仅保留导航摘要：

- `scripts/139_yunduo.py`（待检查）：标准库实现完整SSO与JWT认证链，展示官方返回的非敏感账号身份；获取执行前后AI豆余额；检查当日签到状态并执行每日签到，验证返回结果。完整说明见 [139_yunduo.py.md](docs/scripts/139_yunduo.py.md)。
- `scripts/2cycdx.py`（待检查）：获取论坛签到页面及 formhash 登录参数。；每天 08:00 签到领取贡献，明确识别签到成功和今日已签到。；逐行多账号独立处理，任一账号失败返回非零退出码。。完整说明见 [2cycdx.py.md](docs/scripts/2cycdx.py.md)。
- `scripts/51cto_sign.js`（待检查）：账号密码登录并同步博客会话；获取签到Token并沿用原始MD5接口签名；查询每日签到状态，已经签到时避免重复提交。完整说明见 [51cto_sign.js.md](docs/scripts/51cto_sign.js.md)。
- `scripts/52pojie.js`（待检查）：每日 9 点吾爱破解签到，保留上游地址、PUT 方法和浏览器请求头。；判断签到成功、已签到、登录失效、HTTP 异常和未知响应，失败闭合。；支持 UTF-8 和 GBK 系列网页编码，逐行多账号 Cookie 和旧变量别名。。完整说明见 [52pojie.js.md](docs/scripts/52pojie.js.md)。
- `scripts/999.py`（待检查）：按原接口获取华润通999题目；展示题目、选项和接口标记的正确答案；支持单选或多选正确选项并提交答案。完整说明见 [999.py.md](docs/scripts/999.py.md)。
- `scripts/acfun.py`（待检查）：手机号密码登录及多账号独立执行；每日签到及等级、香蕉余额查询；显示官方返回的非秘密昵称、用户名或公开用户标识。完整说明见 [acfun.py.md](docs/scripts/acfun.py.md)。
- `scripts/agentrouter.py`（待检查）：通过 GitHub OAuth 重新登录触发每日签到，以服务端 checked_in 严格确认为成功。；查询并展示官方账号身份、当前余额美元换算及已用额度。；保留站点公开客户端配置、已知客户端编号和额度换算比例兜底。。完整说明见 [agentrouter.py.md](docs/scripts/agentrouter.py.md)。
- `scripts/airport.py`（待检查）：使用邮箱和密码登录速鹰666，保留原有登录地址与表单字段。；每日签到并核验明确的业务成功结果；明确已签到结果视为已完成。；查询剩余流量，保留原 XPath 与 originBody Base64 页面解码及原始页面回退。。完整说明见 [airport.py.md](docs/scripts/airport.py.md)。
- `scripts/akile_checkin.py`（待检查）：AK 币签到，先查今日流水以避免重复提交，提交后复核实际流水。；查询余额、今日所得、连续天数与累计签到收益，分页校准及增量同步。；显式开启 Token 保活，验证新凭据后唯一匹配回写青龙多行变量。。完整说明见 [akile_checkin.py.md](docs/scripts/akile_checkin.py.md)。
- `scripts/aliyun_web.js`（待检查）：查询官方账号昵称、用户名或公开 UID 及当前积分和待领取积分；按原定时与早晚分界执行社区签到、核对签到奖励资格并领取奖励；解析官网现行积分任务目录，对不支持的任务提示手动完成。完整说明见 [aliyun_web.js.md](docs/scripts/aliyun_web.js.md)。
- `scripts/aliyundrive_checkin.js`（待检查）：通过刷新令牌获取访问令牌并展示官方返回的昵称、用户名或公开用户标识；每日签到并展示本月累计签到天数；领取当日奖励并识别已领取状态。完整说明见 [aliyundrive_checkin.js.md](docs/scripts/aliyundrive_checkin.js.md)。
- `scripts/aliyunpan_checkin.py`（待检查）：刷新登录凭据并识别令牌轮换，全程不输出凭据；查询官方公开身份与存储容量；查询失败继续签到与领奖，最终非零退出；每日签到并输出本月累计签到天数。完整说明见 [aliyunpan_checkin.py.md](docs/scripts/aliyunpan_checkin.py.md)。
- `scripts/aolaxing.py`（待检查）：查询每日任务列表、今日任务总数及完成数。；按显式指定任务 ID 执行未完成任务，执行后重新读取列表核验已完成状态；已完成任务不重复执行。；查询当前积分、累计获得积分和累计签到次数。。完整说明见 [aolaxing.py.md](docs/scripts/aolaxing.py.md)。
- `scripts/api_hax.py`（待检查）：查询并按地区汇总 Hax 开通数量。；按虚拟化类型分组展示 Hax 可开通区域及开通页面链接。；展示 Woiden 可开通区域及开通页面链接。。完整说明见 [api_hax.py.md](docs/scripts/api_hax.py.md)。
- `scripts/arknightsbanner.py`（待检查）：每天 10 点监控明日方舟官方寻访公告，无需游戏账号；无第三方业务依赖。；扫描 LATEST 至末页或最多 50 页；ACTIVITY 前 5 页兜底，整页已知时停止，按公告标识去重并按发布时间排序。；逐条抓取公告正文，不依赖标题或摘要预筛；移除脚本与健康提示页脚后识别卡池出率关键词。。完整说明见 [arknightsbanner.py.md](docs/scripts/arknightsbanner.py.md)。
- `scripts/atxyq.py`（待检查）：查询并直接展示官方昵称，查询学校启用状态与积分任务列表。；每日签到，核验连续天数与获得积分。；领取普通任务奖励，保持上游排除新用户奖励、集赞有奖、发布任务和邀请有奖。。完整说明见 [atxyq.py.md](docs/scripts/atxyq.py.md)。
- `scripts/auto_buy.py`（待检查）：按任务开关独立运行商城定时抢购或积分任务，保留商城默认入口、参数和计划；指定商品、数量、活动编号和促销类型抢购，支持完整日期、时分秒或立即执行；商城明确业务拒绝后按配置次数和间隔重试，未知结果停止重试并提示核对订单。完整说明见 [auto_buy.py.md](docs/scripts/auto_buy.py.md)。
- `scripts/autoclaw_cn_daily.py`（待检查）：国内版每日签到及积分奖励结果显示，明确业务码及成功标记校验；登录态过期后自动续期并重试签到，签名校验失败时使用 agent-refresh 备用接口；无明确领取结果时只读查询任务清单用于诊断，不将诊断冒充领取成功。完整说明见 [autoclaw_cn_daily.py.md](docs/scripts/autoclaw_cn_daily.py.md)。
- `scripts/autosignin.js`（待检查）：刷新并验证登录令牌，显示官方返回的非凭据账号身份。；每天 9 点执行签到并显示当月累计签到天数。；领取当天已完成的每日签到奖励和每日任务奖励，展示领取结果；未完成及已结束奖励明确跳过。。完整说明见 [autosignin.js.md](docs/scripts/autosignin.js.md)。
- `scripts/autosignin.py`（待检查）：访问 E-Hentai 新闻页完成签到，并核验事件区明确奖励或今日已完成提示；识别随机遭遇，提示手动处理或等待结束；未确认签到时非零退出；保留默认 TLS 三次请求及 TLS 1.2 三次回退，设置超时、响应大小限制与证书校验。完整说明见 [autosignin.py.md](docs/scripts/autosignin.py.md)。
- `scripts/baidu.py`（待检查）：下载并校验本站 UTF-8 URL 清单；调用百度站点提交接口并核验 success 与 remain，输出成功条数和剩余配额；支持显式设置重复提交次数，默认仅提交一次。完整说明见 [baidu.py.md](docs/scripts/baidu.py.md)。
- `scripts/baiduwangpan_checkin.py`（上架）：每日百度网盘会员签到，明确验证积分或已完成状态；获取并提交每日会员成长问题答案；读取并报告脱敏用户名、会员等级、成长值和会员类型。完整说明见 [baiduwangpan_checkin.py.md](docs/scripts/baiduwangpan_checkin.py.md)。
- `scripts/baiduwp.py`（待检查）：会员成长值签到并报告获得成长值；获取每日题目并提交官方返回的答案，报告答题成长值；查询当前会员等级和成长值。完整说明见 [baiduwp.py.md](docs/scripts/baiduwp.py.md)。
- `scripts/bilibili.py`（待检查）：验证登录并显示官方返回昵称、公开 UID 和硬币余额；漫画签到及重复签到识别；热门视频来源和排行榜备用来源。完整说明见 [bilibili.py.md](docs/scripts/bilibili.py.md)。
- `scripts/bsly_draw.py`（待检查）：百事乐元抽奖，保留原 GET 接口、Token、User-Agent 和微信 Referer 请求头。；每行多账号及旧账号字段兼容，保留 User-Agent 内的 #，账号独立处理。；显式开启抽奖及每账号可配置次数上限，数字业务码 0 和有效奖品名称双重校验。。完整说明见 [bsly_draw.py.md](docs/scripts/bsly_draw.py.md)。
- `scripts/bugutv.py`（待检查）：使用用户名及密码登录布谷TV，校验官方登录成功消息；每日签到，区分签到成功与今日已签到，拒绝未确认的业务结果；查询签到前后积分并展示本次增量与累计积分，支持小数积分。完整说明见 [bugutv.py.md](docs/scripts/bugutv.py.md)。
- `scripts/bwcj.py`（待检查）：读取并展示官方非秘密账号身份，禁止输出手机号和凭据。；读取积分流水获取签到用户 ID，支持同账号手动补充用户 ID 并核验一致性。；查询新版签到天数，使用上游签名算法执行新版签到并核验业务状态和奖励明细。。完整说明见 [bwcj.py.md](docs/scripts/bwcj.py.md)。
- `scripts/caigamer.js`（待检查）：每日签到，保留原有每天 11:20 调度和 Cookie 参数名；显示官方非敏感账号身份及签到名次、连续签到天数和奖励的安全字段；明确成功及今日已签到判定，未知业务结果失败闭合。完整说明见 [caigamer.js.md](docs/scripts/caigamer.js.md)。
- `scripts/cdrail.py`（待检查）：每日签到与积分增量展示；基于明确业务码确认签到成功或今日已签到；每行一个账号，支持 JSON、查询字符串及自定义请求头。完整说明见 [cdrail.py.md](docs/scripts/cdrail.py.md)。
- `scripts/cfmoto_checkin.py`（上架）：执行每日签到；发帖和评论优先使用接口随机文本，返回出处时拼接作者与作品信息，接口异常时使用本地文案兜底；按配置发布帖子、评论、点赞并完成分享积分任务。完整说明见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/cg163_autocheckin.py`（待检查）：校验网易云游戏账号凭据；执行每日签到并核验业务成功标志；显示官方响应中的昵称、用户名、显示名称或公开 UID。完整说明见 [cg163_autocheckin.py.md](docs/scripts/cg163_autocheckin.py.md)。
- `scripts/chevrolet.js`（待检查）：雪佛兰 APP 每日签到，保留上游接口、POST 方法及 cpctoken 请求头参数。；每行一个账号，兼容上游 xflCookie，独立处理并汇总账号结果。；完全断网预演，检查参数及执行流程，不把预演标为业务签到成功。。完整说明见 [chevrolet.js.md](docs/scripts/chevrolet.js.md)。
- `scripts/ck_2nzz.py`（待检查）：使用登录 Cookie 获取签到令牌，保留原签到接口路径、请求方法和表单字段。；查询并直接显示官方页面返回的公开 UID。；执行每日签到，区分明确成功、明确已完成与失败；混合已签到或时间未开始提示不判成功。。完整说明见 [ck_2nzz.py.md](docs/scripts/ck_2nzz.py.md)。
- `scripts/ck_acfun.py`（待检查）：独立实现手机号密码登录及多账号处理，不依赖原仓库工具。；保留每天 7:31 调度，默认签到与等级、香蕉余额查询。；按需获取排行榜视频和互动令牌。。完整说明见 [ck_acfun.py.md](docs/scripts/ck_acfun.py.md)。
- `scripts/ck_airport.py`（待检查）：使用机场邮箱和密码登录 SSPanel，正确编码表单并维护会话 Cookie。；每日签到，仅明确 ret=1 或明确今日已签到业务响应判定成功。；查询 editXY 主题的用户等级、到期时间和剩余流量；主题不支持的字段明确跳过。。完整说明见 [ck_airport.py.md](docs/scripts/ck_airport.py.md)。
- `scripts/ck_aqc.js`（待检查）：登录状态核验及官方非敏感账号身份展示；热搜词获取与账号独立查询词库；每日签到、每日登录与任务进度复核。完整说明见 [ck_aqc.js.md](docs/scripts/ck_aqc.js.md)。
- `scripts/ck_baidu_url_submit.py`（待检查）：按原每日 07:32 计划获取 UTF-8 URL 列表并向百度推送本站 URL；支持多站点独立执行及显式重复推送次数，统计接受条数、成功次数、失败次数与剩余配额；保留 data_url、submit_url、times 字段和 BAIDU 数组兼容输入。完整说明见 [ck_baidu_url_submit.py.md](docs/scripts/ck_baidu_url_submit.py.md)。
- `scripts/ck_bilibili.py`（待检查）：登录状态验证并显示官方昵称及公开 UID；漫画客户端签到与重复签到识别；直播签到与重复签到识别。完整说明见 [ck_bilibili.py.md](docs/scripts/ck_bilibili.py.md)。
- `scripts/ck_ccava.py`（待检查）：每日签到，保留每天 18:55 的上游计划；显示签到响应中有效的月光币余额；识别今天已签到和失效凭据，未知响应不视为成功。完整说明见 [ck_ccava.py.md](docs/scripts/ck_ccava.py.md)。
- `scripts/ck_csdn.py`（待检查）：每日签到，保留上游每天 10:30 的执行时间；通过 CSDN_DRAW 显式启用签到后的抽奖；每行一个 Cookie 的多账号独立处理，保留 Cookie 值中的等号。完整说明见 [ck_csdn.py.md](docs/scripts/ck_csdn.py.md)。
- `scripts/ck_du163.js`（待检查）：网易蜗牛读书每日签到，保留上游接口、表单字段及每日 09:52 定时；支持 Cookie 中提取 _xsrf 和逐账号可选 User-Agent；业务码 0 确认签到成功，并展示有效的连续签到天数。完整说明见 [ck_du163.js.md](docs/scripts/ck_du163.js.md)。
- `scripts/ck_duokan.py`（待检查）：每日签到，保留上游时间戳与设备字段校验算法。；查询当前书豆总量、各批次数量、到期日期和可延期状态。；可选延长符合条件的书豆有效期。。完整说明见 [ck_duokan.py.md](docs/scripts/ck_duokan.py.md)。
- `scripts/ck_everphoto.py`（待检查）：使用手机号与密码字段值登录时光相册；执行每日签到并区分首次签到与今日已签到；显示接口返回的累积签到天数及非敏感账号身份。完整说明见 [ck_everphoto.py.md](docs/scripts/ck_everphoto.py.md)。
- `scripts/ck_fmapp.py`（待检查）：每日 App 签到并显示下一次及累计签到发米粒奖励信息；查询并原样显示官方返回的非敏感账号昵称；查询发米粒余额。完整说明见 [ck_fmapp.py.md](docs/scripts/ck_fmapp.py.md)。
- `scripts/ck_freenom.py`（待检查）：独立实现 HTTPS 登录并验证官方已登录状态；查询域名距续期天数并判断不足 14 天的续期窗口；显式启用后执行 12 个月免费续期并复核天数增加。完整说明见 [ck_freenom.py.md](docs/scripts/ck_freenom.py.md)。
- `scripts/ck_game163.py`（待检查）：每日网易云游戏签到，保留每天 08:20 的计划和原请求路径、POST 方法及请求头格式。；换行多账号及原 authorization 字段配置兼容，各账号独立处理。；标准库实现 HTTPS 请求，设置超时、响应大小上限并拒绝跳转。。完整说明见 [ck_game163.py.md](docs/scripts/ck_game163.py.md)。
- `scripts/ck_meizu.py`（待检查）：每日社区签到及今日已签到识别，无法确认的响应按失败处理。；查询并显示官方返回的公开 UID；接口返回昵称、用户名或显示名称时一并显示。；显式设置次数后执行活动编号 2 的连续抽奖，保留五秒间隔及逐次奖励结果，默认不抽奖。。完整说明见 [ck_meizu.py.md](docs/scripts/ck_meizu.py.md)。
- `scripts/ck_mgtv.py`（待检查）：查询官方账号信息并显示返回的非敏感昵称；每日签到领取积分，显示签到积分及累计签到天数；保留原始查询串字段与 JSONP 回调，自动刷新请求时间戳。完整说明见 [ck_mgtv.py.md](docs/scripts/ck_mgtv.py.md)。
- `scripts/ck_mimotion.py`（待检查）：华米手机号密码登录、校验账号与应用令牌，显示官方返回的非敏感昵称、用户名或公开 UID。；显式上传本人当天模板并随机修改步数总量，保留 min_step/max_step 参数名及原默认范围。；每行一个账号，独立执行，失败闭合退出。。完整说明见 [ck_mimotion.py.md](docs/scripts/ck_mimotion.py.md)。
- `scripts/ck_oneplusbbs.py`（待检查）：论坛每日签到，识别官方成功或今日已签到结果；显式开启后最多十次抽奖，统计确认奖励、消耗及净加油；一言签到文字及作者来源署名，异常时回退本地文字。完整说明见 [ck_oneplusbbs.py.md](docs/scripts/ck_oneplusbbs.py.md)。
- `scripts/codearts_daily.py`（待检查）：读取和只读预览福利活动（--preview 不续期、不写台账）；领取 USER_LOGIN 信用积分与一次性 NEW_USER_REGISTER 注册礼；领取、确认后同源回读，仅 CONFIRMED/CONSUMED 且不可再领取算到账。完整说明见 [codearts_daily.py.md](docs/scripts/codearts_daily.py.md)。
- `scripts/comicai_ai_cookie.py`（待检查）：可选 Cookie 登录页访问，保留原流程但不将页面 HTTP 200 当作认证成功；查询签到前积分并展示签到成功响应中的签到后积分；每日签到与已签到业务码识别。完整说明见 [comicai_ai_cookie.py.md](docs/scripts/comicai_ai_cookie.py.md)。
- `scripts/crealitycloud_checkin.py`（待检查）：国内站手机号或邮箱密码登录，手机号自动补 86 区号；直接登录态失效后的 OAuth 授权码登录回退；查询今日签到状态，已签到时避免重复操作。完整说明见 [crealitycloud_checkin.py.md](docs/scripts/crealitycloud_checkin.py.md)。
- `scripts/dachao.py`（待检查）：账号密码登录及官方昵称展示；动态发现签到和阅读活动；签到及已签到状态判断。完整说明见 [dachao.py.md](docs/scripts/dachao.py.md)。
- `scripts/dahai.js`（待检查）：每天 11:30 使用登录 Cookie 签到；显示连续签到天数；显示官方返回的非敏感昵称、用户名、显示名称或公开 UID。完整说明见 [dahai.js.md](docs/scripts/dahai.js.md)。
- `scripts/daily_benefits.py`（待检查）：按优先级合并双营销渠道，自动发现福利中心入口并查询活动页面；免费会员打卡、服务端签到日期和连续签到天数核对，提交后刷新核验今日状态；显式开启后可在服务端明确返回系列失效时重开签到系列一次。完整说明见 [daily_benefits.py.md](docs/scripts/daily_benefits.py.md)。
- `scripts/dailynewscn.js`（待检查）：DAILYNEWSCN_TASK=dailynewscn：获取、校验、输出并通知中国日报；保留 DAILYNEWSCN_LIST、DAILYNEWSCN_SUCCESS；同文件另建任务，定时 0 15 9 * * *。；DAILYNEWSCN_TASK=bdhot：获取、校验、输出并通知百度热搜榜；保留 BDHOT_LIST、BDHOT_SUCCESS；同文件另建任务，定时 0 0 9 * * *。；DAILYNEWSCN_TASK=chouq：获取、校验、输出并通知随机抽签；保留 CHOUQ_LIST、CHOUQ_SUCCESS；同文件另建任务，定时 0 10 9 * * *。。完整说明见 [dailynewscn.js.md](docs/scripts/dailynewscn.js.md)。
- `scripts/ddnsto.py`（待检查）：申请 product_id=2 七天免费套餐并查询订单；把新套餐绑定到指定路由器；重新读取官方套餐并确认到期时间延长后才报告续费成功；识别本周免费套餐申请次数限制；只有现有套餐尚未过期才视为已完成。完整说明见 [ddnsto.py.md](docs/scripts/ddnsto.py.md)。
- `scripts/deepflood_checkin.py`（待检查）：执行 DeepFlood 每日签到并验证接口业务结果，支持识别已完成签到；查询并汇总可配置时间窗口内的签到鸡腿收益，保留总量、次数及平均收益；支持换行分隔的多账号独立执行和汇总状态。完整说明见 [deepflood_checkin.py.md](docs/scripts/deepflood_checkin.py.md)。
- `scripts/durex.py`（待检查）：查询并直接显示官方昵称与当前积分；每日签到；显式开启活动分享记录上报（不发布文本）。完整说明见 [durex.py.md](docs/scripts/durex.py.md)。
- `scripts/enshan_checkin.py`（待检查）：使用 Cookie 验证登录，保留签到页 WAF 解码、论坛页回退和响应 Cookie 更新。；获取隐藏字段、退出链接或 JavaScript 中的 formhash，提交每日签到，严格识别成功及今日已签到。；在已验证的签到响应提供连续签到天数时展示天数，并在结构化账号结果中输出；未提供时不推测。。完整说明见 [enshan_checkin.py.md](docs/scripts/enshan_checkin.py.md)。
- `scripts/epicfreegames.py`（待检查）：查询 Epic 本周及即将免费游戏，仅筛选有效基础游戏和零价促销。；展示游戏标题、原价、促销起止北京时间及商店链接，兼容语言地区和国家设置。；合成含封面、标题、原价及免费时间的图片并发送到 Telegram；封面失败保留资料卡片，图片生成或发送失败降级完整文字报告。。完整说明见 [epicfreegames.py.md](docs/scripts/epicfreegames.py.md)。
- `scripts/erke.py`（待检查）：查询积分明细第一页五条，展示累计积分、冻结积分、可用积分和积分记录数；会员签到及明确已签到状态识别；每行一个账号，保留上游账号字段兼容，逐账号与逐阶段统计。完整说明见 [erke.py.md](docs/scripts/erke.py.md)。
- `scripts/f1owkang_qingskyland_skyland.py`（待检查）：鹰角登录 token 换取森空岛认证凭据，独立实现设备认证与 HTTP 签名；查询明日方舟与终末地绑定账号，逐一签到全部角色并显示官方昵称或公开 UID、渠道及奖励；支持每行一个账号、官方 JSON 凭据、可选凭据文件与合并去重。完整说明见 [f1owkang_qingskyland_skyland.py.md](docs/scripts/f1owkang_qingskyland_skyland.py.md)。
- `scripts/fnnasclub.py`（待检查）：显示论坛提供的公开昵称；获取签到参数并执行每日签到；识别今日已打卡并避免重复签到。完整说明见 [fnnasclub.py.md](docs/scripts/fnnasclub.py.md)。
- `scripts/forum_download.py`（待检查）：读取指定版块的主题列表，并按上游顺序读取前三个帖子的附件；下载显式启用，不保存文件，间隔两秒。；访问论坛首页并验证登录状态，不把首页访问成功推断为奖励到账。；提供 dsu_paulsign 和 qiandao.php 两种显式签到开关，保留原端点、方法、签到参数和已签到判断。。完整说明见 [forum_download.py.md](docs/scripts/forum_download.py.md)。
- `scripts/fwxs_checkin.js`（待检查）：登录有效性检查并展示官方公开 UID；废文网每日签到；以个人中心总签到天数增长确认成功；查询总签到天数与连续签到天数；明确的北京时间当天签到记录支持已签到判定。完整说明见 [fwxs_checkin.js.md](docs/scripts/fwxs_checkin.js.md)。
- `scripts/fxh.js`（待检查）：每日查询当前积分；每日执行芬享汇签到，显示可解析的奖励积分与已签到状态；官方返回非敏感昵称、用户名、显示名称或公开 UID 时直接展示。完整说明见 [fxh.js.md](docs/scripts/fxh.js.md)。
- `scripts/get_yys_cgvideo.py`（待检查）：官网 CG 视频目录解析、按标题去重；显式开启后的媒体下载和校验清单；新增下载数量限制及视频下载成功后两秒间隔。完整说明见 [get_yys_cgvideo.py.md](docs/scripts/get_yys_cgvideo.py.md)。
- `scripts/get_yys_imagelinks.py`（待检查）：读取阴阳师官网原画页面，保留首个 tab-cont 内六个链接的第三个原画链接选择规则。；默认仅核验并列出素材；显式开启后保存原画，保留数字路径命名与原画目录默认值，修复未知文件名及同名碰撞。；通过任务开关读取全部官网 CG 视频分组，保存标题命名的 MP4 视频并记录 downloaded_videos.txt 标题历史。。完整说明见 [get_yys_imagelinks.py.md](docs/scripts/get_yys_imagelinks.py.md)。
- `scripts/hellogithub.py`（待检查）：每月 1 日 08:00 查询 HelloGitHub 最新月刊及发布时间；比较持久化期号，跳过已经提醒的月刊；动态提取页面构建标识并读取完整分类项目内容。完整说明见 [hellogithub.py.md](docs/scripts/hellogithub.py.md)。
- `scripts/hifiti_checkin.py`（待检查）：HiFiTi 每日签到与明确业务结果核验；HiFiHi 每日签到与明确业务结果核验；兼容原凭据参数和旧版值格式，完整 Cookie 不截断。完整说明见 [hifiti_checkin.py.md](docs/scripts/hifiti_checkin.py.md)。
- `scripts/hlyl.py`（待检查）：查询账号信息，展示接口提供的非敏感公开身份，屏蔽手机号和凭据；查询当日签到状态、周任务进度和月签到天数；每日签到，已签到时跳过；签到后复查状态并显示可用积分和成长积分奖励。完整说明见 [hlyl.py.md](docs/scripts/hlyl.py.md)。
- `scripts/hsay.py`（待检查）：查询并显示官方返回的用户昵称，隐藏手机号及凭据；从积分流水获取签到所需的公开用户 ID；查询连续签到天数。完整说明见 [hsay.py.md](docs/scripts/hsay.py.md)。
- `scripts/huaruntong_wx.py`（待检查）：华润通微信版加密签到，仅以官方业务码 S0A00000 确认成功；兼容原签到请求全部可配置参数及默认值，保持原 cron；逐行多账号独立执行、参数校验和失败非零退出。完整说明见 [huaruntong_wx.py.md](docs/scripts/huaruntong_wx.py.md)。
- `scripts/hykb_gamesign.js`（待检查）：发现官方游戏签到集合中未结束的活动并去重，无法解析时失败闭合。；逐活动登录并每日签到，明确识别签到成功及今日已签，返回累计签到天数时显示。；可选择记录试玩前置动作，真实运行等待 65 秒后重新登录、签到并核验结果。。完整说明见 [hykb_gamesign.js.md](docs/scripts/hykb_gamesign.js.md)。
- `scripts/ikuuu_checkin.py`（待检查）：保留邮箱密码登录与官方 ret=1 核验，兼容 IKUUU_ACCOUNT 和旧 ikuuu 参数；新增 Cookie 会话签到，支持 IKUUU_COOKIES、备注前缀及同一规范账号变量中的 Cookie 输入；每日签到要求官方 ret=1 或明确的今日已签到证明，成功说明中提取流量奖励。完整说明见 [ikuuu_checkin.py.md](docs/scripts/ikuuu_checkin.py.md)。
- `scripts/imaotai.py`（待检查）：查询官方应用版本、当日北京时间场次及门店资源；按经纬度选择最近有库存门店，或按省市选择库存最多门店；支持多个商品，保留原默认商品列表。完整说明见 [imaotai.py.md](docs/scripts/imaotai.py.md)。
- `scripts/index.js`（待检查）：通过官方收藏页跳转获取并原样显示公开 UID，也支持手动指定公开 UID；分页获取全部公开收藏，校验明确业务成功、总数稳定、无重复以及分页完整性；读取每个作品全部原图页；图片页查询与图片下载分别限制为三个并发任务。完整说明见 [index.js.md](docs/scripts/index.js.md)。
- `scripts/iqiyi_checkin.py`（待检查）：VIP信息、官方身份、会员等级、到期时间及成长值查询；自然月签到、连签天数及已签到识别；网页积分签到及逐项业务确认。完整说明见 [iqiyi_checkin.py.md](docs/scripts/iqiyi_checkin.py.md)。
- `scripts/jc_checkin.py`（待检查）：初始化会话并使用邮箱密码登录机场面板；每日签到及严格业务结果校验；逐行多账号及上游单账号参数兼容。完整说明见 [jc_checkin.py.md](docs/scripts/jc_checkin.py.md)。
- `scripts/jcqd.py`（待检查）：默认 ikuuu 官方导航域名发现、登录及每日签到；通过明确任务开关保留上游可选 v2free 和 gw树洞登录签到，各站独立会话；多账号逐行配置、旧单账号参数兼容、账号及站点失败隔离。完整说明见 [jcqd.py.md](docs/scripts/jcqd.py.md)。
- `scripts/jingyiluntan_sign.py`（待检查）：读取登录页面与表单令牌，显示官方返回的昵称；每日签到并区分成功和今日已签到；显式开启后按上游流程读取热门帖、逐帖评分 +1 和显示积分，保持两秒间隔。完整说明见 [jingyiluntan_sign.py.md](docs/scripts/jingyiluntan_sign.py.md)。
- `scripts/jissbon.py`（待检查）：查询官方昵称与当前积分；每日签到；分享奖励登记，不发布分享文字。完整说明见 [jissbon.py.md](docs/scripts/jissbon.py.md)。
- `scripts/jyj.py`（待检查）：查询官方昵称及可用积分、历史使用和历史总积分；每日签到和每日水滴领取；显式开启三轮拍一拍实际计时游戏和三次幸运转盘。完整说明见 [jyj.py.md](docs/scripts/jyj.py.md)。
- `scripts/kanxue.js`（待检查）：使用完整 Cookie 执行看雪论坛每日签到，保持上游环境变量、请求地址和每日 11:35 计划。；支持每行一个账号，独立执行并汇总各账号结果。；核验 HTTP 状态和业务码；明确已签到消息视为已完成，其他业务拒绝失败退出。。完整说明见 [kanxue.js.md](docs/scripts/kanxue.js.md)。
- `scripts/kgqq.py`（待检查）：查询并显示官方返回昵称及签到前后鲜花余额、计算本轮鲜花增量。；领取上游六类签到入口奖励：1、2、4、16、128、512。；显式开启后执行四类抽奖：入口 1 的类型 1、2，入口 4 的类型 104，以及类型 103。。完整说明见 [kgqq.py.md](docs/scripts/kgqq.py.md)。
- `scripts/kjwj.py`（待检查）：使用邮箱密码登录科技玩家，获取签到令牌；查询当日签到状态、当日获得积分和总积分；未签到时自动签到，并复查当日状态确认完成。完整说明见 [kjwj.py.md](docs/scripts/kjwj.py.md)。
- `scripts/kuaishou_reward_status.py`（上架）：只读查询快手收益与任务状态；按白名单输出非敏感状态字段；换行多账号独立执行并汇总。完整说明见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/kuku_daily.py`（待检查）：查询每日积分任务面板并验证业务登录状态；领取每日登录 LOGIN 奖励；领取对话 CHAT 任务奖励，不实际发送对话。完整说明见 [kuku_daily.py.md](docs/scripts/kuku_daily.py.md)。
- `scripts/kurobbs_sign.py`（待检查）：查询社区每日任务完成进度；查询鸣潮默认绑定角色并展示官方公开身份；库街区每日签到及连续天数、累计天数和奖励展示。完整说明见 [kurobbs_sign.py.md](docs/scripts/kurobbs_sign.py.md)。
- `scripts/l.py`（待检查）：Cookie 登录身份校验并显示官方返回的公开用户名和信任等级；按原有浏览开关与数量参数，从首页发现并随机读取话题，校验标题及帖子正文；查询访问天数、浏览话题、已读帖子、阅读时长、给出点赞、收到点赞及发帖数。完整说明见 [l.py.md](docs/scripts/l.py.md)。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`（待检查）：使用 Cookie 执行 Leaflow 每日签到；自动识别 CSRF 隐藏字段并提交签到表单；明确识别成功、今日已完成、会话失效和失败结果。完整说明见 [leaflow_checkin_pyleaflow_checkin.py.md](docs/scripts/leaflow_checkin_pyleaflow_checkin.py.md)。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`（待检查）：Cookie 登录配置检查，支持每行一个账号并保留 Cookie 值中的等号；从本站页面读取当前登录公开 UID 并按返回值显示，获取签到令牌；咔叽网单每日签到，明确区分签到成功、明确今日已签到和未确认成功。完整说明见 [littlewuh_qinglongbox_dailycheckin_scripts.py.md](docs/scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md)。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`（待检查）：每日签到，支持随机奖励或固定奖励模式。；随机时间窗口、多账号计划排序和带时间戳的等待倒计时；保留每天 04:23 的调度。；近 30 天签到收益分页查询，显示签到天数、鸡腿总数及日均收益；覆盖不完整或字段异常时明确失败。。完整说明见 [lizhixu_ql_script_hub_nodeseek.py.md](docs/scripts/lizhixu_ql_script_hub_nodeseek.py.md)。
- `scripts/lizhixu_ql_script_hub_youdao.py`（待检查）：HTTPS 会话刷新；同步奖励并核验 rewardSpace 字段；每日签到并核验 space 字段。完整说明见 [lizhixu_ql_script_hub_youdao.py.md](docs/scripts/lizhixu_ql_script_hub_youdao.py.md)。
- `scripts/lobsterai_checkin.py`（待检查）：每天签到：查询活动、查询状态、幂等提交和独立复核；明确已签到时不重复提交。；显示积分、连续签到和活动领取天数。；自动查询官方客户端版本，一次运行内共用版本；失败保留上游兜底版本，支持 --version 覆盖。。完整说明见 [lobsterai_checkin.py.md](docs/scripts/lobsterai_checkin.py.md)。
- `scripts/loomy_daily.py`（待检查）：每日首次登录刷新每日赠送积分，按天幂等，以 HTTP 成功且业务码 000000 核验。；--tasks 查询八项新手任务的分组、标题、积分与完成进度。；显式设置 LOOMY_ONBOARDING=1 批量领取未完成新手任务，--no-onboarding 可关闭；--claim KEY 单独领取一项。。完整说明见 [loomy_daily.py.md](docs/scripts/loomy_daily.py.md)。
- `scripts/lynkco_qinglong_single.py`（待检查）：AppCode优先续期、HMAC签名兜底及静态令牌回退；今日签到状态查询、自动签到和签到后复查，已签到时跳过；连续签到天数和签到卡查询。完整说明见 [lynkco_qinglong_single.py.md](docs/scripts/lynkco_qinglong_single.py.md)。
- `scripts/main.py`（待检查）：抓取 Wallhaven 最新列表，默认保留第 1 至 5 页。；按上游 thumb-info 中的六位壁纸编号及 PNG 标记下载 JPG 或 PNG 原图。；按当天日期归档壁纸，校验图片格式；已有有效图片跳过，跨页重复去重。。完整说明见 [main.py.md](docs/scripts/main.py.md)。
- `scripts/mifan_optimized.py`（待检查）：用户名和密码登录及登出，保留上游gid与MD5密码协议；查询米粒余额及展示官方非凭据账户身份；每日签到与已签到识别。完整说明见 [mifan_optimized.py.md](docs/scripts/mifan_optimized.py.md)。
- `scripts/mimotion.py`（待检查）：手机号或邮箱及密码登录 Zepp Life，核验授权与完整登录凭据，显示官方非敏感账号身份。；显式开启后在设定的随机范围内修改本人当天运动记录的步数并上传，要求接口 code=0 且 message=success。；优先获取远程时间戳，失败使用本地毫秒时间；HTTP 表单编码、超时、响应大小限制及禁止凭据重定向。。完整说明见 [mimotion.py.md](docs/scripts/mimotion.py.md)。
- `scripts/netease_task.py`（待检查）：登录确认并显示官方非敏感昵称或公开 UID；手机签到与网页签到，识别业务码 -2 的今日已完成；可选官方 weapi 网页签到，显示返回积分。完整说明见 [netease_task.py.md](docs/scripts/netease_task.py.md)。
- `scripts/nga_checkin.py`（待检查）：每日签到，明确识别签到成功与今日已签到；兼容原 UID|Token 凭据与 iOS 校验码、旧版小写环境变量；展示官方返回的非敏感身份及签到连续天数、累计天数。完整说明见 [nga_checkin.py.md](docs/scripts/nga_checkin.py.md)。
- `scripts/nodeseek.py`（待检查）：每日零点签到，支持随机奖励或固定奖励。；保留 curl_cffi 指纹模拟及默认 chrome110。；保留签到前随机延迟 0～5 分钟。。完整说明见 [nodeseek.py.md](docs/scripts/nodeseek.py.md)。
- `scripts/nodeseek_checkin.py`（待检查）：NodeSeek 每日签到；已签到状态识别；近 N 天签到鸡腿收益统计。完整说明见 [nodeseek_checkin.py.md](docs/scripts/nodeseek_checkin.py.md)。
- `scripts/nte.py`（待检查）：刷新用户中心令牌，保留 1.2.5 客户端请求头及 ds 签名。；塔吉多社区签到及经验、金币结果显示。；自动发现游戏角色，支持各账号角色配置与兼容全局角色配置。。完整说明见 [nte.py.md](docs/scripts/nte.py.md)。
- `scripts/officeace_daily.py`（待检查）：默认领取每日签到奖励和一次性新人礼，保留 V11-HMAC-SHA256 签名接口；--query 只读查询奖励额度积分；--only 指定账号，支持换行多账号和兼容单账号参数。完整说明见 [officeace_daily.py.md](docs/scripts/officeace_daily.py.md)。
- `scripts/ole.py`（待检查）：Ole 微信小程序账号签到；保留原账号字段、门店与城市默认值及定时表达式；多账号独立执行与失败闭合退出。完整说明见 [ole.py.md](docs/scripts/ole.py.md)。
- `scripts/passnat_checkin.py`（待检查）：PassNAT 每日签到；今日已签到的幂等成功识别；查询并显示套餐、流量、隧道、状态和到期时间。完整说明见 [passnat_checkin.py.md](docs/scripts/passnat_checkin.py.md)。
- `scripts/psnine.py`（待检查）：每日 PSNINE 祈祷签到；识别当天已经签到并展示累计祈祷天数；保留上游 do 接口及 psnid、shell 配套凭据。完整说明见 [psnine.py.md](docs/scripts/psnine.py.md)。
- `scripts/pt_sign_v5.js`（待检查）：蝴蝶、CARPT、AFUN 三站每日签到，支持站点选择与签到页地址覆盖；按站点分别配置多账号完整 Cookie，维护独立的服务器 Cookie 罐并识别登录失效；兼容 SafeLine 云端挑战、上游本地计算及验证后重放签到页。完整说明见 [pt_sign_v5.js.md](docs/scripts/pt_sign_v5.js.md)。
- `scripts/qoder_airscript.js`（待检查）：逐账号显式开关，兼容原账号 JSON 及两种访问、刷新令牌字段命名；优先使用访问令牌，缺少时刷新；活动查询 401 后刷新并重试一次；中国区和国际区活动强制刷新查询，支持同批账号指定不同地区。完整说明见 [qoder_airscript.js.md](docs/scripts/qoder_airscript.js.md)。
- `scripts/quark_signin.py`（待检查）：验证夸克账号 Cookie 并显示官方返回的昵称或公开身份；查询当日签到状态，识别今日已签到；领取每日存储空间奖励并展示奖励和连签进度。完整说明见 [quark_signin.py.md](docs/scripts/quark_signin.py.md)。
- `scripts/raccoon_daily.py`（待检查）：每日触发积分发放，以北京时间今日正积分账单核验签到成功。；分别领取首次电脑端、手机端登录奖励，检查业务码和 granted，哈希台账避免重复探测。；--query 只查询今日入账，不触发发放、不领取奖励、不写台账。。完整说明见 [raccoon_daily.py.md](docs/scripts/raccoon_daily.py.md)。
- `scripts/rainyun.py`（待检查）：使用雨云用户名和密码登录，保持登录 Cookie 与 CSRF 令牌。；执行每日签到并领取积分，仅以 HTTP 状态和结构化业务码确认成功。；查询并展示账号积分，展示接口返回的非敏感昵称、用户名或公开 UID。。完整说明见 [rainyun.py.md](docs/scripts/rainyun.py.md)。
- `scripts/rousi_checkin.js`（待检查）：普通模式每日签到，并按服务端今日日期识别已签到，避免重复操作；读取积分余额，保留站点自定义积分名称；展示分享率、当前魔力值及累计上传下载量。完整说明见 [rousi_checkin.js.md](docs/scripts/rousi_checkin.js.md)。
- `scripts/sf.py`（待检查）：使用分享登录凭据获取账号会话并显示官方返回的昵称、用户名或公开用户编号；自动签到、统计连续签到天数并显示签到礼包名称与有效期；查询积分任务列表并解析直接任务代码或跳转链接内任务编号。完整说明见 [sf.py.md](docs/scripts/sf.py.md)。
- `scripts/sfsu_checkin.py`（待检查）：验证顺丰速运登录会话；每日签到并识别已签到状态；查询积分、完成安全的积分任务并领取奖励。完整说明见 [sfsu_checkin.py.md](docs/scripts/sfsu_checkin.py.md)。
- `scripts/sgs.py`（待检查）：获取官方账号姓名与积分，展示非秘密身份；每日签到并检查业务成功；显式开启后随机检索未读文章并阅读最多五篇，限制分页次数。完整说明见 [sgs.py.md](docs/scripts/sgs.py.md)。
- `scripts/shuyi.py`（待检查）：获取书亦烧仙草滑块验证码；使用 OpenCV 模板匹配识别滑块位置；使用 AES 加密并校验滑块，校验成功后签到。完整说明见 [shuyi.py.md](docs/scripts/shuyi.py.md)。
- `scripts/sign_in.py`（待检查）：多账号看雪论坛签到，支持同账号 Cookie、CSRF token 和可选 User-Agent；兼容显式指定的旧配置文件及嵌套账号结构；使用独立标准库 HTTP 请求，固定原签到端点，限制超时及响应大小并核验业务码 0。完整说明见 [sign_in.py.md](docs/scripts/sign_in.py.md)。
- `scripts/skland_daily.py`（待检查）：通行证 Token、森空岛 cred/token 和手机号密码登录，保留官方授权换取及请求签名；自动获取临时设备标识或使用用户指定标识；获取版区及今日检票状态、版区筛选、每日检票及避免重复检票。完整说明见 [skland_daily.py.md](docs/scripts/skland_daily.py.md)。
- `scripts/skland_demo.py`（待检查）：鹰角通行证登录，兼容旧版 TOKEN 和官网单行 JSON 响应输入；手机号密码或已有短信验证码登录；显式动作发送登录验证码；内置数美设备标识计算，也可使用同账号显式提供的设备标识。完整说明见 [skland_demo.py.md](docs/scripts/skland_demo.py.md)。
- `scripts/skyland.py`（待检查）：保留数美设备指纹协议及进程内设备凭据缓存；服务器时间校准，失败时使用本地时间；鹰角 Token 授权并登录森空岛。完整说明见 [skyland.py.md](docs/scripts/skyland.py.md)。
- `scripts/smzdm_checkin.js`（待检查）：校验账号的 sk 与 sess 配套凭据；执行什么值得买每日签到并识别今日已签到状态；查询签到奖励与连续签到状态。完整说明见 [smzdm_checkin.js.md](docs/scripts/smzdm_checkin.js.md)。
- `scripts/ssl_cert_check.py`（待检查）：支持 Cloudflare API Token 和邮箱配套 Global API Key 两种认证，兼容原有环境变量；按区域分页读取 A 记录，多个区域合并去重，检查业务成功及完整分页，单个区域失败继续检查其余区域；多个账号逐行独立运行，配置错误、区域读取失败、无 A 记录、过期或证书检查失败均返回非零。完整说明见 [ssl_cert_check.py.md](docs/scripts/ssl_cert_check.py.md)。
- `scripts/sudojia_33agilestudio.js`（待检查）：邮箱密码登录并获取会话令牌；查询账户信息，显示返回的非敏感昵称、用户名、显示名称或公开 UID；每日签到获得积分。完整说明见 [sudojia_33agilestudio.js.md](docs/scripts/sudojia_33agilestudio.js.md)。
- `scripts/sudojia_allgirls.js`（待检查）：获取并显示官方昵称；查询每日签到状态，已签到时避免重复请求；未签到时执行签到并复查已签到状态。完整说明见 [sudojia_allgirls.js.md](docs/scripts/sudojia_allgirls.js.md)。
- `scripts/sudojia_amx.js`（待检查）：查询账号信息并显示接口返回的昵称，不输出手机号；查询今日签到状态，已签到则跳过重复签到；未签到时执行每日签到，并再次查询签到状态核验结果，显示可用的奖励积分。完整说明见 [sudojia_amx.js.md](docs/scripts/sudojia_amx.js.md)。
- `scripts/sudojia_authcheck.js`（待检查）：所有女生账号凭据有效性检查（兼容 ALL_GIRLS_TOKEN）；安慕希账号凭据有效性检查（兼容 AMX_TOKEN）；霸王茶姬账号凭据有效性检查（兼容 BW_TEA_TOKEN）。完整说明见 [sudojia_authcheck.js.md](docs/scripts/sudojia_authcheck.js.md)。
- `scripts/sudojia_bananavideo.js`（待检查）：每日 01:10 执行登录、账号昵称查询、签到、广告任务、长视频下载任务登记、观看十个视频、二维码任务登记及金币查询。；显式启用后可添加五个随机视频收藏；移除上游清空全部收藏的危险行为。；显式启用后可发布评论：独立 HTTPS 一言文本提供方、作者与来源署名、空白规范化、二百八十字符上限及本地回退。。完整说明见 [sudojia_bananavideo.js.md](docs/scripts/sudojia_bananavideo.js.md)。
- `scripts/sudojia_beiyinmei.js`（待检查）：验证登录状态并显示接口返回的昵称，不输出手机号或凭据。；每日执行贝因美小程序签到，仅业务码 0 判定签到成功，未知状态按失败处理。；支持每行一个账号，失败隔离和整体非零退出。。完整说明见 [sudojia_beiyinmei.js.md](docs/scripts/sudojia_beiyinmei.js.md)。
- `scripts/sudojia_botanystar.js`（待检查）：使用手机号与密码的 MD5 值登录，独立保存各账号会话；每日签到并显示奖励和连续签到天数；完成类型 10 和 60 的浏览任务，两项请求之间等待 11 秒。完整说明见 [sudojia_botanystar.js.md](docs/scripts/sudojia_botanystar.js.md)。
- `scripts/sudojia_bwtea.js`（待检查）：登录状态校验及官方昵称显示；查询新版签到状态及连续签到天数，未签到时执行签到并复核状态；查询当前积分及即将到期的积分和日期。完整说明见 [sudojia_bwtea.js.md](docs/scripts/sudojia_bwtea.js.md)。
- `scripts/sudojia_colorful_mall.js`（待检查）：根据原始登录请求体换取独立账号凭据并校验登录状态；显示官方返回的昵称，不输出手机号及凭据；查询旧版签到状态，未签到时执行旧版签到，并执行新版签到。完整说明见 [sudojia_colorful_mall.js.md](docs/scripts/sudojia_colorful_mall.js.md)。
- `scripts/sudojia_flyant.js`（待检查）：每日签到；查询连续签到天数；查询累计获得、使用及剩余环保豆。完整说明见 [sudojia_flyant.js.md](docs/scripts/sudojia_flyant.js.md)。
- `scripts/sudojia_fnnas.js`（待检查）：读取并显示本站返回的账号昵称和公开 UID，抑制手机号及凭据输出；每日签到，识别明确的今日已签到状态；执行后重新读取页面验证结果；查询最近、本月、连续、累计打卡次数或时间、累计和最近奖励、当前打卡等级。完整说明见 [sudojia_fnnas.js.md](docs/scripts/sudojia_fnnas.js.md)。
- `scripts/sudojia_hgf.js`（待检查）：每日自动签到，显示接口返回的数字酒币奖励。；浏览小阿头条并领取任务奖励。；保留每天 05:33 的执行计划，签到日期按北京时间计算。。完整说明见 [sudojia_hgf.js.md](docs/scripts/sudojia_hgf.js.md)。
- `scripts/sudojia_hlzj_game.js`（待检查）：独立完成请求签名和登录，显示官方返回的昵称及公开用户编号。；领取今日电力并显示明日奖励。；查询签到状态，未签到时执行签到，显示奖励和连续签到天数。。完整说明见 [sudojia_hlzj_game.js.md](docs/scripts/sudojia_hlzj_game.js.md)。
- `scripts/sudojia_hzhfp.js`（待检查）：获取并原样显示官方微信昵称，不输出手机号；每日签到并查询连续签到天数；查询当前积分。完整说明见 [sudojia_hzhfp.js.md](docs/scripts/sudojia_hzhfp.js.md)。
- `scripts/sudojia_instax.js`（待检查）：查询官方昵称、公开 UID、当前积分和等级；每日签到（活动 25）；显式开启后查询抽奖机会并连续抽奖（活动 42），展示奖品结果。完整说明见 [sudojia_instax.js.md](docs/scripts/sudojia_instax.js.md)。
- `scripts/sudojia_jhcard.js`（待检查）：登录并展示官方返回的账号姓名，不展示手机号或凭据；每日签到；查询连续签到天数。完整说明见 [sudojia_jhcard.js.md](docs/scripts/sudojia_jhcard.js.md)。
- `scripts/sudojia_jiangshan.js`（待检查）：每日签到并查询连续签到天数；读取新闻并复查任务完成进度；可选分享任务上报、评论、点赞与本地服务任务上报。完整说明见 [sudojia_jiangshan.js.md](docs/scripts/sudojia_jiangshan.js.md)。
- `scripts/sudojia_jindian.js`（待检查）：查询并显示官方账号昵称等非秘密身份信息；检查每日签到状态，已签到时避免重复写入；执行每日签到，显示奖励并复查签到状态。完整说明见 [sudojia_jindian.js.md](docs/scripts/sudojia_jindian.js.md)。
- `scripts/sudojia_jlc_yj.js`（待检查）：保留开源平台官方昵称查询、每日签到与积分查询，以及维护版默认调度和请求接口；合并原脚本签到前后状态复查、总积分及积分变化、本周签到和本月连续签到统计；已签到避免重复写入；兼容 OSHW_COOKIE 和可选随机签到延迟，保留原脚本调度说明；只读查询网络异常最多重试三次。完整说明见 [sudojia_jlc_yj.js.md](docs/scripts/sudojia_jlc_yj.js.md)。
- `scripts/sudojia_juejin.js`（待检查）：检查登录和今日签到状态；显示官方返回的账号昵称；每日签到，已签到时不重复提交，重复签到业务码须经状态复核。完整说明见 [sudojia_juejin.js.md](docs/scripts/sudojia_juejin.js.md)。
- `scripts/sudojia_kozbs.js`（待检查）：查询官方返回的公开昵称和当前积分。；检查今日签到状态，已签到时避免重复签到。；未签到时执行每日签到，以业务码 errno 严格等于数字 0 确认接口成功。。完整说明见 [sudojia_kozbs.js.md](docs/scripts/sudojia_kozbs.js.md)。
- `scripts/sudojia_ktgzs.js`（待检查）：查询并显示官方返回的账号名称，不输出手机号；每日签到，显示签到奖励和连续签到天数；查询最近积分流水中的当前积分。完整说明见 [sudojia_ktgzs.js.md](docs/scripts/sudojia_ktgzs.js.md)。
- `scripts/sudojia_kukahome.js`（待检查）：读取并显示官方返回的账号昵称，不输出手机号或原始响应；每日签到并校验业务状态与积分结果；查询连续签到天数与当前积分。完整说明见 [sudojia_kukahome.js.md](docs/scripts/sudojia_kukahome.js.md)。
- `scripts/sudojia_kuro.js`（待检查）：检查 Token 与鸣潮角色，保留 H5 到 Android 的验证回退；社区每日签到并显示获得库洛币及连续签到天数；查询账户库洛币余额。完整说明见 [sudojia_kuro.js.md](docs/scripts/sudojia_kuro.js.md)。
- `scripts/sudojia_laoban.js`（待检查）：查询并显示官方账号昵称，不输出手机号或凭据；按中国标准时间检查每日签到状态，未签到时签到并复查；查询累计签到天数，领取可领取的连续签到积分奖励。完整说明见 [sudojia_laoban.js.md](docs/scripts/sudojia_laoban.js.md)。
- `scripts/sudojia_longfor.js`（待检查）：读取并显示官方昵称，隐藏手机号及凭据；每日签到并区分今日已签到；显式启用后抽奖签到、获取机会及执行一次抽奖、显示结果。完整说明见 [sudojia_longfor.js.md](docs/scripts/sudojia_longfor.js.md)。
- `scripts/sudojia_mallcoo.js`（待检查）：查询并显示账号昵称；每日签到，识别今日已签到并复核新签到状态；查询当前积分余额。完整说明见 [sudojia_mallcoo.js.md](docs/scripts/sudojia_mallcoo.js.md)。
- `scripts/sudojia_mawuwang.js`（待检查）：校验登录凭据；读取官方返回的非敏感昵称或用户名以核对账号；每日查询签到状态，已签到时跳过重复提交，未签到时执行签到。完整说明见 [sudojia_mawuwang.js.md](docs/scripts/sudojia_mawuwang.js.md)。
- `scripts/sudojia_midea.js`（待检查）：查询账号登录信息与会员等级，显示接口提供的非敏感公开身份；每日签到并严格验证 errcode 为数字 0；查询当前积分和成长值。完整说明见 [sudojia_midea.js.md](docs/scripts/sudojia_midea.js.md)。
- `scripts/sudojia_moto.js`（已检查）：查询账号信息并显示官方昵称，刷新当前运行中的会话凭据；提交每日签到，严格根据签到接口数字业务码 0 确认成功；按明确要求暂停签到状态查询及二次核验；查询当前能量。完整说明见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。
- `scripts/sudojia_mxbc.js`（待检查）：验证小程序账号登录状态，显示官方返回的非敏感昵称、用户名、显示名称或公开 UID；不显示手机号。；每日签到并显示本次雪王币奖励和连续签到天数。；签到后查询当前雪王币余额；签到失败仍尝试查询，整体保持失败状态。。完整说明见 [sudojia_mxbc.js.md](docs/scripts/sudojia_mxbc.js.md)。
- `scripts/sudojia_naixue.js`（待检查）：校验账号登录状态，显示官方返回的非敏感昵称或用户标识。；查询签到状态和记录天数，已签到时跳过重复提交，未签到时执行每日签到并校验成功标志。；查询当前奈雪币余额。。完整说明见 [sudojia_naixue.js.md](docs/scripts/sudojia_naixue.js.md)。
- `scripts/sudojia_nestle.js`（待检查）：查询官方用户信息并显示昵称等非敏感公开身份，不显示手机号或凭据。；查询任务列表并显示可用于授权的任务编号。；仅提交显式白名单中的任务，以接口 errcode=200 验证成功；默认仅查询。。完整说明见 [sudojia_nestle.js.md](docs/scripts/sudojia_nestle.js.md)。
- `scripts/sudojia_nfhk.js`（待检查）：每日签到，识别今日已签到状态；查询中国时区当月签到进度；查询可用里程。完整说明见 [sudojia_nfhk.js.md](docs/scripts/sudojia_nfhk.js.md)。
- `scripts/sudojia_opposhop.js`（待检查）：从活动页面 DSL 自动发现签到和任务活动 ID；核验登录与会员信息，显示官方会员名称；每日签到并重新查询验证签到状态，识别今日已签到。完整说明见 [sudojia_opposhop.js.md](docs/scripts/sudojia_opposhop.js.md)。
- `scripts/sudojia_pangge.js`（待检查）：校验登录状态并显示官方返回的非敏感昵称；查询签到状态、连续签到天数和累计签到天数；未签到时执行每日签到并再次查询确认，已签到时跳过。完整说明见 [sudojia_pangge.js.md](docs/scripts/sudojia_pangge.js.md)。
- `scripts/sudojia_paotea.js`（待检查）：登录状态校验及官方返回的非敏感身份展示；每日签到及已签到识别，签到后复核状态；查询连续签到天数和下一阶段奖励，显示距离奖励的天数。完整说明见 [sudojia_paotea.js.md](docs/scripts/sudojia_paotea.js.md)。
- `scripts/sudojia_shmedia.js`（待检查）：显示官方返回的昵称、用户名、显示名称或公开 UID，不输出手机号或凭据；查询任务列表，签到、阅读和视频积分任务，检查操作后任务进度；可选收藏、公开评论和分享积分任务，默认关闭；保留上游跳过任务 004 的行为。完整说明见 [sudojia_shmedia.js.md](docs/scripts/sudojia_shmedia.js.md)。
- `scripts/sudojia_shuifei.js`（待检查）：查询官方昵称与剩余签到次数，隐藏手机号及凭据；按剩余次数签到，已签到时跳过并保留连续签到天数展示；查询当前积分。完整说明见 [sudojia_shuifei.js.md](docs/scripts/sudojia_shuifei.js.md)。
- `scripts/sudojia_sspanel.js`（待检查）：通过邮箱和密码登录各账号的 SSPANEL 站点；每日签到并严格验证登录和签到业务成功码；展示接口提供的总套餐、已用流量及剩余流量。完整说明见 [sudojia_sspanel.js.md](docs/scripts/sudojia_sspanel.js.md)。
- `scripts/sudojia_starmom.js`（待检查）：每日签到及签到积分校验；浏览主会场、热销爆品、优惠券、视频和粮油专场并领取任务积分；显示官方昵称、等级和积分。完整说明见 [sudojia_starmom.js.md](docs/scripts/sudojia_starmom.js.md)。
- `scripts/sudojia_tebu.js`（待检查）：查询并显示官方返回的非敏感账号身份；为每个账号独立发现签到活动；每日签到并显示获得积分。完整说明见 [sudojia_tebu.js.md](docs/scripts/sudojia_tebu.js.md)。
- `scripts/sudojia_tilta.js`（待检查）：获取官方昵称用于账号核对，抑制凭据及手机号输出；每日签到并复查今日日历状态；可选社区文章点赞，默认关闭。完整说明见 [sudojia_tilta.js.md](docs/scripts/sudojia_tilta.js.md)。
- `scripts/sudojia_tuchong.js`（待检查）：手机号密码登录，沿用上游 AES-128-ECB 手机号加密与请求头。；查询并展示官方昵称及公开 UID。；每日签到获取积分。。完整说明见 [sudojia_tuchong.js.md](docs/scripts/sudojia_tuchong.js.md)。
- `scripts/sudojia_v2ex.js`（待检查）：Cookie 登录校验及官方公开用户名显示；每日奖励领取和已领取状态识别；连续签到天数查询。完整说明见 [sudojia_v2ex.js.md](docs/scripts/sudojia_v2ex.js.md)。
- `scripts/sudojia_wnna.js`（待检查）：查询上海时区当日签到状态，仅在明确未签到时提交签到；展示连续签到天数，已签到账号不重复提交；查询并展示官方昵称、等级和当前积分。完整说明见 [sudojia_wnna.js.md](docs/scripts/sudojia_wnna.js.md)。
- `scripts/sudojia_xhn.js`（待检查）：使用抓包表单登录并检查授权令牌；每日签到并核验业务成功码；查询当前可用积分并验证响应字段。完整说明见 [sudojia_xhn.js.md](docs/scripts/sudojia_xhn.js.md)。
- `scripts/sudojia_xiangwan.js`（待检查）：每日登录并签到，显示本次签到玩豆奖励；查询当前玩豆余额，显示官方返回的昵称；可选受限权限 Token 缓存、有效性验证与密码登录回退。完整说明见 [sudojia_xiangwan.js.md](docs/scripts/sudojia_xiangwan.js.md)。
- `scripts/sudojia_xiaomi_community.js`（待检查）：查询并展示官方返回的公开用户名和用户编号，抑制敏感字段；每天执行微信小程序签到，展示接口确认的增加积分；查询成长值明细并按上游规则汇总展示当前成长值。完整说明见 [sudojia_xiaomi_community.js.md](docs/scripts/sudojia_xiaomi_community.js.md)。
- `scripts/sudojia_xinxi.js`（待检查）：查询官方昵称并原样显示非凭据身份，查询执行前后喜点；每日签到并显示奖励与连续签到天数，识别今日已签到；显式启用后查询免费次数并最多执行一次免费抽奖，禁止积分抽奖。完整说明见 [sudojia_xinxi.js.md](docs/scripts/sudojia_xinxi.js.md)。
- `scripts/sudojia_xpfarm.js`（待检查）：获取官方账号昵称并展示以核对账号；每日签到，已签到时跳过；按显式配置的任务编号完成任务并领取奖励。完整说明见 [sudojia_xpfarm.js.md](docs/scripts/sudojia_xpfarm.js.md)。
- `scripts/sudojia_znds.js`（待检查）：验证登录状态并显示官方公开 UID；每日签到并区分签到成功和今日已完成；显式配置后访问指定用户空间。完整说明见 [sudojia_znds.js.md](docs/scripts/sudojia_znds.js.md)。
- `scripts/sudojia_zxice.js`（待检查）：校验账号登录状态并展示官方返回的非敏感昵称；查询今日签到状态，已签到时避免重复操作；每日签到并展示接口确认的奶滴奖励。完整说明见 [sudojia_zxice.js.md](docs/scripts/sudojia_zxice.js.md)。
- `scripts/supertopicsign.py`（待检查）：读取关注超话完整分页列表，检查分页结构和循环上限；识别已签到状态并跳过重复签到；按超话等级升序、降序或接口原始顺序执行。完整说明见 [supertopicsign.py.md](docs/scripts/supertopicsign.py.md)。
- `scripts/synspoint.py`（待检查）：查询官方昵称并显示非敏感身份；查询任务前后积分；执行会员签到。完整说明见 [synspoint.py.md](docs/scripts/synspoint.py.md)。
- `scripts/task_ef2d3863.js`（待检查）：使用刷新令牌获取访问令牌，显示官方返回的非敏感昵称、用户名、显示名称或公开用户编号。；每日签到，核验业务成功字段与当天签到状态，显示本月累计签到天数。；依次补领全部正常且未领取的签到奖励，显示公开奖励名称与说明；今日已领取时显示今日奖励。。完整说明见 [task_ef2d3863.js.md](docs/scripts/task_ef2d3863.js.md)。
- `scripts/tencent_video_checkin.py`（待检查）：每日签到获取 V力值；领取每日观看任务奖励（不自动播放视频）；查询会员积分、等级和 V力值，保留零值展示。完整说明见 [tencent_video_checkin.py.md](docs/scripts/tencent_video_checkin.py.md)。
- `scripts/tieba_checkin.py`（上架）：保留登录验证和 TBS 获取、读取关注贴吧、识别当日已签到项目、为未签到贴吧逐吧签到，沿用明确成功码和已签到判断。；直接显示官方接口返回的昵称、用户名或公开 UID，方便核对账号。；显式开启后通过 APP 成长接口验证登录、取得独立 TBS，并执行成长任务每日签到，要求业务码明确为 0。。完整说明见 [tieba_checkin.py.md](docs/scripts/tieba_checkin.py.md)。
- `scripts/tjd_daily.py`（待检查）：社区每日签到并复核服务端任务进度；浏览推荐帖子，按服务端剩余次数执行和复核；显式启用帖子点赞，跳过已点赞帖子并复核进度。完整说明见 [tjd_daily.py.md](docs/scripts/tjd_daily.py.md)。
- `scripts/trae_checkin.py`（待检查）：每日查询签到状态、按需签到，官方已签不重复领取；签到后查询真实积分余额；独立 credits 模式显示总额、已用及余额，保留权益接口到用量接口的回退链；访问凭据复用、过期或鉴权失败自动续期，保留新版设备证明、IDE_PC、SOLO_PC 与旧客户端兼容链。完整说明见 [trae_checkin.py.md](docs/scripts/trae_checkin.py.md)。
- `scripts/tsthb_checkin.py`（待检查）：从官方活动列表查询当前签到活动，优先每日签到入口；校验账号并展示官方返回的非敏感身份，隐藏手机号；每日签到并展示奖励名称或积分。完整说明见 [tsthb_checkin.py.md](docs/scripts/tsthb_checkin.py.md)。
- `scripts/ty_netdisk_checkin.py`（待检查）：使用官方密码登录流程和 RSA 加密建立独立账号 Cookie 会话；每日签到、区分新签到和今日已签到、显示奖励空间并严格校验业务结果；每行配套凭据、多账号独立执行、任一失败整体非零退出。完整说明见 [ty_netdisk_checkin.py.md](docs/scripts/ty_netdisk_checkin.py.md)。
- `scripts/tyqhdraw.py`（待检查）：登录并校验业务成功码与有效会话；查询调料包和番茄资产；打印官方返回的非秘密账号身份；显式开启后执行活动 58 集市兑换抽奖，每轮最多 10 次并检查奖品字段。完整说明见 [tyqhdraw.py.md](docs/scripts/tyqhdraw.py.md)。
- `scripts/valorantstore.py`（待检查）：按原每日 08:15 定时查询掌上无畏契约每日商店，不购买商品。；刷新 access_token、client ticket、web ticket 和临时票据；刷新失败仍尝试旧会话查询并以失败状态退出。；查询绑定账号并按官方返回显示昵称；无昵称时使用账号序号。。完整说明见 [valorantstore.py.md](docs/scripts/valorantstore.py.md)。
- `scripts/vortexa_free_claim.js`（待检查）：账号密码登录，邮箱或用户名字段自动识别与自定义登录字段；访问 Token、刷新 Cookie 登录；授权失效后按原方式重新登录一次。；检查已有免费主机，显示公开服务名称或 ID；官网返回昵称、用户名、显示名或公开 UID 时输出身份以核对账号，不输出邮箱登录凭据。；查询免费主机库存、领取资格，默认完成只读检查；已有免费主机时确认已完成。。完整说明见 [vortexa_free_claim.js.md](docs/scripts/vortexa_free_claim.js.md)。
- `scripts/wangchao.py`（待检查）：手机号与密码登录，展示官方返回的非敏感昵称或公开账号标识；保留上游随机客户端标识、RSA 密码加密、HMAC 登录认证、应用请求签名和 SM2 阅读参数加密；进入 App，获取每日阅读任务、识别已读文章、浏览未读文章、提交阅读记录并复查完成进度。完整说明见 [wangchao.py.md](docs/scripts/wangchao.py.md)。
- `scripts/wentiweilaihui.py`（待检查）：查询签到记录及今日签到状态；今日已签到时跳过重复签到，否则执行每日签到；查询并展示当前会员积分。完整说明见 [wentiweilaihui.py.md](docs/scripts/wentiweilaihui.py.md)。
- `scripts/workbuddy.py`（待检查）：每日签到和今日状态查询；主状态接口失败时回退兼容接口，令牌失效不盲目回退。；展示每日积分、签到获得积分、连续签到天数及连签奖励标记。；识别官方确认的活动关闭或今日已签；签到失败后复查，确认已签则视为完成。。完整说明见 [workbuddy.py.md](docs/scripts/workbuddy.py.md)。
- `scripts/workbuddy_daily.py`（待检查）：国内版每日签到及服务端签到状态回读，活动关闭正常跳过，区分签到连签与活跃连签；积分套餐总量、余额、用量、等级、能量、活跃连签及成长任务状态查询，显示官方非敏感账号身份；扫描已完成成长任务并领取奖励，回读验证领取状态；领奖保留网页请求头回退。完整说明见 [workbuddy_daily.py.md](docs/scripts/workbuddy_daily.py.md)。
- `scripts/wps_clock_in.py`（待检查）：查询并显示官方返回的账号昵称，隐藏凭据和手机号。；查询打卡活动首条奖励名称，兼容sku_name与mb_name。；查询持续打卡天数，明确空奖励不能证明今日打卡成功。。完整说明见 [wps_clock_in.py.md](docs/scripts/wps_clock_in.py.md)。
- `scripts/wyycg.py`（待检查）：验证网易云游戏 Authorization 凭据并读取账户配置；每日签到并对业务结果进行明确成功判定，未知响应按失败处理；显示官方返回的非敏感昵称、用户名、显示名称或公开 UID。完整说明见 [wyycg.py.md](docs/scripts/wyycg.py.md)。
- `scripts/yht.py`（待检查）：查询官方账号昵称等非敏感身份，不输出手机号；查询种植活动标题；参与种植活动。完整说明见 [yht.py.md](docs/scripts/yht.py.md)。
- `scripts/youdao.py`（待检查）：刷新登录会话，保留已有 Cookie 并接收服务端更新。；每日同步空间奖励，验证 rewardSpace 字段。；每日签到，验证 space 字段。。完整说明见 [youdao.py.md](docs/scripts/youdao.py.md)。
- `scripts/yyshuijuantime.py`（待检查）：每天读取阴阳师官网最新五条维护更新公告；支持原有三种正文容器，并保留嵌套正文内容；提取追忆绘卷活动名称、维护后开始日期及结束时间，支持跨年并验证日期。完整说明见 [yyshuijuantime.py.md](docs/scripts/yyshuijuantime.py.md)。
- `scripts/zcode_cn_daily.py`（待检查）：保留国内版默认任务，新增显式国际版及跨区域账号选择；两类凭据独立处理。；查询可领取套餐、权益及有效期，并按北京时间显示。；优先级最高套餐自动领取，同优先级保持上游顺序；可指定套餐。。完整说明见 [zcode_cn_daily.py.md](docs/scripts/zcode_cn_daily.py.md)。
- `scripts/zippo.py`（待检查）：积分余额查询；每日签到及奖励核验；商品分类7前两页检索。完整说明见 [zippo.py.md](docs/scripts/zippo.py.md)。
- `scripts/zodgame_test.py`（待检查）：每日签到及今日已签到识别；Bux 首次加入、广告观看读秒、观看完成更新与积分领取；领取结果重试一次并核验已知业务成功提示。完整说明见 [zodgame_test.py.md](docs/scripts/zodgame_test.py.md)。

## 环境变量与参数

先配置“必选参数”再运行脚本；缺少任一必选参数时任务会失败。可选参数只用于调整行为，不影响首次配置。敏感值不得写入脚本、订阅地址或日志。

多账号统一规则：每行一个账号；需要多个凭据变量时按相同非空行号配对，行数必须一致。

### 必选参数（优先配置）

各脚本必选变量名称如下；格式、默认值与示例见对应详单。

- `scripts/139_yunduo.py`：必选 `YDYP_ACCOUNTS`；详见 [139_yunduo.py.md](docs/scripts/139_yunduo.py.md)。
- `scripts/2cycdx.py`：必选 `cycd_cookie`；详见 [2cycdx.py.md](docs/scripts/2cycdx.py.md)。
- `scripts/51cto_sign.js`：必选 `ICTO_BLOG_ACCOUNTS`；详见 [51cto_sign.js.md](docs/scripts/51cto_sign.js.md)。
- `scripts/52pojie.js`：必选 `POJIE_COOKIE`；详见 [52pojie.js.md](docs/scripts/52pojie.js.md)。
- `scripts/999.py`：必选 `HRT999_ACCOUNTS`；详见 [999.py.md](docs/scripts/999.py.md)。
- `scripts/acfun.py`：必选 `ACFUN_ACCOUNTS`；详见 [acfun.py.md](docs/scripts/acfun.py.md)。
- `scripts/agentrouter.py`：必选 `AGENTROUTER_ACCOUNTS`；详见 [agentrouter.py.md](docs/scripts/agentrouter.py.md)。
- `scripts/airport.py`：必选 `SUYING_ACCOUNTS`；详见 [airport.py.md](docs/scripts/airport.py.md)。
- `scripts/akile_checkin.py`：必选 `AKILE_TOKEN`；详见 [akile_checkin.py.md](docs/scripts/akile_checkin.py.md)。
- `scripts/aliyun_web.js`：必选 `aliyunWeb_data`；详见 [aliyun_web.js.md](docs/scripts/aliyun_web.js.md)。
- `scripts/aliyundrive_checkin.js`：必选 `refreshToken`；详见 [aliyundrive_checkin.js.md](docs/scripts/aliyundrive_checkin.js.md)。
- `scripts/aliyunpan_checkin.py`：必选 `ALIYUN_REFRESH_TOKEN`；详见 [aliyunpan_checkin.py.md](docs/scripts/aliyunpan_checkin.py.md)。
- `scripts/aolaxing.py`：必选 `AOLAXING_COOKIE`；详见 [aolaxing.py.md](docs/scripts/aolaxing.py.md)。
- `scripts/api_hax.py`：必选 `HAX`；详见 [api_hax.py.md](docs/scripts/api_hax.py.md)。
- `scripts/arknightsbanner.py`：必选 `ARKNIGHTS_STATE_FILE`；详见 [arknightsbanner.py.md](docs/scripts/arknightsbanner.py.md)。
- `scripts/atxyq.py`：必选 `atxyqs`；详见 [atxyq.py.md](docs/scripts/atxyq.py.md)。
- `scripts/auto_buy.py`：必选 `SHYP_BUY_ACCOUNTS`, `SHYP_BUY_SKU_ID`, `SHYP_BUY_ACTIVITY_ID`, `SHYP_POINTS_ACCOUNTS`；详见 [auto_buy.py.md](docs/scripts/auto_buy.py.md)。
- `scripts/autoclaw_cn_daily.py`：必选 `AUTOCLAW_CN_TOKENS`；详见 [autoclaw_cn_daily.py.md](docs/scripts/autoclaw_cn_daily.py.md)。
- `scripts/autosignin.js`：必选 `ALIYUN_REFRESH_TOKEN`；详见 [autosignin.js.md](docs/scripts/autosignin.js.md)。
- `scripts/autosignin.py`：必选 `E_COOKIE`；详见 [autosignin.py.md](docs/scripts/autosignin.py.md)。
- `scripts/baidu.py`：必选 `BAIDU`；详见 [baidu.py.md](docs/scripts/baidu.py.md)。
- `scripts/baiduwangpan_checkin.py`：必选 `BAIDU_COOKIE`；详见 [baiduwangpan_checkin.py.md](docs/scripts/baiduwangpan_checkin.py.md)。
- `scripts/baiduwp.py`：必选 `BAIDUWP_COOKIE`；详见 [baiduwp.py.md](docs/scripts/baiduwp.py.md)。
- `scripts/bilibili.py`：必选 `BILIBILI_COOKIE`；详见 [bilibili.py.md](docs/scripts/bilibili.py.md)。
- `scripts/bsly_draw.py`：必选 `bsly`；详见 [bsly_draw.py.md](docs/scripts/bsly_draw.py.md)。
- `scripts/bugutv.py`：必选 `BUGUTV_ACCOUNTS`；详见 [bugutv.py.md](docs/scripts/bugutv.py.md)。
- `scripts/bwcj.py`：必选 `bwcjCookie`；详见 [bwcj.py.md](docs/scripts/bwcj.py.md)。
- `scripts/caigamer.js`：必选 `CAIGAMER_COOKIE_LIST`；详见 [caigamer.js.md](docs/scripts/caigamer.js.md)。
- `scripts/cdrail.py`：必选 `CDRAIL_DATA`；详见 [cdrail.py.md](docs/scripts/cdrail.py.md)。
- `scripts/cfmoto_checkin.py`：必选 `CFMOTO_COOKIE`；详见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/cg163_autocheckin.py`：必选 `CG163_ACCOUNTS`；详见 [cg163_autocheckin.py.md](docs/scripts/cg163_autocheckin.py.md)。
- `scripts/chevrolet.js`：必选 `CHEVROLET_ACCOUNTS`；详见 [chevrolet.js.md](docs/scripts/chevrolet.js.md)。
- `scripts/ck_2nzz.py`：必选 `NZZ_COOKIE`；详见 [ck_2nzz.py.md](docs/scripts/ck_2nzz.py.md)。
- `scripts/ck_acfun.py`：必选 `ACFUN_ACCOUNTS`；详见 [ck_acfun.py.md](docs/scripts/ck_acfun.py.md)。
- `scripts/ck_airport.py`：必选 `AIRPORT_ACCOUNTS`；详见 [ck_airport.py.md](docs/scripts/ck_airport.py.md)。
- `scripts/ck_aqc.js`：必选 `AQC_ACCOUNTS`；详见 [ck_aqc.js.md](docs/scripts/ck_aqc.js.md)。
- `scripts/ck_baidu_url_submit.py`：必选 `BAIDU_ACCOUNTS`；详见 [ck_baidu_url_submit.py.md](docs/scripts/ck_baidu_url_submit.py.md)。
- `scripts/ck_bilibili.py`：必选 `BILIBILI_COOKIES`；详见 [ck_bilibili.py.md](docs/scripts/ck_bilibili.py.md)。
- `scripts/ck_ccava.py`：必选 `CCAVA_COOKIE`；详见 [ck_ccava.py.md](docs/scripts/ck_ccava.py.md)。
- `scripts/ck_csdn.py`：必选 `CSDN_COOKIE`；详见 [ck_csdn.py.md](docs/scripts/ck_csdn.py.md)。
- `scripts/ck_du163.js`：必选 `DU163_COOKIE`；详见 [ck_du163.js.md](docs/scripts/ck_du163.js.md)。
- `scripts/ck_duokan.py`：必选 `DUOKAN_COOKIE`；详见 [ck_duokan.py.md](docs/scripts/ck_duokan.py.md)。
- `scripts/ck_everphoto.py`：必选 `EVERPHOTO`；详见 [ck_everphoto.py.md](docs/scripts/ck_everphoto.py.md)。
- `scripts/ck_fmapp.py`：必选 `FMAPP`；详见 [ck_fmapp.py.md](docs/scripts/ck_fmapp.py.md)。
- `scripts/ck_freenom.py`：必选 `FREENOM_ACCOUNTS`；详见 [ck_freenom.py.md](docs/scripts/ck_freenom.py.md)。
- `scripts/ck_game163.py`：必选 `GAME163_AUTHORIZATION`；详见 [ck_game163.py.md](docs/scripts/ck_game163.py.md)。
- `scripts/ck_meizu.py`：必选 `MEIZU_COOKIE`；详见 [ck_meizu.py.md](docs/scripts/ck_meizu.py.md)。
- `scripts/ck_mgtv.py`：必选 `MGTV_PARAMS`；详见 [ck_mgtv.py.md](docs/scripts/ck_mgtv.py.md)。
- `scripts/ck_mimotion.py`：必选 `MIMOTION_ACCOUNTS`；详见 [ck_mimotion.py.md](docs/scripts/ck_mimotion.py.md)。
- `scripts/ck_oneplusbbs.py`：必选 `ONEPLUSBBS`；详见 [ck_oneplusbbs.py.md](docs/scripts/ck_oneplusbbs.py.md)。
- `scripts/codearts_daily.py`：必选 `CODEARTS_CREDENTIALS`；详见 [codearts_daily.py.md](docs/scripts/codearts_daily.py.md)。
- `scripts/comicai_ai_cookie.py`：必选 `COMICAI_ACCOUNTS`；详见 [comicai_ai_cookie.py.md](docs/scripts/comicai_ai_cookie.py.md)。
- `scripts/crealitycloud_checkin.py`：必选 `CREALITY_ACCOUNTS`；详见 [crealitycloud_checkin.py.md](docs/scripts/crealitycloud_checkin.py.md)。
- `scripts/dachao.py`：必选 `DACHAO_ACCOUNTS`；详见 [dachao.py.md](docs/scripts/dachao.py.md)。
- `scripts/dahai.js`：必选 `DAHAI_COOKIE_LIST`；详见 [dahai.js.md](docs/scripts/dahai.js.md)。
- `scripts/daily_benefits.py`：必选 `WPS_ACCOUNTS`；详见 [daily_benefits.py.md](docs/scripts/daily_benefits.py.md)。
- `scripts/dailynewscn.js`：必选 `DAILYNEWSCN_LIST`, `OILPRICE_LIST`；详见 [dailynewscn.js.md](docs/scripts/dailynewscn.js.md)。
- `scripts/ddnsto.py`：必选 `DDNSTO_ACCOUNTS`；详见 [ddnsto.py.md](docs/scripts/ddnsto.py.md)。
- `scripts/deepflood_checkin.py`：必选 `DEEPFLOOD_COOKIE`；详见 [deepflood_checkin.py.md](docs/scripts/deepflood_checkin.py.md)。
- `scripts/durex.py`：必选 `dlshyzx`；详见 [durex.py.md](docs/scripts/durex.py.md)。
- `scripts/enshan_checkin.py`：必选 `ENSHAN_COOKIE`；详见 [enshan_checkin.py.md](docs/scripts/enshan_checkin.py.md)。
- `scripts/epicfreegames.py`：必选 `EPIC_TG_ACCOUNTS`；详见 [epicfreegames.py.md](docs/scripts/epicfreegames.py.md)。
- `scripts/erke.py`：必选 `ERKE_ACCOUNTS`；详见 [erke.py.md](docs/scripts/erke.py.md)。
- `scripts/f1owkang_qingskyland_skyland.py`：必选 `SKYLAND_TOKENS`；详见 [f1owkang_qingskyland_skyland.py.md](docs/scripts/f1owkang_qingskyland_skyland.py.md)。
- `scripts/fnnasclub.py`：必选 `FNNASCLUB_COOKIE`；详见 [fnnasclub.py.md](docs/scripts/fnnasclub.py.md)。
- `scripts/forum_download.py`：必选 `FORUM_ACCOUNTS`；详见 [forum_download.py.md](docs/scripts/forum_download.py.md)。
- `scripts/fwxs_checkin.js`：必选 `fwxs`；详见 [fwxs_checkin.js.md](docs/scripts/fwxs_checkin.js.md)。
- `scripts/fxh.js`：必选 `fxhOpenId`；详见 [fxh.js.md](docs/scripts/fxh.js.md)。
- `scripts/get_yys_cgvideo.py`：必选 `YYS_OUTPUT_DIR`；详见 [get_yys_cgvideo.py.md](docs/scripts/get_yys_cgvideo.py.md)。
- `scripts/get_yys_imagelinks.py`：必选 无；详见 [get_yys_imagelinks.py.md](docs/scripts/get_yys_imagelinks.py.md)。
- `scripts/hellogithub.py`：必选 `HELLOGITHUB_STATE_FILE`；详见 [hellogithub.py.md](docs/scripts/hellogithub.py.md)。
- `scripts/hifiti_checkin.py`：必选 `HiFiTi_COOKIE`；详见 [hifiti_checkin.py.md](docs/scripts/hifiti_checkin.py.md)。
- `scripts/hlyl.py`：必选 `hlylck`；详见 [hlyl.py.md](docs/scripts/hlyl.py.md)。
- `scripts/hsay.py`：必选 `hsayCookie`；详见 [hsay.py.md](docs/scripts/hsay.py.md)。
- `scripts/huaruntong_wx.py`：必选 `HRT_WX_ACCOUNTS`；详见 [huaruntong_wx.py.md](docs/scripts/huaruntong_wx.py.md)。
- `scripts/hykb_gamesign.js`：必选 `HYKB_SCOOKIE`；详见 [hykb_gamesign.js.md](docs/scripts/hykb_gamesign.js.md)。
- `scripts/ikuuu_checkin.py`：必选 `IKUUU_ACCOUNT`；详见 [ikuuu_checkin.py.md](docs/scripts/ikuuu_checkin.py.md)。
- `scripts/imaotai.py`：必选 `IMAOTAI_ACCOUNTS`；详见 [imaotai.py.md](docs/scripts/imaotai.py.md)。
- `scripts/index.js`：必选 `PIXIV_ACCOUNTS`；详见 [index.js.md](docs/scripts/index.js.md)。
- `scripts/iqiyi_checkin.py`：必选 `IQIYI_COOKIES`；详见 [iqiyi_checkin.py.md](docs/scripts/iqiyi_checkin.py.md)。
- `scripts/jc_checkin.py`：必选 `JC_ACCOUNTS`, `BASE_URL`；详见 [jc_checkin.py.md](docs/scripts/jc_checkin.py.md)。
- `scripts/jcqd.py`：必选 `JCQD_ACCOUNTS`；详见 [jcqd.py.md](docs/scripts/jcqd.py.md)。
- `scripts/jingyiluntan_sign.py`：必选 `JYLT_Cookie`；详见 [jingyiluntan_sign.py.md](docs/scripts/jingyiluntan_sign.py.md)。
- `scripts/jissbon.py`：必选 `jsbaxfls`；详见 [jissbon.py.md](docs/scripts/jissbon.py.md)。
- `scripts/jyj.py`：必选 `jyjck`；详见 [jyj.py.md](docs/scripts/jyj.py.md)。
- `scripts/kanxue.js`：必选 `KANXUE_COOKIE_LIST`；详见 [kanxue.js.md](docs/scripts/kanxue.js.md)。
- `scripts/kgqq.py`：必选 `KGQQ_COOKIE`；详见 [kgqq.py.md](docs/scripts/kgqq.py.md)。
- `scripts/kjwj.py`：必选 `kjwj_info`；详见 [kjwj.py.md](docs/scripts/kjwj.py.md)。
- `scripts/kuaishou_reward_status.py`：必选 `KUAISHOU_COOKIE`；详见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/kuku_daily.py`：必选 `KUKU_ACCOUNTS`；详见 [kuku_daily.py.md](docs/scripts/kuku_daily.py.md)。
- `scripts/kurobbs_sign.py`：必选 `KUROBBS_ACCOUNTS`；详见 [kurobbs_sign.py.md](docs/scripts/kurobbs_sign.py.md)。
- `scripts/l.py`：必选 `LINUXDO_COOKIES`；详见 [l.py.md](docs/scripts/l.py.md)。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`：必选 `LEAFLOW_COOKIE`；详见 [leaflow_checkin_pyleaflow_checkin.py.md](docs/scripts/leaflow_checkin_pyleaflow_checkin.py.md)。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`：必选 `NZZ_COOKIE`；详见 [littlewuh_qinglongbox_dailycheckin_scripts.py.md](docs/scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md)。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`：必选 `NODESEEK_COOKIE`；详见 [lizhixu_ql_script_hub_nodeseek.py.md](docs/scripts/lizhixu_ql_script_hub_nodeseek.py.md)。
- `scripts/lizhixu_ql_script_hub_youdao.py`：必选 `YOUDAO_COOKIE`；详见 [lizhixu_ql_script_hub_youdao.py.md](docs/scripts/lizhixu_ql_script_hub_youdao.py.md)。
- `scripts/lobsterai_checkin.py`：必选 `LOBSTERAI_TOKEN`；详见 [lobsterai_checkin.py.md](docs/scripts/lobsterai_checkin.py.md)。
- `scripts/loomy_daily.py`：必选 `LOOMY_TOKENS`；详见 [loomy_daily.py.md](docs/scripts/loomy_daily.py.md)。
- `scripts/lynkco_qinglong_single.py`：必选 `LYNKCO_ACCOUNTS`, `LYNKCO_APP_SECRETS`；详见 [lynkco_qinglong_single.py.md](docs/scripts/lynkco_qinglong_single.py.md)。
- `scripts/main.py`：必选 `WALLHAVEN_SAVE_DIR`；详见 [main.py.md](docs/scripts/main.py.md)。
- `scripts/mifan_optimized.py`：必选 `MIFAN_ACCOUNTS`；详见 [mifan_optimized.py.md](docs/scripts/mifan_optimized.py.md)。
- `scripts/mimotion.py`：必选 `MIMOTION_ACCOUNTS`；详见 [mimotion.py.md](docs/scripts/mimotion.py.md)。
- `scripts/netease_task.py`：必选 `NETEASE_COOKIE`, `NETEASE_API_BASE`；详见 [netease_task.py.md](docs/scripts/netease_task.py.md)。
- `scripts/nga_checkin.py`：必选 `NGA_ACCOUNT`；详见 [nga_checkin.py.md](docs/scripts/nga_checkin.py.md)。
- `scripts/nodeseek.py`：必选 `NS_COOKIE`；详见 [nodeseek.py.md](docs/scripts/nodeseek.py.md)。
- `scripts/nodeseek_checkin.py`：必选 `NODESEEK_COOKIE`；详见 [nodeseek_checkin.py.md](docs/scripts/nodeseek_checkin.py.md)。
- `scripts/nte.py`：必选 `NTE_TOKEN`；详见 [nte.py.md](docs/scripts/nte.py.md)。
- `scripts/officeace_daily.py`：必选 `OFFICEACE_TOKENS`；详见 [officeace_daily.py.md](docs/scripts/officeace_daily.py.md)。
- `scripts/ole.py`：必选 `OLE_ACCOUNTS`；详见 [ole.py.md](docs/scripts/ole.py.md)。
- `scripts/passnat_checkin.py`：必选 `PASSNAT_SK`；详见 [passnat_checkin.py.md](docs/scripts/passnat_checkin.py.md)。
- `scripts/psnine.py`：必选 `PSNINE_ACCOUNTS`；详见 [psnine.py.md](docs/scripts/psnine.py.md)。
- `scripts/pt_sign_v5.js`：必选 `PT_SITE_HDKYL_CK`, `PT_SITE_CARPT_CK`, `PT_SITE_AFUN_CK`；详见 [pt_sign_v5.js.md](docs/scripts/pt_sign_v5.js.md)。
- `scripts/qoder_airscript.js`：必选 `QODER_ACCOUNTS`；详见 [qoder_airscript.js.md](docs/scripts/qoder_airscript.js.md)。
- `scripts/quark_signin.py`：必选 `QUARK_COOKIE`；详见 [quark_signin.py.md](docs/scripts/quark_signin.py.md)。
- `scripts/raccoon_daily.py`：必选 `RACCOON_TOKENS`；详见 [raccoon_daily.py.md](docs/scripts/raccoon_daily.py.md)。
- `scripts/rainyun.py`：必选 `rainyun_ck`；详见 [rainyun.py.md](docs/scripts/rainyun.py.md)。
- `scripts/rousi_checkin.js`：必选 `ROUSI_TOKEN`；详见 [rousi_checkin.js.md](docs/scripts/rousi_checkin.js.md)。
- `scripts/sf.py`：必选 `SF_ACCOUNTS`；详见 [sf.py.md](docs/scripts/sf.py.md)。
- `scripts/sfsu_checkin.py`：必选 `sfsyUrl`；详见 [sfsu_checkin.py.md](docs/scripts/sfsu_checkin.py.md)。
- `scripts/sgs.py`：必选 `sgs`；详见 [sgs.py.md](docs/scripts/sgs.py.md)。
- `scripts/shuyi.py`：必选 `sysxc_auth`；详见 [shuyi.py.md](docs/scripts/shuyi.py.md)。
- `scripts/sign_in.py`：必选 `KANXUE_ACCOUNTS`；详见 [sign_in.py.md](docs/scripts/sign_in.py.md)。
- `scripts/skland_daily.py`：必选 `SKLAND_TOKEN`；详见 [skland_daily.py.md](docs/scripts/skland_daily.py.md)。
- `scripts/skland_demo.py`：必选 `SKLAND_ACCOUNTS`；详见 [skland_demo.py.md](docs/scripts/skland_demo.py.md)。
- `scripts/skyland.py`：必选 `SKYLAND_TOKEN`；详见 [skyland.py.md](docs/scripts/skyland.py.md)。
- `scripts/smzdm_checkin.js`：必选 `SMZDM_ACCOUNT`；详见 [smzdm_checkin.js.md](docs/scripts/smzdm_checkin.js.md)。
- `scripts/ssl_cert_check.py`：必选 `SSL_ACCOUNTS`；详见 [ssl_cert_check.py.md](docs/scripts/ssl_cert_check.py.md)。
- `scripts/sudojia_33agilestudio.js`：必选 `AGILE_STUDIO_ACCOUNTS`；详见 [sudojia_33agilestudio.js.md](docs/scripts/sudojia_33agilestudio.js.md)。
- `scripts/sudojia_allgirls.js`：必选 `ALL_GIRLS_TOKEN`；详见 [sudojia_allgirls.js.md](docs/scripts/sudojia_allgirls.js.md)。
- `scripts/sudojia_amx.js`：必选 `AMX_TOKEN`；详见 [sudojia_amx.js.md](docs/scripts/sudojia_amx.js.md)。
- `scripts/sudojia_authcheck.js`：必选 `AUTH_CHECK_ACCOUNTS`；详见 [sudojia_authcheck.js.md](docs/scripts/sudojia_authcheck.js.md)。
- `scripts/sudojia_bananavideo.js`：必选 `BANANA_ACCOUNT`；详见 [sudojia_bananavideo.js.md](docs/scripts/sudojia_bananavideo.js.md)。
- `scripts/sudojia_beiyinmei.js`：必选 `BYM_ACCOUNT`；详见 [sudojia_beiyinmei.js.md](docs/scripts/sudojia_beiyinmei.js.md)。
- `scripts/sudojia_botanystar.js`：必选 `BOTANY_ACCOUNT`；详见 [sudojia_botanystar.js.md](docs/scripts/sudojia_botanystar.js.md)。
- `scripts/sudojia_bwtea.js`：必选 `BW_TEA_TOKEN`；详见 [sudojia_bwtea.js.md](docs/scripts/sudojia_bwtea.js.md)。
- `scripts/sudojia_colorful_mall.js`：必选 `COLORFUL_TOKEN`；详见 [sudojia_colorful_mall.js.md](docs/scripts/sudojia_colorful_mall.js.md)。
- `scripts/sudojia_flyant.js`：必选 `FLY_ANT_TOKEN`；详见 [sudojia_flyant.js.md](docs/scripts/sudojia_flyant.js.md)。
- `scripts/sudojia_fnnas.js`：必选 `FN_NAS_COOKIE`；详见 [sudojia_fnnas.js.md](docs/scripts/sudojia_fnnas.js.md)。
- `scripts/sudojia_hgf.js`：必选 `HGF_COOKIE`；详见 [sudojia_hgf.js.md](docs/scripts/sudojia_hgf.js.md)。
- `scripts/sudojia_hlzj_game.js`：必选 `HLZJ_UNID`；详见 [sudojia_hlzj_game.js.md](docs/scripts/sudojia_hlzj_game.js.md)。
- `scripts/sudojia_hzhfp.js`：必选 `HZHFP_TOKEN`；详见 [sudojia_hzhfp.js.md](docs/scripts/sudojia_hzhfp.js.md)。
- `scripts/sudojia_instax.js`：必选 `INSTAX_TOKEN`；详见 [sudojia_instax.js.md](docs/scripts/sudojia_instax.js.md)。
- `scripts/sudojia_jhcard.js`：必选 `JHCARD_BODY`；详见 [sudojia_jhcard.js.md](docs/scripts/sudojia_jhcard.js.md)。
- `scripts/sudojia_jiangshan.js`：必选 `JIANG_SHAN_SESSION`；详见 [sudojia_jiangshan.js.md](docs/scripts/sudojia_jiangshan.js.md)。
- `scripts/sudojia_jindian.js`：必选 `JINDIAN_TOKEN`；详见 [sudojia_jindian.js.md](docs/scripts/sudojia_jindian.js.md)。
- `scripts/sudojia_jlc_yj.js`：必选 `JLC_COOKIE`；详见 [sudojia_jlc_yj.js.md](docs/scripts/sudojia_jlc_yj.js.md)。
- `scripts/sudojia_juejin.js`：必选 `JUEJIN_COOKIE`；详见 [sudojia_juejin.js.md](docs/scripts/sudojia_juejin.js.md)。
- `scripts/sudojia_kozbs.js`：必选 `KOZBS_TOKEN`；详见 [sudojia_kozbs.js.md](docs/scripts/sudojia_kozbs.js.md)。
- `scripts/sudojia_ktgzs.js`：必选 `KTGZS_TOKEN`；详见 [sudojia_ktgzs.js.md](docs/scripts/sudojia_ktgzs.js.md)。
- `scripts/sudojia_kukahome.js`：必选 `GU_HOME_TOKEN`, `GU_HOME_APP_SECRET`；详见 [sudojia_kukahome.js.md](docs/scripts/sudojia_kukahome.js.md)。
- `scripts/sudojia_kuro.js`：必选 `KURO_TOKEN`；详见 [sudojia_kuro.js.md](docs/scripts/sudojia_kuro.js.md)。
- `scripts/sudojia_laoban.js`：必选 `LAOBAN_OPENID`；详见 [sudojia_laoban.js.md](docs/scripts/sudojia_laoban.js.md)。
- `scripts/sudojia_longfor.js`：必选 `LONG_FOR_TOKEN`；详见 [sudojia_longfor.js.md](docs/scripts/sudojia_longfor.js.md)。
- `scripts/sudojia_mallcoo.js`：必选 `MALLCOO_TOKEN`；详见 [sudojia_mallcoo.js.md](docs/scripts/sudojia_mallcoo.js.md)。
- `scripts/sudojia_mawuwang.js`：必选 `MAWUW_TOKEN`；详见 [sudojia_mawuwang.js.md](docs/scripts/sudojia_mawuwang.js.md)。
- `scripts/sudojia_midea.js`：必选 `MIDEA_COOKIE`；详见 [sudojia_midea.js.md](docs/scripts/sudojia_midea.js.md)。
- `scripts/sudojia_moto.js`：必选 `MOTO_TOKEN`；详见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。
- `scripts/sudojia_mxbc.js`：必选 `MXBC_TOKEN`, `MXBC_SIGNING_KEY`；详见 [sudojia_mxbc.js.md](docs/scripts/sudojia_mxbc.js.md)。
- `scripts/sudojia_naixue.js`：必选 `NAIXUE_TOKEN`；详见 [sudojia_naixue.js.md](docs/scripts/sudojia_naixue.js.md)。
- `scripts/sudojia_nestle.js`：必选 `NESTLE_TOKEN`；详见 [sudojia_nestle.js.md](docs/scripts/sudojia_nestle.js.md)。
- `scripts/sudojia_nfhk.js`：必选 `NFHK_COOKIE`；详见 [sudojia_nfhk.js.md](docs/scripts/sudojia_nfhk.js.md)。
- `scripts/sudojia_opposhop.js`：必选 `OPPOSHOP_ACCOUNTS`；详见 [sudojia_opposhop.js.md](docs/scripts/sudojia_opposhop.js.md)。
- `scripts/sudojia_pangge.js`：必选 `PANG_GE_TOKEN`；详见 [sudojia_pangge.js.md](docs/scripts/sudojia_pangge.js.md)。
- `scripts/sudojia_paotea.js`：必选 `PAO_TEA_TOKEN`；详见 [sudojia_paotea.js.md](docs/scripts/sudojia_paotea.js.md)。
- `scripts/sudojia_shmedia.js`：必选 `SHYP_TOKEN`；详见 [sudojia_shmedia.js.md](docs/scripts/sudojia_shmedia.js.md)。
- `scripts/sudojia_shuifei.js`：必选 `SHUI_FEI_COOKIE`；详见 [sudojia_shuifei.js.md](docs/scripts/sudojia_shuifei.js.md)。
- `scripts/sudojia_sspanel.js`：必选 `SITE_ACCOUNTS`；详见 [sudojia_sspanel.js.md](docs/scripts/sudojia_sspanel.js.md)。
- `scripts/sudojia_starmom.js`：必选 `STAR_MOM_TOKEN`；详见 [sudojia_starmom.js.md](docs/scripts/sudojia_starmom.js.md)。
- `scripts/sudojia_tebu.js`：必选 `TEBU_TOKEN`；详见 [sudojia_tebu.js.md](docs/scripts/sudojia_tebu.js.md)。
- `scripts/sudojia_tilta.js`：必选 `TILTA_TOKEN`；详见 [sudojia_tilta.js.md](docs/scripts/sudojia_tilta.js.md)。
- `scripts/sudojia_tuchong.js`：必选 `TUC_ACCOUNTS`；详见 [sudojia_tuchong.js.md](docs/scripts/sudojia_tuchong.js.md)。
- `scripts/sudojia_v2ex.js`：必选 `V2EX_COOKIE`；详见 [sudojia_v2ex.js.md](docs/scripts/sudojia_v2ex.js.md)。
- `scripts/sudojia_wnna.js`：必选 `WNNA_TOKEN`；详见 [sudojia_wnna.js.md](docs/scripts/sudojia_wnna.js.md)。
- `scripts/sudojia_xhn.js`：必选 `XHN_ACCOUNTS`；详见 [sudojia_xhn.js.md](docs/scripts/sudojia_xhn.js.md)。
- `scripts/sudojia_xiangwan.js`：必选 `XWGAME_ACCOUNTS`；详见 [sudojia_xiangwan.js.md](docs/scripts/sudojia_xiangwan.js.md)。
- `scripts/sudojia_xiaomi_community.js`：必选 `XIAOMI_COMM_COOKIE`；详见 [sudojia_xiaomi_community.js.md](docs/scripts/sudojia_xiaomi_community.js.md)。
- `scripts/sudojia_xinxi.js`：必选 `XINXI_TOKEN`；详见 [sudojia_xinxi.js.md](docs/scripts/sudojia_xinxi.js.md)。
- `scripts/sudojia_xpfarm.js`：必选 `XPFARM_TOKEN`；详见 [sudojia_xpfarm.js.md](docs/scripts/sudojia_xpfarm.js.md)。
- `scripts/sudojia_znds.js`：必选 `ZNDS_COOKIE`；详见 [sudojia_znds.js.md](docs/scripts/sudojia_znds.js.md)。
- `scripts/sudojia_zxice.js`：必选 `ZX_ICE_TOKEN`；详见 [sudojia_zxice.js.md](docs/scripts/sudojia_zxice.js.md)。
- `scripts/supertopicsign.py`：必选 `WEIBO_SUPERTOPIC_ACCOUNTS`；详见 [supertopicsign.py.md](docs/scripts/supertopicsign.py.md)。
- `scripts/synspoint.py`：必选 `synshd`；详见 [synspoint.py.md](docs/scripts/synspoint.py.md)。
- `scripts/task_ef2d3863.js`：必选 `refreshToken`；详见 [task_ef2d3863.js.md](docs/scripts/task_ef2d3863.js.md)。
- `scripts/tencent_video_checkin.py`：必选 `TENCENT_VIDEO_COOKIES`；详见 [tencent_video_checkin.py.md](docs/scripts/tencent_video_checkin.py.md)。
- `scripts/tieba_checkin.py`：必选 `TIEBA_COOKIE`；详见 [tieba_checkin.py.md](docs/scripts/tieba_checkin.py.md)。
- `scripts/tjd_daily.py`：必选 `TJD_ACCOUNTS`；详见 [tjd_daily.py.md](docs/scripts/tjd_daily.py.md)。
- `scripts/trae_checkin.py`：必选 `TRAE_ACCOUNTS`；详见 [trae_checkin.py.md](docs/scripts/trae_checkin.py.md)。
- `scripts/tsthb_checkin.py`：必选 `tsthbck`；详见 [tsthb_checkin.py.md](docs/scripts/tsthb_checkin.py.md)。
- `scripts/ty_netdisk_checkin.py`：必选 `TY_ACCOUNTS`；详见 [ty_netdisk_checkin.py.md](docs/scripts/ty_netdisk_checkin.py.md)。
- `scripts/tyqhdraw.py`：必选 `tyqhCookie`；详见 [tyqhdraw.py.md](docs/scripts/tyqhdraw.py.md)。
- `scripts/valorantstore.py`：必选 `VALORANT_COOKIE`；详见 [valorantstore.py.md](docs/scripts/valorantstore.py.md)。
- `scripts/vortexa_free_claim.js`：必选 `VORTEXA_ACCOUNTS`；详见 [vortexa_free_claim.js.md](docs/scripts/vortexa_free_claim.js.md)。
- `scripts/wangchao.py`：必选 `WangChao`；详见 [wangchao.py.md](docs/scripts/wangchao.py.md)。
- `scripts/wentiweilaihui.py`：必选 `WENTIWEILAIHUI_ACCOUNTS`；详见 [wentiweilaihui.py.md](docs/scripts/wentiweilaihui.py.md)。
- `scripts/workbuddy.py`：必选 `WORKBUDDY_ACCOUNTS`；详见 [workbuddy.py.md](docs/scripts/workbuddy.py.md)。
- `scripts/workbuddy_daily.py`：必选 `WORKBUDDY_REFRESH_TOKEN`, `WORKBUDDY_INTL_TOKENS`；详见 [workbuddy_daily.py.md](docs/scripts/workbuddy_daily.py.md)。
- `scripts/wps_clock_in.py`：必选 `wps_ck`；详见 [wps_clock_in.py.md](docs/scripts/wps_clock_in.py.md)。
- `scripts/wyycg.py`：必选 `WYYCG_ACCOUNTS`；详见 [wyycg.py.md](docs/scripts/wyycg.py.md)。
- `scripts/yht.py`：必选 `Yht_token`；详见 [yht.py.md](docs/scripts/yht.py.md)。
- `scripts/youdao.py`：必选 `YOUDAO_COOKIE`；详见 [youdao.py.md](docs/scripts/youdao.py.md)。
- `scripts/yyshuijuantime.py`：必选 `YYS_HUIJUAN_OUTPUT`；详见 [yyshuijuantime.py.md](docs/scripts/yyshuijuantime.py.md)。
- `scripts/zcode_cn_daily.py`：必选 `ZCODE_CN_TOKENS`；详见 [zcode_cn_daily.py.md](docs/scripts/zcode_cn_daily.py.md)。
- `scripts/zippo.py`：必选 `zippoCookie`；详见 [zippo.py.md](docs/scripts/zippo.py.md)。
- `scripts/zodgame_test.py`：必选 `ZODGAME_COOKIE`；详见 [zodgame_test.py.md](docs/scripts/zodgame_test.py.md)。

### 可选参数

可选变量同样写在各脚本详单中，不需要自定义行为时可先不配置。

## 参数获取方法

每个脚本的参数获取步骤写在对应详单的「环境变量与参数」中。优先打开上方「待检查脚本」清单中的链接逐项配置。

## 验证与兼容性

- `scripts/139_yunduo.py`（待检查）：SHA-256 `c37eff8c6b1d510213e6ec929a3f4505e7ecf43f6934c655d924fd0165024942`；基础核验通过，业务待检查。详见 [139_yunduo.py.md](docs/scripts/139_yunduo.py.md)。
- `scripts/2cycdx.py`（待检查）：SHA-256 `50e848475c664acc9e2f665f75dd6c0f4b72d770e94fea08f421185fdbd77d1b`；基础核验通过，业务待检查。详见 [2cycdx.py.md](docs/scripts/2cycdx.py.md)。
- `scripts/51cto_sign.js`（待检查）：SHA-256 `0f62a8d10db8c2b4dd354e467d57274ec1ed97c9734cd4ac1965a96be9e43410`；基础核验通过，业务待检查。详见 [51cto_sign.js.md](docs/scripts/51cto_sign.js.md)。
- `scripts/52pojie.js`（待检查）：SHA-256 `8477d0f2eec2d4cc38799acc921cd04b11d9648be363ee519d8bb51d3d15f664`；基础核验通过，业务待检查。详见 [52pojie.js.md](docs/scripts/52pojie.js.md)。
- `scripts/999.py`（待检查）：SHA-256 `c42405330b4bfbd4f50bdc0b0e37203134a0ea24701f9d51e3e5a5a680419b84`；基础核验通过，业务待检查。详见 [999.py.md](docs/scripts/999.py.md)。
- `scripts/acfun.py`（待检查）：SHA-256 `006ac42bec4fba6c9e41599da022e9b425b4ca5b6617bcd66c0403ab8917ed65`；基础核验通过，业务待检查。详见 [acfun.py.md](docs/scripts/acfun.py.md)。
- `scripts/agentrouter.py`（待检查）：SHA-256 `a22e06bb7c32b2ce57c1dbbea73b86dac505381bde53a818ec84254669f4c888`；基础核验通过，业务待检查。详见 [agentrouter.py.md](docs/scripts/agentrouter.py.md)。
- `scripts/airport.py`（待检查）：SHA-256 `751d2835e39d2431905eacf72fc64a9cddfb4fac8032eaa83bc7af4632e7983d`；基础核验通过，业务待检查。详见 [airport.py.md](docs/scripts/airport.py.md)。
- `scripts/akile_checkin.py`（待检查）：SHA-256 `414598a6cc00cd6d0f804fb48bb2bed84dc8b9a64ca5fad8687925799c3e85be`；基础核验通过，业务待检查。详见 [akile_checkin.py.md](docs/scripts/akile_checkin.py.md)。
- `scripts/aliyun_web.js`（待检查）：SHA-256 `e3a41513e0fa2aeb85a4af8d6d321c03ccac7a069071dd2b96067077e0f19676`；基础核验通过，业务待检查。详见 [aliyun_web.js.md](docs/scripts/aliyun_web.js.md)。
- `scripts/aliyundrive_checkin.js`（待检查）：SHA-256 `e247d342c3624bc2e7cc9da6f1808d8dfeffe19f1df4a64d3a410b2b87a4ac0b`；基础核验通过，业务待检查。详见 [aliyundrive_checkin.js.md](docs/scripts/aliyundrive_checkin.js.md)。
- `scripts/aliyunpan_checkin.py`（待检查）：SHA-256 `ed1ba9f840e3411c993266ae1b29c1db3cd968bf49f318d682fea69aab37815c`；基础核验通过，业务待检查。详见 [aliyunpan_checkin.py.md](docs/scripts/aliyunpan_checkin.py.md)。
- `scripts/aolaxing.py`（待检查）：SHA-256 `5e2e40940a4bd132b7f240273fe1e6850ace43aa93856a8ee9871aa263ee7b46`；基础核验通过，业务待检查。详见 [aolaxing.py.md](docs/scripts/aolaxing.py.md)。
- `scripts/api_hax.py`（待检查）：SHA-256 `b82b5df5898bca09afb910abd7db43507e0fa2b93866ffd7fec97e722e3b8d49`；基础核验通过，业务待检查。详见 [api_hax.py.md](docs/scripts/api_hax.py.md)。
- `scripts/arknightsbanner.py`（待检查）：SHA-256 `e8f9017bbd7ddf89573d8a0e04bc5bdef09d8f3aa0da333b42a57e5df74e9161`；基础核验通过，业务待检查。详见 [arknightsbanner.py.md](docs/scripts/arknightsbanner.py.md)。
- `scripts/atxyq.py`（待检查）：SHA-256 `6d8723d7248ad77b80ee7a77734038bb6dae5c87cdebc86da19af1319553fcf1`；基础核验通过，业务待检查。详见 [atxyq.py.md](docs/scripts/atxyq.py.md)。
- `scripts/auto_buy.py`（待检查）：SHA-256 `551b1099baab98acf5d68dc9ff68add1914aad1763a9fec69ee6ffe93852b859`；基础核验通过，业务待检查。详见 [auto_buy.py.md](docs/scripts/auto_buy.py.md)。
- `scripts/autoclaw_cn_daily.py`（待检查）：SHA-256 `f8bdc918bce6376ca7e1a8cb8d182c987fd9ff3286a808187d66a3768305a426`；基础核验通过，业务待检查。详见 [autoclaw_cn_daily.py.md](docs/scripts/autoclaw_cn_daily.py.md)。
- `scripts/autosignin.js`（待检查）：SHA-256 `c9f9cb1e7cf025514b245d555ac63849d2617eb3d29b473f92cf61f6b2a4a72b`；基础核验通过，业务待检查。详见 [autosignin.js.md](docs/scripts/autosignin.js.md)。
- `scripts/autosignin.py`（待检查）：SHA-256 `cd2b330788aa14bc2e020a5451329f291e5d1dd97f66ad0a6ed2c921b6dee3d8`；基础核验通过，业务待检查。详见 [autosignin.py.md](docs/scripts/autosignin.py.md)。
- `scripts/baidu.py`（待检查）：SHA-256 `f3bfc64c4f219e4c451796542f4d2af0605812c82ab871f29039441d108afd1a`；基础核验通过，业务待检查。详见 [baidu.py.md](docs/scripts/baidu.py.md)。
- `scripts/baiduwangpan_checkin.py`（上架）：SHA-256 `e9c658f4544427bd94ab4da74a724038d1f849c8b9665464ded6e8a1c4dd2c18`；含 live 业务证据。详见 [baiduwangpan_checkin.py.md](docs/scripts/baiduwangpan_checkin.py.md)。
- `scripts/baiduwp.py`（待检查）：SHA-256 `419008b91e8a348b310d5de9d819e6670ec665dd212922406e85348e52f6b0d6`；基础核验通过，业务待检查。详见 [baiduwp.py.md](docs/scripts/baiduwp.py.md)。
- `scripts/bilibili.py`（待检查）：SHA-256 `b9d238f43b63599e7dfac7bac80c8f2de6b13eaa657e8f589a7a9039ab4f1f8c`；基础核验通过，业务待检查。详见 [bilibili.py.md](docs/scripts/bilibili.py.md)。
- `scripts/bsly_draw.py`（待检查）：SHA-256 `ae1d0fe072b35fe9c22ad02ebc04ca2b0571c7cf0e60c3ad68e2c8cca58925a3`；基础核验通过，业务待检查。详见 [bsly_draw.py.md](docs/scripts/bsly_draw.py.md)。
- `scripts/bugutv.py`（待检查）：SHA-256 `655c9b0fad89e4df49112865cea7fe78d7fe8f4f5a4a12649ea5a8a532cb1a97`；基础核验通过，业务待检查。详见 [bugutv.py.md](docs/scripts/bugutv.py.md)。
- `scripts/bwcj.py`（待检查）：SHA-256 `ae20e692177d7102468ed3ddc462576f39fd2c81ea51a9dad626e138700ac4af`；基础核验通过，业务待检查。详见 [bwcj.py.md](docs/scripts/bwcj.py.md)。
- `scripts/caigamer.js`（待检查）：SHA-256 `fd3bdc3108575c6901f1f9d8626e1a039f85da54bb2d200d3dd28124f794bd01`；基础核验通过，业务待检查。详见 [caigamer.js.md](docs/scripts/caigamer.js.md)。
- `scripts/cdrail.py`（待检查）：SHA-256 `5caed175e6b1ff5b1033fbbd59105a71dfb952c8dd79bc9b92f3d354a69e5225`；基础核验通过，业务待检查。详见 [cdrail.py.md](docs/scripts/cdrail.py.md)。
- `scripts/cfmoto_checkin.py`（上架）：SHA-256 `15ecc5e482af800b18360374359667392176fe88ab77c7950509da115f09f07a`；含 live 业务证据。详见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/cg163_autocheckin.py`（待检查）：SHA-256 `fc594db2c57c2b95da1b8dc4bdb49d887ad50e6d22ff58d3f7af82b1bf76d074`；基础核验通过，业务待检查。详见 [cg163_autocheckin.py.md](docs/scripts/cg163_autocheckin.py.md)。
- `scripts/chevrolet.js`（待检查）：SHA-256 `fc9137b46f1cb49c1d8f9523c145651d9453fbf8beac391fcc85039a950d7cd2`；基础核验通过，业务待检查。详见 [chevrolet.js.md](docs/scripts/chevrolet.js.md)。
- `scripts/ck_2nzz.py`（待检查）：SHA-256 `7f3516766b49802f68470d5adb40d69a59014b79178df5de52a083e60f8af02b`；基础核验通过，业务待检查。详见 [ck_2nzz.py.md](docs/scripts/ck_2nzz.py.md)。
- `scripts/ck_acfun.py`（待检查）：SHA-256 `1e650693abb1fbf6f49934ed22d3ac1ff876d5c4ab719c232c57a5f15212af15`；基础核验通过，业务待检查。详见 [ck_acfun.py.md](docs/scripts/ck_acfun.py.md)。
- `scripts/ck_airport.py`（待检查）：SHA-256 `9a5dc96063ef5b2e77ac8c1bab75562901852657bb2d51fa1d5f7ce2d859f848`；基础核验通过，业务待检查。详见 [ck_airport.py.md](docs/scripts/ck_airport.py.md)。
- `scripts/ck_aqc.js`（待检查）：SHA-256 `50092e54a944fd3c08f134bbed637e9c0a1d923bc416018811ae437ba5485fc8`；基础核验通过，业务待检查。详见 [ck_aqc.js.md](docs/scripts/ck_aqc.js.md)。
- `scripts/ck_baidu_url_submit.py`（待检查）：SHA-256 `ab3ff2232123e9a8d0a05f1a738b6b3c632ff7797d6fb51ecc32f0565ed12423`；基础核验通过，业务待检查。详见 [ck_baidu_url_submit.py.md](docs/scripts/ck_baidu_url_submit.py.md)。
- `scripts/ck_bilibili.py`（待检查）：SHA-256 `7d12bb124f137766e58e75551367d57af0e15dbfc07efc8da129bc6b71df820b`；基础核验通过，业务待检查。详见 [ck_bilibili.py.md](docs/scripts/ck_bilibili.py.md)。
- `scripts/ck_ccava.py`（待检查）：SHA-256 `de4c8a9cb4f76800d04f9aca4d80b49599231295f1a1f0dff1e922c5eb4bd360`；基础核验通过，业务待检查。详见 [ck_ccava.py.md](docs/scripts/ck_ccava.py.md)。
- `scripts/ck_csdn.py`（待检查）：SHA-256 `5ee4485d4cbbe36ccff6b5fd298dc3d0cba445e2a35d6dab5929a48454d7159b`；基础核验通过，业务待检查。详见 [ck_csdn.py.md](docs/scripts/ck_csdn.py.md)。
- `scripts/ck_du163.js`（待检查）：SHA-256 `75d6aa77f89a9e3f51773b5e963b147b2ae8537d66f1a55ac7efd735f1c808e0`；基础核验通过，业务待检查。详见 [ck_du163.js.md](docs/scripts/ck_du163.js.md)。
- `scripts/ck_duokan.py`（待检查）：SHA-256 `761187366b78083a2345c626db63d1ed6104b63f726bfd37fd2bc99f4348861a`；基础核验通过，业务待检查。详见 [ck_duokan.py.md](docs/scripts/ck_duokan.py.md)。
- `scripts/ck_everphoto.py`（待检查）：SHA-256 `1c503ab4c6801ad18b37fa4b979bf3bf3bdb87dadace5ebb8d44c038966e35ae`；基础核验通过，业务待检查。详见 [ck_everphoto.py.md](docs/scripts/ck_everphoto.py.md)。
- `scripts/ck_fmapp.py`（待检查）：SHA-256 `cf54bcf59156219426860a1c43d3467c51b8a7ae3b1f726612aff8d51557d227`；基础核验通过，业务待检查。详见 [ck_fmapp.py.md](docs/scripts/ck_fmapp.py.md)。
- `scripts/ck_freenom.py`（待检查）：SHA-256 `924fc4494dcdf15d6aeb90d7f59dd6438878241af726c137fdad9e5b38099cdb`；基础核验通过，业务待检查。详见 [ck_freenom.py.md](docs/scripts/ck_freenom.py.md)。
- `scripts/ck_game163.py`（待检查）：SHA-256 `7ed0cd491d05665776eca881d37deab2c42b356bc28ab3b1735f544fc6d56b4d`；基础核验通过，业务待检查。详见 [ck_game163.py.md](docs/scripts/ck_game163.py.md)。
- `scripts/ck_meizu.py`（待检查）：SHA-256 `b4aacb9c39582bc2b67c68e5ee5ede9d327a1df08b6b9d14ef23ef1658bb4f88`；基础核验通过，业务待检查。详见 [ck_meizu.py.md](docs/scripts/ck_meizu.py.md)。
- `scripts/ck_mgtv.py`（待检查）：SHA-256 `87ba378186422a2d560ae13c7cb814fbca39b9df9c488955d9db96b83e161ccb`；基础核验通过，业务待检查。详见 [ck_mgtv.py.md](docs/scripts/ck_mgtv.py.md)。
- `scripts/ck_mimotion.py`（待检查）：SHA-256 `9a640f375412c39df2651b8e557fa26f0b4f7784bc360c6144c29ffaacca4f51`；基础核验通过，业务待检查。详见 [ck_mimotion.py.md](docs/scripts/ck_mimotion.py.md)。
- `scripts/ck_oneplusbbs.py`（待检查）：SHA-256 `924c0a8026449096829e6622116ea2deab5b47b7614cd237c7760e810fdcf505`；基础核验通过，业务待检查。详见 [ck_oneplusbbs.py.md](docs/scripts/ck_oneplusbbs.py.md)。
- `scripts/codearts_daily.py`（待检查）：SHA-256 `c6bdd619ce35cd32e1fca575006e8420c6ac3b55d55cc1ffb48ba9122862d856`；基础核验通过，业务待检查。详见 [codearts_daily.py.md](docs/scripts/codearts_daily.py.md)。
- `scripts/comicai_ai_cookie.py`（待检查）：SHA-256 `173db2c22758f322022dedfb23fdd735a85d1cff0d39ad308ed5a8c3d0d45c8c`；基础核验通过，业务待检查。详见 [comicai_ai_cookie.py.md](docs/scripts/comicai_ai_cookie.py.md)。
- `scripts/crealitycloud_checkin.py`（待检查）：SHA-256 `65ca612e847d35d7aabc19505ed10d819c478e1bdda4b88321a9dc4c24e11743`；基础核验通过，业务待检查。详见 [crealitycloud_checkin.py.md](docs/scripts/crealitycloud_checkin.py.md)。
- `scripts/dachao.py`（待检查）：SHA-256 `5745d76090d1c471883f40df8aead8ad74fd0f1b7fe8db24c7b995bac3dc25a9`；基础核验通过，业务待检查。详见 [dachao.py.md](docs/scripts/dachao.py.md)。
- `scripts/dahai.js`（待检查）：SHA-256 `a07b71c7c9787d0b7034b5c8fda3aa3e70b2e96d2285b11e63b7e3fa35373b4d`；基础核验通过，业务待检查。详见 [dahai.js.md](docs/scripts/dahai.js.md)。
- `scripts/daily_benefits.py`（待检查）：SHA-256 `9a155b77acadb949a6fedf73bdd5e63ec7684a45fabd5143b66ac1873f27676b`；基础核验通过，业务待检查。详见 [daily_benefits.py.md](docs/scripts/daily_benefits.py.md)。
- `scripts/dailynewscn.js`（待检查）：SHA-256 `f2c3d44944b98f1c36d9d248b6b80554a34a74656b6df7d267acf7a1583b1268`；基础核验通过，业务待检查。详见 [dailynewscn.js.md](docs/scripts/dailynewscn.js.md)。
- `scripts/ddnsto.py`（待检查）：SHA-256 `a36378f008a43fa3824429fe8650bb693f256aba081914b5254cc51fcfe58087`；基础核验通过，业务待检查。详见 [ddnsto.py.md](docs/scripts/ddnsto.py.md)。
- `scripts/deepflood_checkin.py`（待检查）：SHA-256 `1743ea3da4f0ef463f70619fb5a49d375dc48e5817d867ea080875a12b3f68c4`；基础核验通过，业务待检查。详见 [deepflood_checkin.py.md](docs/scripts/deepflood_checkin.py.md)。
- `scripts/durex.py`（待检查）：SHA-256 `dcfd65a77d774a5ea04efb135a56f675f531c6fd11d770279ec6120cbd8e025c`；基础核验通过，业务待检查。详见 [durex.py.md](docs/scripts/durex.py.md)。
- `scripts/enshan_checkin.py`（待检查）：SHA-256 `bbf4daf1880caeb8d30c22e335df244f0aec8756937d3e810ef62da534899504`；基础核验通过，业务待检查。详见 [enshan_checkin.py.md](docs/scripts/enshan_checkin.py.md)。
- `scripts/epicfreegames.py`（待检查）：SHA-256 `c8d5c51c3bc4dfbfb194ddb29720a35d605c3285eca606ec4af7ffdff72d0d4a`；基础核验通过，业务待检查。详见 [epicfreegames.py.md](docs/scripts/epicfreegames.py.md)。
- `scripts/erke.py`（待检查）：SHA-256 `887228083c773feabe55dd6c936eec5ff029daf6c252a28f05732b9d32e83e59`；基础核验通过，业务待检查。详见 [erke.py.md](docs/scripts/erke.py.md)。
- `scripts/f1owkang_qingskyland_skyland.py`（待检查）：SHA-256 `2fa1e00174515df634f27a6225379ab867b62fcd9f4049f46a7431bc0efb7ed3`；基础核验通过，业务待检查。详见 [f1owkang_qingskyland_skyland.py.md](docs/scripts/f1owkang_qingskyland_skyland.py.md)。
- `scripts/fnnasclub.py`（待检查）：SHA-256 `80358575b8206ca830681be924da4c67dc20b6d4aa1e323a9f810fadff669cfc`；基础核验通过，业务待检查。详见 [fnnasclub.py.md](docs/scripts/fnnasclub.py.md)。
- `scripts/forum_download.py`（待检查）：SHA-256 `f7c36f3c4bb0ef72d1c9bdaec2387d373c870a5be4607ac71ed9f274c0339751`；基础核验通过，业务待检查。详见 [forum_download.py.md](docs/scripts/forum_download.py.md)。
- `scripts/fwxs_checkin.js`（待检查）：SHA-256 `e9f6410e225fbef75b20d661e4122ea2bece6b41b7908f17f4f42244f151780c`；基础核验通过，业务待检查。详见 [fwxs_checkin.js.md](docs/scripts/fwxs_checkin.js.md)。
- `scripts/fxh.js`（待检查）：SHA-256 `228504f8a8e327c856a9187a242e930442b57356490653b6e6c7e692509f4081`；基础核验通过，业务待检查。详见 [fxh.js.md](docs/scripts/fxh.js.md)。
- `scripts/get_yys_cgvideo.py`（待检查）：SHA-256 `5acaf38a721b681a7ea5a7ac0240d4116214d54ea3dde624435202a040af09cd`；基础核验通过，业务待检查。详见 [get_yys_cgvideo.py.md](docs/scripts/get_yys_cgvideo.py.md)。
- `scripts/get_yys_imagelinks.py`（待检查）：SHA-256 `ee7273bd292415bb0bad2603012b77b85fb0287709a5ca24d7f4e426408e3cf3`；基础核验通过，业务待检查。详见 [get_yys_imagelinks.py.md](docs/scripts/get_yys_imagelinks.py.md)。
- `scripts/hellogithub.py`（待检查）：SHA-256 `9ba47639b981f682c235acbddab2d09e14f1e0bc0737fc1d07171debe254a8ce`；基础核验通过，业务待检查。详见 [hellogithub.py.md](docs/scripts/hellogithub.py.md)。
- `scripts/hifiti_checkin.py`（待检查）：SHA-256 `ae18f25d6d7ad768ae64880761732b510e7bc3e75179bb9d66790f8203e4faf9`；基础核验通过，业务待检查。详见 [hifiti_checkin.py.md](docs/scripts/hifiti_checkin.py.md)。
- `scripts/hlyl.py`（待检查）：SHA-256 `ad472c7faec4d4ebd6c081c9abc6e3f6274a701c7a2f7284c0f6e7292878097d`；基础核验通过，业务待检查。详见 [hlyl.py.md](docs/scripts/hlyl.py.md)。
- `scripts/hsay.py`（待检查）：SHA-256 `334abc1e83a833188dedc6debb51a5f46c2bf1c7ffff2b2a0c57aeffb60954f7`；基础核验通过，业务待检查。详见 [hsay.py.md](docs/scripts/hsay.py.md)。
- `scripts/huaruntong_wx.py`（待检查）：SHA-256 `6fb8e542eeeed076b41be51b9c90430571698ff02226f25d85b83b54562a7c8e`；基础核验通过，业务待检查。详见 [huaruntong_wx.py.md](docs/scripts/huaruntong_wx.py.md)。
- `scripts/hykb_gamesign.js`（待检查）：SHA-256 `11f5887f78f37ed569c9d8c0e75944c30a98d62dca54cb30bddab8644d2e75ae`；基础核验通过，业务待检查。详见 [hykb_gamesign.js.md](docs/scripts/hykb_gamesign.js.md)。
- `scripts/ikuuu_checkin.py`（待检查）：SHA-256 `44c91448c6d2d8ef71df14ee1a232e58f45bd7b232ff8870983ff6379e378694`；基础核验通过，业务待检查。详见 [ikuuu_checkin.py.md](docs/scripts/ikuuu_checkin.py.md)。
- `scripts/imaotai.py`（待检查）：SHA-256 `9c2f6927060e1dfa9b08784217483bfe8e4979e81763380ed03ad98f3fa8bd66`；基础核验通过，业务待检查。详见 [imaotai.py.md](docs/scripts/imaotai.py.md)。
- `scripts/index.js`（待检查）：SHA-256 `b0f670de5353137cb479251c75283cf6960207864f98a92c687c46147f7db3d7`；基础核验通过，业务待检查。详见 [index.js.md](docs/scripts/index.js.md)。
- `scripts/iqiyi_checkin.py`（待检查）：SHA-256 `2829c7add08087e4c054a99ebc6b3f88c9e665a7a9310b713d19b2467acebed2`；基础核验通过，业务待检查。详见 [iqiyi_checkin.py.md](docs/scripts/iqiyi_checkin.py.md)。
- `scripts/jc_checkin.py`（待检查）：SHA-256 `a9e3d7940077da25253b9b49f7a39552ffe129ebf250bf5036d3a1dad18cc787`；基础核验通过，业务待检查。详见 [jc_checkin.py.md](docs/scripts/jc_checkin.py.md)。
- `scripts/jcqd.py`（待检查）：SHA-256 `ddbc8159cadbfeb3332e7ecfed3200f268bc1950c4fd4a6f6597b461ac7ad731`；基础核验通过，业务待检查。详见 [jcqd.py.md](docs/scripts/jcqd.py.md)。
- `scripts/jingyiluntan_sign.py`（待检查）：SHA-256 `0a3987df426c3b1aecf1022de9d2c61da039f8ce3c6dc0bebff7f6c50117ca3e`；基础核验通过，业务待检查。详见 [jingyiluntan_sign.py.md](docs/scripts/jingyiluntan_sign.py.md)。
- `scripts/jissbon.py`（待检查）：SHA-256 `6fac3023c4ba77d121f3e7679bd5a0cc28b3739bb988776f28a22fb80e9d20bf`；基础核验通过，业务待检查。详见 [jissbon.py.md](docs/scripts/jissbon.py.md)。
- `scripts/jyj.py`（待检查）：SHA-256 `28d1ce160e4bd75321dc615c98494c1703728f17bfb1bc4b692b5bc6f1278042`；基础核验通过，业务待检查。详见 [jyj.py.md](docs/scripts/jyj.py.md)。
- `scripts/kanxue.js`（待检查）：SHA-256 `e56f8983e110ca4e6d1af661b968a593a0b896fb9befb4f38f02f7ee95924466`；基础核验通过，业务待检查。详见 [kanxue.js.md](docs/scripts/kanxue.js.md)。
- `scripts/kgqq.py`（待检查）：SHA-256 `fd14c4b064a5168918f0d3eb0ea766762361151ca7c441e4188cd7b98c31d9a9`；基础核验通过，业务待检查。详见 [kgqq.py.md](docs/scripts/kgqq.py.md)。
- `scripts/kjwj.py`（待检查）：SHA-256 `6867c355c23ccfdd7deafbcbeef48865c1001d7e274c9b9e265dced5047eaaab`；基础核验通过，业务待检查。详见 [kjwj.py.md](docs/scripts/kjwj.py.md)。
- `scripts/kuaishou_reward_status.py`（上架）：SHA-256 `b727e90b3326ec58b00281be13ad27879cb75be0af9a9c5c0a93fe3fbd8aa305`；含 live 业务证据。详见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/kuku_daily.py`（待检查）：SHA-256 `d16dbbed6f9a6a5ebe6daa4597c46b4e692c7f363beb4a6296bb1e1fceb35fc9`；基础核验通过，业务待检查。详见 [kuku_daily.py.md](docs/scripts/kuku_daily.py.md)。
- `scripts/kurobbs_sign.py`（待检查）：SHA-256 `420de38577b9132e63b09652938838b0a60f03519d374ea9114bc9a01d80bb05`；基础核验通过，业务待检查。详见 [kurobbs_sign.py.md](docs/scripts/kurobbs_sign.py.md)。
- `scripts/l.py`（待检查）：SHA-256 `aba0cf5855af880ab672f6f322417b935718dc8e2e81351ebd65791a1b9809dd`；基础核验通过，业务待检查。详见 [l.py.md](docs/scripts/l.py.md)。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`（待检查）：SHA-256 `1e758c69465f04e6b2561615b1b0a222871c106bbacbb0f0afab42fbb0fa238c`；基础核验通过，业务待检查。详见 [leaflow_checkin_pyleaflow_checkin.py.md](docs/scripts/leaflow_checkin_pyleaflow_checkin.py.md)。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`（待检查）：SHA-256 `b165e0325fb0761f66081e45083b65726d03157099f19fddec58665381ad2c34`；基础核验通过，业务待检查。详见 [littlewuh_qinglongbox_dailycheckin_scripts.py.md](docs/scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md)。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`（待检查）：SHA-256 `d403a1c68ee24f721a320318363bb0a763d815b217fa73801512ecbac8c303ff`；基础核验通过，业务待检查。详见 [lizhixu_ql_script_hub_nodeseek.py.md](docs/scripts/lizhixu_ql_script_hub_nodeseek.py.md)。
- `scripts/lizhixu_ql_script_hub_youdao.py`（待检查）：SHA-256 `6aca37b98181444404cc54f0917b8aab7d6a0995e485aff80918ec32a205e3a6`；基础核验通过，业务待检查。详见 [lizhixu_ql_script_hub_youdao.py.md](docs/scripts/lizhixu_ql_script_hub_youdao.py.md)。
- `scripts/lobsterai_checkin.py`（待检查）：SHA-256 `30863a779860e257ebe6c38bb2b222f97448e0748a912b1c8cea38dc33f4dc18`；基础核验通过，业务待检查。详见 [lobsterai_checkin.py.md](docs/scripts/lobsterai_checkin.py.md)。
- `scripts/loomy_daily.py`（待检查）：SHA-256 `31903376bb554862f5d23f99b67975b4d159ee6de93bb8b280b3fc329d451ce9`；基础核验通过，业务待检查。详见 [loomy_daily.py.md](docs/scripts/loomy_daily.py.md)。
- `scripts/lynkco_qinglong_single.py`（待检查）：SHA-256 `5c07b38c3cc8f306cafb7a9efda1215db8b036c5d4d24c2faeb9985c89490233`；基础核验通过，业务待检查。详见 [lynkco_qinglong_single.py.md](docs/scripts/lynkco_qinglong_single.py.md)。
- `scripts/main.py`（待检查）：SHA-256 `ea3bb416264f093933b3bf07dbc40a5dc02eeb4e8fc02d1626f2db0e4ac1ae17`；基础核验通过，业务待检查。详见 [main.py.md](docs/scripts/main.py.md)。
- `scripts/mifan_optimized.py`（待检查）：SHA-256 `7fbd32635c2c61d2e89c6ef056726314c439ad70655c0295af47364e565f8ffb`；基础核验通过，业务待检查。详见 [mifan_optimized.py.md](docs/scripts/mifan_optimized.py.md)。
- `scripts/mimotion.py`（待检查）：SHA-256 `4e8149eb7fd9f48b6a92c4b22190c633a40d7def1754bb196a3c26bcbf30d7cc`；基础核验通过，业务待检查。详见 [mimotion.py.md](docs/scripts/mimotion.py.md)。
- `scripts/netease_task.py`（待检查）：SHA-256 `a94fc863e187c81a29f6c44ab88c30162bc3d1570ebbe602a70ed4824a198fbe`；基础核验通过，业务待检查。详见 [netease_task.py.md](docs/scripts/netease_task.py.md)。
- `scripts/nga_checkin.py`（待检查）：SHA-256 `147ff1cce75da800dc48ed5dade6222282afff8f7bd6f1bbbdebda74ede5242e`；基础核验通过，业务待检查。详见 [nga_checkin.py.md](docs/scripts/nga_checkin.py.md)。
- `scripts/nodeseek.py`（待检查）：SHA-256 `9e38011e2840ce76dc24111e8c6d6522aeb75b71d8212be4551def23840e5549`；基础核验通过，业务待检查。详见 [nodeseek.py.md](docs/scripts/nodeseek.py.md)。
- `scripts/nodeseek_checkin.py`（待检查）：SHA-256 `bc4d97b59c92bda264dd477193a902490e25641b333bfe8feab8406d233ef505`；基础核验通过，业务待检查。详见 [nodeseek_checkin.py.md](docs/scripts/nodeseek_checkin.py.md)。
- `scripts/nte.py`（待检查）：SHA-256 `44b3e9817214e01d674b189c4b2b38af6bb6fcb0012f2887f471080a78e635b1`；基础核验通过，业务待检查。详见 [nte.py.md](docs/scripts/nte.py.md)。
- `scripts/officeace_daily.py`（待检查）：SHA-256 `24733f11f9b386cbd668978df42e4c7a7140f8ef4480651d0aa73abe3d2ebb22`；基础核验通过，业务待检查。详见 [officeace_daily.py.md](docs/scripts/officeace_daily.py.md)。
- `scripts/ole.py`（待检查）：SHA-256 `5dba4860d34bf701f15f92c59b1cfa4f6cea511c7b24355c2ea839334eea3796`；基础核验通过，业务待检查。详见 [ole.py.md](docs/scripts/ole.py.md)。
- `scripts/passnat_checkin.py`（待检查）：SHA-256 `378ef21771663547b6f58d6d66d4639e79047fee044815af7c84d137b4bf2aaf`；基础核验通过，业务待检查。详见 [passnat_checkin.py.md](docs/scripts/passnat_checkin.py.md)。
- `scripts/psnine.py`（待检查）：SHA-256 `c5eee3d70ff8779f96a50277dac5ceb6076b88c62dea16a15ac2c625078950c4`；基础核验通过，业务待检查。详见 [psnine.py.md](docs/scripts/psnine.py.md)。
- `scripts/pt_sign_v5.js`（待检查）：SHA-256 `00c5772a3b7bacd61255515237ab1bd9f1d9d075d9bbf32d8ce4ec8c123552d2`；基础核验通过，业务待检查。详见 [pt_sign_v5.js.md](docs/scripts/pt_sign_v5.js.md)。
- `scripts/qoder_airscript.js`（待检查）：SHA-256 `e1e74cc7bb351cb9b95995c142025eebec911240c0b7e54d0a9fb62b60e54480`；基础核验通过，业务待检查。详见 [qoder_airscript.js.md](docs/scripts/qoder_airscript.js.md)。
- `scripts/quark_signin.py`（待检查）：SHA-256 `500262df894e109fbe27a2dfafe56d9c395e01d816d6644bc6ff10c46b89d530`；基础核验通过，业务待检查。详见 [quark_signin.py.md](docs/scripts/quark_signin.py.md)。
- `scripts/raccoon_daily.py`（待检查）：SHA-256 `3ebdbfeaf41c75c467fdeb6f2e11889b5a985cacfc3b7203679348087ed36b63`；基础核验通过，业务待检查。详见 [raccoon_daily.py.md](docs/scripts/raccoon_daily.py.md)。
- `scripts/rainyun.py`（待检查）：SHA-256 `15f8b296b4bca186c9376744151cbb06dafa0d3b1a0c79f0ddff119163dc2b4a`；基础核验通过，业务待检查。详见 [rainyun.py.md](docs/scripts/rainyun.py.md)。
- `scripts/rousi_checkin.js`（待检查）：SHA-256 `b20207312e40ff721f057cfe38dbdf6570486e9f4ce1b4d7882f60f85dafb138`；基础核验通过，业务待检查。详见 [rousi_checkin.js.md](docs/scripts/rousi_checkin.js.md)。
- `scripts/sf.py`（待检查）：SHA-256 `5c594804fd2d2a74fe2ad188aa73f95755d5bd28e562d3feceb78cc0fa87fcaf`；基础核验通过，业务待检查。详见 [sf.py.md](docs/scripts/sf.py.md)。
- `scripts/sfsu_checkin.py`（待检查）：SHA-256 `d48a9999e72bbea15c0de43dc537ab4f37f63c5a6fb38708098482f92761affb`；基础核验通过，业务待检查。详见 [sfsu_checkin.py.md](docs/scripts/sfsu_checkin.py.md)。
- `scripts/sgs.py`（待检查）：SHA-256 `af3d44c77a409fccb89cdf36a8282bb311c17463a559c544c114d78b253efce7`；基础核验通过，业务待检查。详见 [sgs.py.md](docs/scripts/sgs.py.md)。
- `scripts/shuyi.py`（待检查）：SHA-256 `947ec405caf0bacdc1f2b823552425d882c3510d733c99c8a1801bf7a739870c`；基础核验通过，业务待检查。详见 [shuyi.py.md](docs/scripts/shuyi.py.md)。
- `scripts/sign_in.py`（待检查）：SHA-256 `d2d3f6610f0aaf4c6866b93fc47751f18a8004bf53c9eae43b560cde380d6cef`；基础核验通过，业务待检查。详见 [sign_in.py.md](docs/scripts/sign_in.py.md)。
- `scripts/skland_daily.py`（待检查）：SHA-256 `23bae97efad62a8e36e4ed2b0d82fe9a2d97450fdba6f089cd23c2d9561580b3`；基础核验通过，业务待检查。详见 [skland_daily.py.md](docs/scripts/skland_daily.py.md)。
- `scripts/skland_demo.py`（待检查）：SHA-256 `6630751a2fdb3b62947ba9dd9b33187db05cbf4dcdd859fe9f60da9e9dda5c2b`；基础核验通过，业务待检查。详见 [skland_demo.py.md](docs/scripts/skland_demo.py.md)。
- `scripts/skyland.py`（待检查）：SHA-256 `4e83f3d0eda94365bdd5fc3648594f678a381cb513c7d065667be9dfbe8874e1`；基础核验通过，业务待检查。详见 [skyland.py.md](docs/scripts/skyland.py.md)。
- `scripts/smzdm_checkin.js`（待检查）：SHA-256 `b01d902608844777102486bab86a7fa18f18c4dfb3166375b7bfacad07e0808b`；基础核验通过，业务待检查。详见 [smzdm_checkin.js.md](docs/scripts/smzdm_checkin.js.md)。
- `scripts/ssl_cert_check.py`（待检查）：SHA-256 `6fc3c3040959c04d815c2ba897050e99994e591f34fbdd4ab6ca2b894ed54766`；基础核验通过，业务待检查。详见 [ssl_cert_check.py.md](docs/scripts/ssl_cert_check.py.md)。
- `scripts/sudojia_33agilestudio.js`（待检查）：SHA-256 `7677c43b5720b0556f6d0b2949405b7c91d218dbc5d020ad6be0dd46ce2308d8`；基础核验通过，业务待检查。详见 [sudojia_33agilestudio.js.md](docs/scripts/sudojia_33agilestudio.js.md)。
- `scripts/sudojia_allgirls.js`（待检查）：SHA-256 `c553619d6534fdf01df62c381df54bfb5557104402a27aa037bf381b075d8934`；基础核验通过，业务待检查。详见 [sudojia_allgirls.js.md](docs/scripts/sudojia_allgirls.js.md)。
- `scripts/sudojia_amx.js`（待检查）：SHA-256 `74c9e4adc427ad5b11fa3790b55857eb5a928af78cabc6c0d7c7d04ee8694c65`；基础核验通过，业务待检查。详见 [sudojia_amx.js.md](docs/scripts/sudojia_amx.js.md)。
- `scripts/sudojia_authcheck.js`（待检查）：SHA-256 `cb0ac42844920cb1be7a54b04e2781ad0f330cda89176379e2f8353a87119a0c`；基础核验通过，业务待检查。详见 [sudojia_authcheck.js.md](docs/scripts/sudojia_authcheck.js.md)。
- `scripts/sudojia_bananavideo.js`（待检查）：SHA-256 `0406e66e2c06dd0ff5f9b74c79cd2bba0f41b104b417a0c40f08830bf023dbb0`；基础核验通过，业务待检查。详见 [sudojia_bananavideo.js.md](docs/scripts/sudojia_bananavideo.js.md)。
- `scripts/sudojia_beiyinmei.js`（待检查）：SHA-256 `7829fb15cfeb7cd36abbc90c383ca2774ac04804b3c03f77e2957b87ed3b0195`；基础核验通过，业务待检查。详见 [sudojia_beiyinmei.js.md](docs/scripts/sudojia_beiyinmei.js.md)。
- `scripts/sudojia_botanystar.js`（待检查）：SHA-256 `49514a5ef472c0344b18fd9a97ece749a06dbb354e83ec3972b74fcd8293fbd2`；基础核验通过，业务待检查。详见 [sudojia_botanystar.js.md](docs/scripts/sudojia_botanystar.js.md)。
- `scripts/sudojia_bwtea.js`（待检查）：SHA-256 `6c7a37e9d10e71acbf0f22997db91262260bfb5b30c0da79c90b0b1c0fe7baec`；基础核验通过，业务待检查。详见 [sudojia_bwtea.js.md](docs/scripts/sudojia_bwtea.js.md)。
- `scripts/sudojia_colorful_mall.js`（待检查）：SHA-256 `d8d73f9403e695405a0ed89a282f242158c47aadb97f8576d4049bb94a1146e9`；基础核验通过，业务待检查。详见 [sudojia_colorful_mall.js.md](docs/scripts/sudojia_colorful_mall.js.md)。
- `scripts/sudojia_flyant.js`（待检查）：SHA-256 `8e3e229e4db887c4588444e53211ef4610a82cae51cb463409a4bb06cb831c03`；基础核验通过，业务待检查。详见 [sudojia_flyant.js.md](docs/scripts/sudojia_flyant.js.md)。
- `scripts/sudojia_fnnas.js`（待检查）：SHA-256 `4106209f1efdb73b3c49564c0ea186123ee5c04bc81f209dcd0ac561c6b6d21d`；基础核验通过，业务待检查。详见 [sudojia_fnnas.js.md](docs/scripts/sudojia_fnnas.js.md)。
- `scripts/sudojia_hgf.js`（待检查）：SHA-256 `7a2fc3f49f3bb53dd24a27db4453415048f8b5db6640c7a3adbc1bf3c2b406b8`；基础核验通过，业务待检查。详见 [sudojia_hgf.js.md](docs/scripts/sudojia_hgf.js.md)。
- `scripts/sudojia_hlzj_game.js`（待检查）：SHA-256 `cb6afdaa59ce18500e46bb208ba48c468eca19656abb8b12cd79db5a501bbbb8`；基础核验通过，业务待检查。详见 [sudojia_hlzj_game.js.md](docs/scripts/sudojia_hlzj_game.js.md)。
- `scripts/sudojia_hzhfp.js`（待检查）：SHA-256 `3ed150270405b542635e468b2ab1eaf8902dcc9fa41fb6a46b4cef62002a6cab`；基础核验通过，业务待检查。详见 [sudojia_hzhfp.js.md](docs/scripts/sudojia_hzhfp.js.md)。
- `scripts/sudojia_instax.js`（待检查）：SHA-256 `815b3148db43b02667a8b792285e4846925af30866e78ff5a1fec5804c29e377`；基础核验通过，业务待检查。详见 [sudojia_instax.js.md](docs/scripts/sudojia_instax.js.md)。
- `scripts/sudojia_jhcard.js`（待检查）：SHA-256 `ac86d6cc9fda1657bb61169b9feecbb9cadba6a61b95a92bec66912155d2eff6`；基础核验通过，业务待检查。详见 [sudojia_jhcard.js.md](docs/scripts/sudojia_jhcard.js.md)。
- `scripts/sudojia_jiangshan.js`（待检查）：SHA-256 `6aeecd07cf2173fa8e1a7775bd17849dd373ce9ca102ba5d5e5e48b9af78f04d`；基础核验通过，业务待检查。详见 [sudojia_jiangshan.js.md](docs/scripts/sudojia_jiangshan.js.md)。
- `scripts/sudojia_jindian.js`（待检查）：SHA-256 `d9c3bef3a86ccd7da990e856f7567029c688349b162cb554fd9b8407bd515f22`；基础核验通过，业务待检查。详见 [sudojia_jindian.js.md](docs/scripts/sudojia_jindian.js.md)。
- `scripts/sudojia_jlc_yj.js`（待检查）：SHA-256 `1f7a49e30dd7a0e4da2a1298bd24b1ca0578cf86e10fec9406d001aa872cb493`；基础核验通过，业务待检查。详见 [sudojia_jlc_yj.js.md](docs/scripts/sudojia_jlc_yj.js.md)。
- `scripts/sudojia_juejin.js`（待检查）：SHA-256 `6d8be6058694325cf547c831c4d33f9ce732a7d681ff94b96f42d26056f3406f`；基础核验通过，业务待检查。详见 [sudojia_juejin.js.md](docs/scripts/sudojia_juejin.js.md)。
- `scripts/sudojia_kozbs.js`（待检查）：SHA-256 `a9390adda3bb8938f8d40627ede49a6106dba6267805d7c285f6024e36ef6f58`；基础核验通过，业务待检查。详见 [sudojia_kozbs.js.md](docs/scripts/sudojia_kozbs.js.md)。
- `scripts/sudojia_ktgzs.js`（待检查）：SHA-256 `180d6b848c37e9703d05e65962b1eaf2200052389c048b88f739381b7270346e`；基础核验通过，业务待检查。详见 [sudojia_ktgzs.js.md](docs/scripts/sudojia_ktgzs.js.md)。
- `scripts/sudojia_kukahome.js`（待检查）：SHA-256 `e7081807d92d65a4516d0d1c2c6359451127abbed1f4fffbba0f5e1d645075da`；基础核验通过，业务待检查。详见 [sudojia_kukahome.js.md](docs/scripts/sudojia_kukahome.js.md)。
- `scripts/sudojia_kuro.js`（待检查）：SHA-256 `be7c42c79d74c6f7586588a793084df541257e17fb784f8be817afd5bd95765d`；基础核验通过，业务待检查。详见 [sudojia_kuro.js.md](docs/scripts/sudojia_kuro.js.md)。
- `scripts/sudojia_laoban.js`（待检查）：SHA-256 `39e4e4100e0b82ac9c308d03855d22caaaf0efe0377d7f0ecf4e7d83f899d351`；基础核验通过，业务待检查。详见 [sudojia_laoban.js.md](docs/scripts/sudojia_laoban.js.md)。
- `scripts/sudojia_longfor.js`（待检查）：SHA-256 `33edfe8a54af9a0b7612b5700a2a2a6bf83e80a556481bc021369adaf0c5f3ad`；基础核验通过，业务待检查。详见 [sudojia_longfor.js.md](docs/scripts/sudojia_longfor.js.md)。
- `scripts/sudojia_mallcoo.js`（待检查）：SHA-256 `b5821afa069beb30c1be78bf64dd693a82ee253b2e55105d44d42dd6becdcc30`；基础核验通过，业务待检查。详见 [sudojia_mallcoo.js.md](docs/scripts/sudojia_mallcoo.js.md)。
- `scripts/sudojia_mawuwang.js`（待检查）：SHA-256 `133423898018d04a1784a7cf197c143785cdb359002ed09b826684e793f18b80`；基础核验通过，业务待检查。详见 [sudojia_mawuwang.js.md](docs/scripts/sudojia_mawuwang.js.md)。
- `scripts/sudojia_midea.js`（待检查）：SHA-256 `c474e087bd04b25b5b67faa27c649aec711da38b906cf7f8a969210e2c9061b4`；基础核验通过，业务待检查。详见 [sudojia_midea.js.md](docs/scripts/sudojia_midea.js.md)。
- `scripts/sudojia_moto.js`（已检查）：SHA-256 `1c73ab0fa75d3ca74dd40f04891ec43fa7d8853eb3866b6dd43cd0939e183363`；基础核验通过，业务待检查。详见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。
- `scripts/sudojia_mxbc.js`（待检查）：SHA-256 `9c2a5be7246f6fbf3ed44f52e358102e649f410f5b4219df8b61075b9e0e7612`；基础核验通过，业务待检查。详见 [sudojia_mxbc.js.md](docs/scripts/sudojia_mxbc.js.md)。
- `scripts/sudojia_naixue.js`（待检查）：SHA-256 `754c1557511faa7d5ae360b58a2f7e079ff87e68a92fea15e89e5458bfa43756`；基础核验通过，业务待检查。详见 [sudojia_naixue.js.md](docs/scripts/sudojia_naixue.js.md)。
- `scripts/sudojia_nestle.js`（待检查）：SHA-256 `98ba9fa7508d12ac34f2f91c89c20a3354659412c206df72cb7378f373e83e5d`；基础核验通过，业务待检查。详见 [sudojia_nestle.js.md](docs/scripts/sudojia_nestle.js.md)。
- `scripts/sudojia_nfhk.js`（待检查）：SHA-256 `267c19e71999efaddbbd94c7293565b4e37f91f8deac237b6f88fdd20f321e8f`；基础核验通过，业务待检查。详见 [sudojia_nfhk.js.md](docs/scripts/sudojia_nfhk.js.md)。
- `scripts/sudojia_opposhop.js`（待检查）：SHA-256 `a26cac12229f3c18c37e5557b0ea130b8025ea86c967b5dd8460c91b89cc663d`；基础核验通过，业务待检查。详见 [sudojia_opposhop.js.md](docs/scripts/sudojia_opposhop.js.md)。
- `scripts/sudojia_pangge.js`（待检查）：SHA-256 `4a89dd87925b538c497735bc2a2a45c84b10d5f1658a177922d28738873a63a0`；基础核验通过，业务待检查。详见 [sudojia_pangge.js.md](docs/scripts/sudojia_pangge.js.md)。
- `scripts/sudojia_paotea.js`（待检查）：SHA-256 `9a497af082be58ef72bfa201bc722141d50a9f81c1e8722776a2b010e9f5be19`；基础核验通过，业务待检查。详见 [sudojia_paotea.js.md](docs/scripts/sudojia_paotea.js.md)。
- `scripts/sudojia_shmedia.js`（待检查）：SHA-256 `0bdd067ab5f7eb66e62fce27037da779ed6f050e9c81cb20dae010a4f8a4bbd1`；基础核验通过，业务待检查。详见 [sudojia_shmedia.js.md](docs/scripts/sudojia_shmedia.js.md)。
- `scripts/sudojia_shuifei.js`（待检查）：SHA-256 `dd28f0ff5164c33d9b3db09d1214c9c46ee429180edf34dfd7f2fdeb70c9397a`；基础核验通过，业务待检查。详见 [sudojia_shuifei.js.md](docs/scripts/sudojia_shuifei.js.md)。
- `scripts/sudojia_sspanel.js`（待检查）：SHA-256 `1055ccec4def07a28137aee50d995f6650d6918197b0d9ff7be7508ed5281ca2`；基础核验通过，业务待检查。详见 [sudojia_sspanel.js.md](docs/scripts/sudojia_sspanel.js.md)。
- `scripts/sudojia_starmom.js`（待检查）：SHA-256 `bc2b70cfb62513c69d904e375dce06bbc55b7592b9131cea78a2a1e894bc1b29`；基础核验通过，业务待检查。详见 [sudojia_starmom.js.md](docs/scripts/sudojia_starmom.js.md)。
- `scripts/sudojia_tebu.js`（待检查）：SHA-256 `25c0e6a616e7945d13727f2326b14a059c89cece3405730c8999a16480024428`；基础核验通过，业务待检查。详见 [sudojia_tebu.js.md](docs/scripts/sudojia_tebu.js.md)。
- `scripts/sudojia_tilta.js`（待检查）：SHA-256 `ca9c192577ffee68ddc1083e55704065dac8f6f756f2d3af1f4fc99e03565d22`；基础核验通过，业务待检查。详见 [sudojia_tilta.js.md](docs/scripts/sudojia_tilta.js.md)。
- `scripts/sudojia_tuchong.js`（待检查）：SHA-256 `cdc3e24cb80e5424179994733a38c773a31e05e91eb357a0d54e1fd47d32e270`；基础核验通过，业务待检查。详见 [sudojia_tuchong.js.md](docs/scripts/sudojia_tuchong.js.md)。
- `scripts/sudojia_v2ex.js`（待检查）：SHA-256 `a1f67a331ea725190a2791e37240a488b7be8db2f0f64bb1b436162fa8c45080`；基础核验通过，业务待检查。详见 [sudojia_v2ex.js.md](docs/scripts/sudojia_v2ex.js.md)。
- `scripts/sudojia_wnna.js`（待检查）：SHA-256 `776fd6f05d881afb02e5c070096ab8909a638f944e548065d702ae7e1bb2dd72`；基础核验通过，业务待检查。详见 [sudojia_wnna.js.md](docs/scripts/sudojia_wnna.js.md)。
- `scripts/sudojia_xhn.js`（待检查）：SHA-256 `b0131f2d77c0d1f5ae6271d2a7604798ee3313db307e23390343d2d5e316abbd`；基础核验通过，业务待检查。详见 [sudojia_xhn.js.md](docs/scripts/sudojia_xhn.js.md)。
- `scripts/sudojia_xiangwan.js`（待检查）：SHA-256 `692566ebd5403b42b7671029cf12e1d993ebc6199d8ae704fd3bc489b9069ed7`；基础核验通过，业务待检查。详见 [sudojia_xiangwan.js.md](docs/scripts/sudojia_xiangwan.js.md)。
- `scripts/sudojia_xiaomi_community.js`（待检查）：SHA-256 `2426f49711019ec8e7fe8dc664362df99aa478c1828bd5d5f48c331dbb2a88dd`；基础核验通过，业务待检查。详见 [sudojia_xiaomi_community.js.md](docs/scripts/sudojia_xiaomi_community.js.md)。
- `scripts/sudojia_xinxi.js`（待检查）：SHA-256 `fcdb27ec00935e010ddc68dcaae974b36d3d5effd2de4cf408cd1971f28d6a3d`；基础核验通过，业务待检查。详见 [sudojia_xinxi.js.md](docs/scripts/sudojia_xinxi.js.md)。
- `scripts/sudojia_xpfarm.js`（待检查）：SHA-256 `ffa9878cc55005e28061ca97009b8ffa7c48ce01144b325d0354d499c28a897d`；基础核验通过，业务待检查。详见 [sudojia_xpfarm.js.md](docs/scripts/sudojia_xpfarm.js.md)。
- `scripts/sudojia_znds.js`（待检查）：SHA-256 `e642ddf42719ca2ac4e37a94856f3c35e08307bc0b47d993bd5a1a83eb13eba1`；基础核验通过，业务待检查。详见 [sudojia_znds.js.md](docs/scripts/sudojia_znds.js.md)。
- `scripts/sudojia_zxice.js`（待检查）：SHA-256 `eb50f784e85263452ae010edf81d6b0e1d6c864532f2c6f1a170aa168ddc8c5d`；基础核验通过，业务待检查。详见 [sudojia_zxice.js.md](docs/scripts/sudojia_zxice.js.md)。
- `scripts/supertopicsign.py`（待检查）：SHA-256 `7ec766c350e8734acddc724e720a0073d8838430e1885a9e699e13d907fbacb4`；基础核验通过，业务待检查。详见 [supertopicsign.py.md](docs/scripts/supertopicsign.py.md)。
- `scripts/synspoint.py`（待检查）：SHA-256 `f343af6c80ac9ca40e51f0fb72a81d41acb2af51233623d6fa2f1fca4e636f7f`；基础核验通过，业务待检查。详见 [synspoint.py.md](docs/scripts/synspoint.py.md)。
- `scripts/task_ef2d3863.js`（待检查）：SHA-256 `8586de43a2f596862d6cb8d81ed151c476292dca5f800bcc20985219e3d892a4`；基础核验通过，业务待检查。详见 [task_ef2d3863.js.md](docs/scripts/task_ef2d3863.js.md)。
- `scripts/tencent_video_checkin.py`（待检查）：SHA-256 `22ae305cd2e4196c0574785ab58f4dc0fb54266676ba599ea71971c4dc973ec6`；基础核验通过，业务待检查。详见 [tencent_video_checkin.py.md](docs/scripts/tencent_video_checkin.py.md)。
- `scripts/tieba_checkin.py`（上架）：SHA-256 `2db577380e0d0f1f5cf940b40cceca8bfcd21e2d140e284552f9cc943f4a7d4e`；基础核验通过，业务待检查。详见 [tieba_checkin.py.md](docs/scripts/tieba_checkin.py.md)。
- `scripts/tjd_daily.py`（待检查）：SHA-256 `95bb1d686b6e91e37c588601be134a99e9715c943ea99b63f6fda75fd0d51943`；基础核验通过，业务待检查。详见 [tjd_daily.py.md](docs/scripts/tjd_daily.py.md)。
- `scripts/trae_checkin.py`（待检查）：SHA-256 `45962500ef7a2bad52fda864d421f76bf3639e6ee0fb6dee695b394eb34199b8`；基础核验通过，业务待检查。详见 [trae_checkin.py.md](docs/scripts/trae_checkin.py.md)。
- `scripts/tsthb_checkin.py`（待检查）：SHA-256 `f1f423f22e8134fb3080600f07293746eeb4d05783ec1778f489174dc1166d4c`；含 live 业务证据。详见 [tsthb_checkin.py.md](docs/scripts/tsthb_checkin.py.md)。
- `scripts/ty_netdisk_checkin.py`（待检查）：SHA-256 `096668383bde7522670dd87830f0e8b48ed4ce3e142e723c6fe6ebce238f99f2`；基础核验通过，业务待检查。详见 [ty_netdisk_checkin.py.md](docs/scripts/ty_netdisk_checkin.py.md)。
- `scripts/tyqhdraw.py`（待检查）：SHA-256 `c2c1115b60fd085034eb55d28ffb8fd3cb6476263eeff23f53f5bea8ad892b7e`；基础核验通过，业务待检查。详见 [tyqhdraw.py.md](docs/scripts/tyqhdraw.py.md)。
- `scripts/valorantstore.py`（待检查）：SHA-256 `e7b189720b1086ca20bad310b392de69d4f75c7fa0660ed843120affa4bcc0fb`；基础核验通过，业务待检查。详见 [valorantstore.py.md](docs/scripts/valorantstore.py.md)。
- `scripts/vortexa_free_claim.js`（待检查）：SHA-256 `4a9d6c8d8e147991d196f0ddebf7c74f200c9e12ab1fca721555034e46e2da04`；基础核验通过，业务待检查。详见 [vortexa_free_claim.js.md](docs/scripts/vortexa_free_claim.js.md)。
- `scripts/wangchao.py`（待检查）：SHA-256 `487368c93ce9621b956e4df0aba44badaf3094070a94d3a6a61c384742915067`；基础核验通过，业务待检查。详见 [wangchao.py.md](docs/scripts/wangchao.py.md)。
- `scripts/wentiweilaihui.py`（待检查）：SHA-256 `f91a3a6a1873b350c695cc5466ff224a18d90d01e59e013c5a319dfc55facc24`；基础核验通过，业务待检查。详见 [wentiweilaihui.py.md](docs/scripts/wentiweilaihui.py.md)。
- `scripts/workbuddy.py`（待检查）：SHA-256 `c20f62f74b4c3a50a42852229dff9b40dc79baa5f6854e8d40e01a4f361c5a7a`；基础核验通过，业务待检查。详见 [workbuddy.py.md](docs/scripts/workbuddy.py.md)。
- `scripts/workbuddy_daily.py`（待检查）：SHA-256 `af37790e41e116c92ebe1ecb8a001b4fc030d65a9785e161dc1bc926e23be14a`；基础核验通过，业务待检查。详见 [workbuddy_daily.py.md](docs/scripts/workbuddy_daily.py.md)。
- `scripts/wps_clock_in.py`（待检查）：SHA-256 `bc653d3a575e4993de249bd00b7f3107a8ca17f8da320903f086372b1df9a827`；基础核验通过，业务待检查。详见 [wps_clock_in.py.md](docs/scripts/wps_clock_in.py.md)。
- `scripts/wyycg.py`（待检查）：SHA-256 `1da9e1203d9de2f68ac046c6271f1a425858ea39e54914d0bdb3e143b5df9975`；基础核验通过，业务待检查。详见 [wyycg.py.md](docs/scripts/wyycg.py.md)。
- `scripts/yht.py`（待检查）：SHA-256 `041f5e6059185deb57a956d7c3d4f62db0b4f9e6438d6884ea9b561a04a7ad9d`；基础核验通过，业务待检查。详见 [yht.py.md](docs/scripts/yht.py.md)。
- `scripts/youdao.py`（待检查）：SHA-256 `0c740bfa5e0616e362c80e44bb42aedacc6cf7785d7a0665f4f9be29f4ddb799`；基础核验通过，业务待检查。详见 [youdao.py.md](docs/scripts/youdao.py.md)。
- `scripts/yyshuijuantime.py`（待检查）：SHA-256 `ed7e4a6e165c239056135e84d3f2a0825a5fcfded2a1f0961d11b37172069cf6`；基础核验通过，业务待检查。详见 [yyshuijuantime.py.md](docs/scripts/yyshuijuantime.py.md)。
- `scripts/zcode_cn_daily.py`（待检查）：SHA-256 `7085cd0c4eeef4e5c9bc6f38f03e752e4e253b341c6fdb25334537e6ceceb8e5`；基础核验通过，业务待检查。详见 [zcode_cn_daily.py.md](docs/scripts/zcode_cn_daily.py.md)。
- `scripts/zippo.py`（待检查）：SHA-256 `db87391467bd1a78afea9e1725cf8a5a06a4f78373821128a20dcb98ed03b338`；基础核验通过，业务待检查。详见 [zippo.py.md](docs/scripts/zippo.py.md)。
- `scripts/zodgame_test.py`（待检查）：SHA-256 `1e51c1301d3f6930103407ee55631084359d11244ffb4b40e9bc149eb0fb3ef9`；基础核验通过，业务待检查。详见 [zodgame_test.py.md](docs/scripts/zodgame_test.py.md)。

发布清单中的验证只对应所列哈希；脚本、依赖或接口逻辑变化后必须重新进行 live 业务验证。`待检查` 不代表业务失败，只表示维护者尚未完成当前版本人工核验。

## 副作用与风险

- `scripts/139_yunduo.py`：执行每日签到并领取AI豆；点击互动、问卷及其他已选择任务，可能改变任务进度或领取AI豆。完整说明见 [139_yunduo.py.md](docs/scripts/139_yunduo.py.md)。
- `scripts/2cycdx.py`：正式运行提交论坛签到及签到文案，领取对应贡献奖励。；正式运行且开启通知时发送脱敏任务通知。。完整说明见 [2cycdx.py.md](docs/scripts/2cycdx.py.md)。
- `scripts/51cto_sign.js`：登录建立服务端会话；每日签到及平台对应的签到奖励。完整说明见 [51cto_sign.js.md](docs/scripts/51cto_sign.js.md)。
- `scripts/52pojie.js`：正式执行申请论坛每日签到任务，可能增加签到奖励。；通知启用且通道可用时发送脱敏总结，配置 Bark 时发送可选推送。。完整说明见 [52pojie.js.md](docs/scripts/52pojie.js.md)。
- `scripts/999.py`：正式执行提交答题选项，可能按活动规则产生积分奖励；正式执行在通知开启且模块可用时外发脱敏任务摘要。完整说明见 [999.py.md](docs/scripts/999.py.md)。
- `scripts/acfun.py`：默认执行每日签到，更新签到状态；选择 like 时新增点赞；选择 like-cycle 时新增点赞后取消。完整说明见 [acfun.py.md](docs/scripts/acfun.py.md)。
- `scripts/agentrouter.py`：重新登录 AgentRouter，创建登录会话并可能发放当日签到额度。；仅显式启用 AGENTROUTER_ALLOW_AUTHORIZE 后可提交 GitHub 首次应用授权。。完整说明见 [agentrouter.py.md](docs/scripts/agentrouter.py.md)。
- `scripts/airport.py`：正式模式通过登录建立网站会话。；正式模式执行每日签到，可能增加网站赠送流量或签到记录。。完整说明见 [airport.py.md](docs/scripts/airport.py.md)。
- `scripts/akile_checkin.py`：未完成今日签到时提交一次 AK 币签到。；实际执行保存本地连续签到及累计收益统计；只读和预演不写入。。完整说明见 [akile_checkin.py.md](docs/scripts/akile_checkin.py.md)。
- `scripts/aliyun_web.js`：社区签到及领取签到奖励；显式开启后增加文章点赞、收藏、分享事件和回答点赞记录，不自动取消已有操作。完整说明见 [aliyun_web.js.md](docs/scripts/aliyun_web.js.md)。
- `scripts/aliyundrive_checkin.js`：刷新账号访问令牌；执行每日签到。完整说明见 [aliyundrive_checkin.js.md](docs/scripts/aliyundrive_checkin.js.md)。
- `scripts/aliyunpan_checkin.py`：执行账号每日签到；默认领取当日奖励，显式全量模式下补领其他已签到未领奖励。完整说明见 [aliyunpan_checkin.py.md](docs/scripts/aliyunpan_checkin.py.md)。
- `scripts/aolaxing.py`：配置 AOLAXING_TASK_IDS 时触发对应每日任务完成及服务端关联积分或签到状态变更，具体效果以用户审阅的任务为准。；在线运行且通知开启时发送青龙任务汇总通知。。完整说明见 [aolaxing.py.md](docs/scripts/aolaxing.py.md)。
- `scripts/api_hax.py`：正式模式且启用通知时，通过青龙通知渠道发送查询结果和统计。。完整说明见 [api_hax.py.md](docs/scripts/api_hax.py.md)。
- `scripts/arknightsbanner.py`：正式运行在用户明确指定的位置创建或原子更新公告去重状态文件。；启用通知时向青龙配置的通知渠道发送卡池公告与运行总结；配置图片接收目标且公告有封面时向 Telegram 发送图片。。完整说明见 [arknightsbanner.py.md](docs/scripts/arknightsbanner.py.md)。
- `scripts/atxyq.py`：默认每日签到，记录签到并可能增加积分。；默认领取普通任务奖励，可能增加积分。。完整说明见 [atxyq.py.md](docs/scripts/atxyq.py.md)。
- `scripts/auto_buy.py`：显式开启商城后提交抢购请求，可能兑换商品、扣除积分或产生付费订单；明确拒绝时可能重复提交；显式开启积分后增加阅读计数并提交阅读、视频或分享积分请求，可能增加积分及改变任务进度。完整说明见 [auto_buy.py.md](docs/scripts/auto_buy.py.md)。
- `scripts/autoclaw_cn_daily.py`：真实运行提交所选地区 daily_signin 签到任务，可能获得积分；登录态过期或 --refresh-only 时续期登录态，可能使旧登录态失效。完整说明见 [autoclaw_cn_daily.py.md](docs/scripts/autoclaw_cn_daily.py.md)。
- `scripts/autosignin.js`：正式运行刷新阿里云盘会话令牌，新凭据仅在内存使用。；正式运行执行每日签到。。完整说明见 [autosignin.js.md](docs/scripts/autosignin.js.md)。
- `scripts/autosignin.py`：正式访问新闻页可能领取每日签到奖励及触发服务端随机遭遇事件；正式运行在通知启用且模块可用时发送脱敏通知。完整说明见 [autosignin.py.md](docs/scripts/autosignin.py.md)。
- `scripts/baidu.py`：实际运行向百度提交本站 URL 并消耗提交配额；显式 times 大于 1 时重复提交同一清单；实际运行在通知开启且通知模块可用时发送脱敏任务通知。完整说明见 [baidu.py.md](docs/scripts/baidu.py.md)。
- `scripts/baiduwangpan_checkin.py`：为每个已配置的百度网盘账号执行每日会员签到；为每个已配置的百度网盘账号提交每日会员问题答案。完整说明见 [baiduwangpan_checkin.py.md](docs/scripts/baiduwangpan_checkin.py.md)。
- `scripts/baiduwp.py`：执行会员签到，增加会员成长值；提交每日题目答案，可能增加会员成长值。完整说明见 [baiduwp.py.md](docs/scripts/baiduwp.py.md)。
- `scripts/bilibili.py`：漫画签到改变签到记录；观看进度上报改变观看历史与任务记录。完整说明见 [bilibili.py.md](docs/scripts/bilibili.py.md)。
- `scripts/bsly_draw.py`：显式开启实跑后消耗抽奖机会并可能获得奖品。；实跑启用通知且桥接可用时向青龙配置的通知渠道发送脱敏总结。。完整说明见 [bsly_draw.py.md](docs/scripts/bsly_draw.py.md)。
- `scripts/bugutv.py`：登录并建立账户会话，沿用上游rememberme登录参数；每日签到并领取服务端实际发放的积分奖励。完整说明见 [bugutv.py.md](docs/scripts/bugutv.py.md)。
- `scripts/bwcj.py`：新版签到产生签到记录及服务端发放的积分或奖励。；显式开启旧版签到后产生旧版签到记录及服务端奖励。。完整说明见 [bwcj.py.md](docs/scripts/bwcj.py.md)。
- `scripts/caigamer.js`：正式运行提交签到并领取站点签到奖励；正式运行在通知启用且通知模块可用时发送脱敏任务统计。完整说明见 [caigamer.js.md](docs/scripts/caigamer.js.md)。
- `scripts/cdrail.py`：调用签到接口，完成每日签到并可能增加积分；正式模式通过青龙通知模块发送脱敏结果摘要。完整说明见 [cdrail.py.md](docs/scripts/cdrail.py.md)。
- `scripts/cfmoto_checkin.py`：改变账号的当日签到和积分状态；最多发布三个公开帖子并留下可见内容。完整说明见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/cg163_autocheckin.py`：每日签到可能增加账号签到天数及奖励；向青龙通知渠道发送脱敏任务摘要。完整说明见 [cg163_autocheckin.py.md](docs/scripts/cg163_autocheckin.py.md)。
- `scripts/chevrolet.js`：实际运行向雪佛兰签到接口提交签到，可能改变签到状态并获得服务端签到奖励。；通知启用且本地青龙通知器可用时，实际运行发送脱敏任务总结。。完整说明见 [chevrolet.js.md](docs/scripts/chevrolet.js.md)。
- `scripts/ck_2nzz.py`：正式运行向咔叽网单提交每日签到，可能获得站点签到奖励。；正式运行且通知开启时通过青龙配置的通知渠道发送脱敏任务摘要。。完整说明见 [ck_2nzz.py.md](docs/scripts/ck_2nzz.py.md)。
- `scripts/ck_acfun.py`：默认执行每日签到，可能获得签到奖励。；启用 like 时先点赞再取消；取消失败时可能保留点赞状态。。完整说明见 [ck_acfun.py.md](docs/scripts/ck_acfun.py.md)。
- `scripts/ck_airport.py`：向机场发起每日签到，可能领取流量等奖励。；登录时创建服务器账号会话。。完整说明见 [ck_airport.py.md](docs/scripts/ck_airport.py.md)。
- `scripts/ck_aqc.js`：签到并记录登录或查询浏览任务进度；领取任务奖励并增加爱豆积分。完整说明见 [ck_aqc.js.md](docs/scripts/ck_aqc.js.md)。
- `scripts/ck_baidu_url_submit.py`：实际运行向百度提交本站 URL 并消耗每日配额，显式设置 times 大于 1 时重复提交同一列表；实际运行且通知开启时通过青龙通知模块发送脱敏总结。完整说明见 [ck_baidu_url_submit.py.md](docs/scripts/ck_baidu_url_submit.py.md)。
- `scripts/ck_bilibili.py`：漫画签到改变签到记录并可能发放奖励；直播签到改变签到记录并可能发放奖励。完整说明见 [ck_bilibili.py.md](docs/scripts/ck_bilibili.py.md)。
- `scripts/ck_ccava.py`：实际模式调用 CCAVA 每日签到接口，可能增加账号月光币；实际模式通知开启且工具可用时发送脱敏任务结果通知。完整说明见 [ck_ccava.py.md](docs/scripts/ck_ccava.py.md)。
- `scripts/ck_csdn.py`：签到改变当天签到状态并可能领取奖励；显式开启抽奖后消耗抽奖机会并可能领取奖品。完整说明见 [ck_csdn.py.md](docs/scripts/ck_csdn.py.md)。
- `scripts/ck_du163.js`：真实模式向官方提交每日签到，可能增加连续签到天数和官方签到奖励；通知启用且青龙通知可用时发送任务汇总。完整说明见 [ck_du163.js.md](docs/scripts/ck_du163.js.md)。
- `scripts/ck_duokan.py`：每日签到改变签到状态并可能获得书豆。；开启 DUOKAN_FREE 时领取图书并改变书架或购买记录。。完整说明见 [ck_duokan.py.md](docs/scripts/ck_duokan.py.md)。
- `scripts/ck_everphoto.py`：正式执行登录请求创建认证会话；正式执行每日签到改变签到状态。完整说明见 [ck_everphoto.py.md](docs/scripts/ck_everphoto.py.md)。
- `scripts/ck_fmapp.py`：向 Fa米家提交每日签到，按服务端规则更新签到记录并发放发米粒。完整说明见 [ck_fmapp.py.md](docs/scripts/ck_fmapp.py.md)。
- `scripts/ck_freenom.py`：登录建立服务端账号会话；显式启用且表单证明免费时提交域名 12 个月续期。完整说明见 [ck_freenom.py.md](docs/scripts/ck_freenom.py.md)。
- `scripts/ck_game163.py`：实际模式向网易云游戏提交每日签到，可能获得服务端签到奖励。；通知开启且实际模式下，通过青龙通知模块发送脱敏任务总结。。完整说明见 [ck_game163.py.md](docs/scripts/ck_game163.py.md)。
- `scripts/ck_meizu.py`：签到改变社区签到状态并可能获得奖励。；显式开启抽奖后消耗活动次数或积分，并可能获得奖励。。完整说明见 [ck_meizu.py.md](docs/scripts/ck_meizu.py.md)。
- `scripts/ck_mgtv.py`：正式执行向芒果TV提交签到，更新签到记录并领取积分；启用通知时发送脱敏任务结果通知。完整说明见 [ck_mgtv.py.md](docs/scripts/ck_mgtv.py.md)。
- `scripts/ck_mimotion.py`：显式 upload 同步本人提供的当天健康记录并修改当天步数总量；模板中的活动、心率和睡眠等数据也一同上传。。完整说明见 [ck_mimotion.py.md](docs/scripts/ck_mimotion.py.md)。
- `scripts/ck_oneplusbbs.py`：提交每日签到及公开签到文字；显式开启抽奖后每次消耗 10 加油并可能获得奖励。完整说明见 [ck_oneplusbbs.py.md](docs/scripts/ck_oneplusbbs.py.md)。
- `scripts/codearts_daily.py`：领取福利积分与新人奖励；确认福利到账。完整说明见 [codearts_daily.py.md](docs/scripts/codearts_daily.py.md)。
- `scripts/comicai_ai_cookie.py`：向 ComicAI 提交每日签到并可能获得积分；启用通知时发送脱敏任务总结。完整说明见 [comicai_ai_cookie.py.md](docs/scripts/comicai_ai_cookie.py.md)。
- `scripts/crealitycloud_checkin.py`：登录与 OAuth 授权生成服务端会话；每日签到改变签到记录并领取奖励。完整说明见 [crealitycloud_checkin.py.md](docs/scripts/crealitycloud_checkin.py.md)。
- `scripts/dachao.py`：签到改变签到记录及活动积分；完成阅读任务并上报阅读时长。完整说明见 [dachao.py.md](docs/scripts/dachao.py.md)。
- `scripts/dahai.js`：正式运行提交每日签到，可能增加积分、经验及连续签到天数；正式运行启用通知时发送青龙任务总结。完整说明见 [dahai.js.md](docs/scripts/dahai.js.md)。
- `scripts/daily_benefits.py`：默认执行免费会员签到，符合条件时领取七日奖励；显式开启会员试用时提交申请并消耗申请机会。完整说明见 [daily_benefits.py.md](docs/scripts/daily_benefits.py.md)。
- `scripts/dailynewscn.js`：正式运行且通知启用时，向青龙已配置渠道发送所选公开内容及脱敏总结。。完整说明见 [dailynewscn.js.md](docs/scripts/dailynewscn.js.md)。
- `scripts/ddnsto.py`：真实执行时创建七天免费套餐订单；真实执行时将订单套餐绑定到指定路由器并延长套餐到期时间。完整说明见 [ddnsto.py.md](docs/scripts/ddnsto.py.md)。
- `scripts/deepflood_checkin.py`：正式运行向 DeepFlood 提交每日签到，可能获得鸡腿并改变账号签到及积分状态；正式运行通知启用且模块可用时，通过青龙已配置渠道发送脱敏任务汇总。完整说明见 [deepflood_checkin.py.md](docs/scripts/deepflood_checkin.py.md)。
- `scripts/durex.py`：每日签到改变签到状态并可能获得积分；开启分享后上报活动分享记录并可能获得奖励。完整说明见 [durex.py.md](docs/scripts/durex.py.md)。
- `scripts/enshan_checkin.py`：正式运行提交每日签到，可能增加恩山币和积分。；正式访问论坛可能产生论坛自身的登录奖励或访问记录。。完整说明见 [enshan_checkin.py.md](docs/scripts/enshan_checkin.py.md)。
- `scripts/epicfreegames.py`：向配置的 Telegram 会话发送免费游戏图片或文字提醒。；真实运行时按 QINGLONG_NOTIFY 设置通过青龙 notify.py 发送脱敏任务汇总。。完整说明见 [epicfreegames.py.md](docs/scripts/epicfreegames.py.md)。
- `scripts/erke.py`：正式运行提交会员签到，可能增加积分和签到记录。完整说明见 [erke.py.md](docs/scripts/erke.py.md)。
- `scripts/f1owkang_qingskyland_skyland.py`：实际运行时向设备认证服务注册本次设备认证信息；实际运行时换取鹰角授权及森空岛登录凭据。完整说明见 [f1owkang_qingskyland_skyland.py.md](docs/scripts/f1owkang_qingskyland_skyland.py.md)。
- `scripts/fnnasclub.py`：执行论坛签到，更新签到记录及论坛对应奖励；正式运行向已配置的青龙通知渠道发送脱敏总结。完整说明见 [fnnasclub.py.md](docs/scripts/fnnasclub.py.md)。
- `scripts/forum_download.py`：启用 sign 或 sign_plus 时提交每日签到并可能获得签到奖励。；首页访问及页面读取可能增加论坛访问统计或触发站点每日访问奖励。。完整说明见 [forum_download.py.md](docs/scripts/forum_download.py.md)。
- `scripts/fwxs_checkin.js`：通过 GET /qiandao 完成废文网签到，增加签到天数及服务端签到奖励（以站点规则为准）；正式执行结束后通过青龙通知渠道发送脱敏任务统计（可关闭）。完整说明见 [fwxs_checkin.js.md](docs/scripts/fwxs_checkin.js.md)。
- `scripts/fxh.js`：实际执行每日签到，改变签到状态并由服务端发放积分；启用通知时调用青龙通知模块发送任务总结。完整说明见 [fxh.js.md](docs/scripts/fxh.js.md)。
- `scripts/get_yys_cgvideo.py`：显式下载且非预演时创建保存目录、媒体文件和校验清单；实际运行且通知开启时调用青龙通知发送摘要。完整说明见 [get_yys_cgvideo.py.md](docs/scripts/get_yys_cgvideo.py.md)。
- `scripts/get_yys_imagelinks.py`：仅在 YYS_DOWNLOAD 显式开启时创建素材目录并保存原画或视频文件；视频同时维护标题历史记录。；正式运行且通知开启时调用青龙通知模块发送脱敏任务结果。。完整说明见 [get_yys_imagelinks.py.md](docs/scripts/get_yys_imagelinks.py.md)。
- `scripts/hellogithub.py`：正式运行时提交月刊内容及任务总结到青龙通知渠道；所有月刊消息提交成功后原子更新本地已发送期号状态文件。完整说明见 [hellogithub.py.md](docs/scripts/hellogithub.py.md)。
- `scripts/hifiti_checkin.py`：向 HiFiTi 提交每日签到；向 HiFiHi 提交每日签到。完整说明见 [hifiti_checkin.py.md](docs/scripts/hifiti_checkin.py.md)。
- `scripts/hlyl.py`：未签到时提交每日签到，可能获得积分和成长积分；显式开启时执行活动抽奖，可能消耗活动次数或积分并获得奖品。完整说明见 [hlyl.py.md](docs/scripts/hlyl.py.md)。
- `scripts/hsay.py`：向沪上阿姨签到接口提交每日签到，领取活动奖励；实际模式下通过青龙通知模块发送脱敏任务总结。完整说明见 [hsay.py.md](docs/scripts/hsay.py.md)。
- `scripts/huaruntong_wx.py`：正式运行提交签到与答题结果，可能获得签到积分；正式运行通过青龙通知组件发送脱敏任务汇总。完整说明见 [huaruntong_wx.py.md](docs/scripts/huaruntong_wx.py.md)。
- `scripts/hykb_gamesign.js`：默认向所发现的未结束游戏活动提交每日签到，可能领取相应活动奖励。；仅在 HYKB_ALLOW_EXPERIENCE=1 且活动要求试玩时，记录官方试玩前置动作。。完整说明见 [hykb_gamesign.js.md](docs/scripts/hykb_gamesign.js.md)。
- `scripts/ikuuu_checkin.py`：实际运行时邮箱密码登录并建立账号会话；实际运行时提交每日签到，可能增加账号流量。完整说明见 [ikuuu_checkin.py.md](docs/scripts/ikuuu_checkin.py.md)。
- `scripts/imaotai.py`：显式开启后提交商品申购申请；启用耐力任务后领取耐力奖励。完整说明见 [imaotai.py.md](docs/scripts/imaotai.py.md)。
- `scripts/index.js`：正式运行时创建明确指定的图片目录并保存收藏原图；替换未通过校验的普通图片文件；下载过程中创建临时文件并在结束时清理。完整说明见 [index.js.md](docs/scripts/index.js.md)。
- `scripts/iqiyi_checkin.py`：自然月签到改变签到记录并可能发放积分；网页积分签到改变积分及签到记录。完整说明见 [iqiyi_checkin.py.md](docs/scripts/iqiyi_checkin.py.md)。
- `scripts/jc_checkin.py`：正式运行登录并建立账号会话；正式运行每日签到，可能增加机场签到流量或奖励。完整说明见 [jc_checkin.py.md](docs/scripts/jc_checkin.py.md)。
- `scripts/jcqd.py`：向所选站点提交登录并建立会话；向所选站点提交每日签到，可能获得流量或站点签到奖励。完整说明见 [jcqd.py.md](docs/scripts/jcqd.py.md)。
- `scripts/jingyiluntan_sign.py`：正式运行提交每日签到；仅在 JYLT_RATE=1 时提交热门帖 +1 评分和附言，消耗论坛允许的评分额度。完整说明见 [jingyiluntan_sign.py.md](docs/scripts/jingyiluntan_sign.py.md)。
- `scripts/jissbon.py`：实际执行时提交每日签到；实际执行时登记分享奖励。完整说明见 [jissbon.py.md](docs/scripts/jissbon.py.md)。
- `scripts/jyj.py`：签到并领取积分或水滴奖励；创建及提交拍一拍和药材游戏记录，领取游戏奖励。完整说明见 [jyj.py.md](docs/scripts/jyj.py.md)。
- `scripts/kanxue.js`：正式执行时提交签到请求，改变账号当日签到状态并可能领取论坛签到奖励。；通知启用且可用时发送脱敏任务总结；断网预演限制通知组件联网。。完整说明见 [kanxue.js.md](docs/scripts/kanxue.js.md)。
- `scripts/kgqq.py`：领取签到奖励，可能增加账号鲜花或道具。；开启抽奖后执行抽奖，可能消耗次数或活动资源并发放奖励。。完整说明见 [kgqq.py.md](docs/scripts/kgqq.py.md)。
- `scripts/kjwj.py`：未签到时提交每日签到并获得积分；正式执行时按通知开关发送青龙任务通知。完整说明见 [kjwj.py.md](docs/scripts/kjwj.py.md)。
- `scripts/kuaishou_reward_status.py`：见详单。完整说明见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/kuku_daily.py`：领取每日登录任务积分；领取对话任务积分。完整说明见 [kuku_daily.py.md](docs/scripts/kuku_daily.py.md)。
- `scripts/kurobbs_sign.py`：库街区社区签到并领取对应奖励；鸣潮游戏签到并领取对应奖励。完整说明见 [kurobbs_sign.py.md](docs/scripts/kurobbs_sign.py.md)。
- `scripts/l.py`：正式运行的已登录页面请求可能由站点计入访问或浏览记录；是否更新由站点决定；正式运行且启用通知时调用青龙通知模块发送任务汇总。完整说明见 [l.py.md](docs/scripts/l.py.md)。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`：正式执行时提交 Leaflow 每日签到表单，记录账号签到并可能发放当日奖励；正式执行且通知启用时调用青龙通知模块发送脱敏任务汇总。完整说明见 [leaflow_checkin_pyleaflow_checkin.py.md](docs/scripts/leaflow_checkin_pyleaflow_checkin.py.md)。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`：正式运行在咔叽网单为已登录账号执行每日签到；通知开启且助手可用时发送脱敏任务汇总；预演仅尝试离线通知。完整说明见 [littlewuh_qinglongbox_dailycheckin_scripts.py.md](docs/scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md)。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`：正式运行调用 NodeSeek 签到接口，产生当日签到记录并领取签到奖励。；启用通知时向已配置的青龙通知渠道发送脱敏任务汇总。。完整说明见 [lizhixu_ql_script_hub_nodeseek.py.md](docs/scripts/lizhixu_ql_script_hub_nodeseek.py.md)。
- `scripts/lizhixu_ql_script_hub_youdao.py`：正式运行刷新登录会话；正式运行同步奖励并增加云笔记空间。完整说明见 [lizhixu_ql_script_hub_youdao.py.md](docs/scripts/lizhixu_ql_script_hub_youdao.py.md)。
- `scripts/lobsterai_checkin.py`：向官方接口提交每日签到，领取活动积分。；RT 自动续期会轮换账号令牌，并在本地写入私密续期缓存。。完整说明见 [lobsterai_checkin.py.md](docs/scripts/lobsterai_checkin.py.md)。
- `scripts/loomy_daily.py`：正式默认执行刷新账号每日赠送积分。；显式批量或单项领取时上报新手任务完成状态并领取积分。。完整说明见 [loomy_daily.py.md](docs/scripts/loomy_daily.py.md)。
- `scripts/lynkco_qinglong_single.py`：每日签到并领取服务端奖励；默认上报文章分享并可能增加能量体积分，可用LYNKCO_DO_SHARE关闭。完整说明见 [lynkco_qinglong_single.py.md](docs/scripts/lynkco_qinglong_single.py.md)。
- `scripts/main.py`：正式运行时在显式指定目录创建日期子目录并保存已验证的壁纸文件；不覆盖已有文件。；正式运行且启用通知时，调用青龙通知模块发送脱敏总结。。完整说明见 [main.py.md](docs/scripts/main.py.md)。
- `scripts/mifan_optimized.py`：登录创建会话、登出结束本次会话；每日签到改变签到状态并可能获得米粒。完整说明见 [mifan_optimized.py.md](docs/scripts/mifan_optimized.py.md)。
- `scripts/mimotion.py`：正式登录会申请 Zepp 授权及登录令牌。；仅 MIMOTION_ACTION=upload 时上传本人提供的当天运动记录，修改 summary.stp.ttl；其它提供的记录字段保持原样，不合成心率或睡眠数据。。完整说明见 [mimotion.py.md](docs/scripts/mimotion.py.md)。
- `scripts/netease_task.py`：手机、网页与云贝签到改变签到记录或积分；领取已完成云贝任务奖励。完整说明见 [netease_task.py.md](docs/scripts/netease_task.py.md)。
- `scripts/nga_checkin.py`：每日签到改变签到及奖励状态；显式开启时增加日常任务计数及奖励状态。完整说明见 [nga_checkin.py.md](docs/scripts/nga_checkin.py.md)。
- `scripts/nodeseek.py`：正式运行向 NodeSeek 提交签到并领取随机或固定奖励。；通知启用且助手可用时发送脱敏任务通知。。完整说明见 [nodeseek.py.md](docs/scripts/nodeseek.py.md)。
- `scripts/nodeseek_checkin.py`：成功请求会记录 NodeSeek 当日签到并可能增加鸡腿余额；启用青龙通知时会向已配置的通知渠道发送脱敏任务汇总。完整说明见 [nodeseek_checkin.py.md](docs/scripts/nodeseek_checkin.py.md)。
- `scripts/nte.py`：刷新用户中心令牌，可能轮换服务端会话凭据。；社区签到，可能增加经验和金币。。完整说明见 [nte.py.md](docs/scripts/nte.py.md)。
- `scripts/officeace_daily.py`：默认领取每日签到奖励和新人礼，可能增加积分；查询和预演不领取；实时模式通知开启且组件或兼容推送已配置时发送脱敏任务通知。完整说明见 [officeace_daily.py.md](docs/scripts/officeace_daily.py.md)。
- `scripts/ole.py`：正式模式向 Ole 提交会员签到，可能增加签到记录及奖励积分；正式模式按青龙配置发送任务通知。完整说明见 [ole.py.md](docs/scripts/ole.py.md)。
- `scripts/passnat_checkin.py`：向 PassNAT 提交每日签到并可能增加账号流量。完整说明见 [passnat_checkin.py.md](docs/scripts/passnat_checkin.py.md)。
- `scripts/psnine.py`：向 PSNINE 提交每日祈祷签到，改变签到记录及服务发放的奖励；实时模式向配置的青龙通知渠道发送脱敏任务摘要。完整说明见 [psnine.py.md](docs/scripts/psnine.py.md)。
- `scripts/pt_sign_v5.js`：向选中站点提交签到，可能增加站点奖励及连续签到计数；遇到 SafeLine 时提交挑战验证并更新当前进程内的会话 Cookie，不写入文件。完整说明见 [pt_sign_v5.js.md](docs/scripts/pt_sign_v5.js.md)。
- `scripts/qoder_airscript.js`：显式启用账号后领取可领活动奖励；必要时或仅刷新模式下刷新令牌，可能轮换刷新令牌。完整说明见 [qoder_airscript.js.md](docs/scripts/qoder_airscript.js.md)。
- `scripts/quark_signin.py`：实时模式下为尚未签到的账号完成每日签到并领取存储空间奖励；实时模式下启用通知时通过青龙发送脱敏任务摘要。完整说明见 [quark_signin.py.md](docs/scripts/quark_signin.py.md)。
- `scripts/raccoon_daily.py`：正式模式请求 setting_info 触发每日积分发放。；正式模式默认领取桌面端、手机端一次性登录积分。。完整说明见 [raccoon_daily.py.md](docs/scripts/raccoon_daily.py.md)。
- `scripts/rainyun.py`：登录创建账号会话。；每日签到改变当日签到状态并领取积分。。完整说明见 [rainyun.py.md](docs/scripts/rainyun.py.md)。
- `scripts/rousi_checkin.js`：正式运行未签到账号时提交普通签到，改变签到记录并领取服务端积分奖励；正式运行且通知开启时向青龙配置的通知渠道发送脱敏总结。完整说明见 [rousi_checkin.js.md](docs/scripts/rousi_checkin.js.md)。
- `scripts/sf.py`：分享登录创建账号会话；签到并领取签到礼包。完整说明见 [sf.py.md](docs/scripts/sf.py.md)。
- `scripts/sfsu_checkin.py`：执行每日签到；完成符合安全规则的积分及丰蜜任务并领取奖励。完整说明见 [sfsu_checkin.py.md](docs/scripts/sfsu_checkin.py.md)。
- `scripts/sgs.py`：每日签到；显式开启时写入文章阅读记录。完整说明见 [sgs.py.md](docs/scripts/sgs.py.md)。
- `scripts/shuyi.py`：在书亦烧仙草账号执行签到并领取服务端发放的积分；实际执行时向青龙通知渠道发送脱敏任务总结。完整说明见 [shuyi.py.md](docs/scripts/shuyi.py.md)。
- `scripts/sign_in.py`：正式执行时向看雪论坛提交签到，可能增加账号积分；正式执行且通知开启时通过青龙发送脱敏任务总结。完整说明见 [sign_in.py.md](docs/scripts/sign_in.py.md)。
- `scripts/skland_daily.py`：未配置 SKLAND_DID 时向上游设备服务注册临时设备标识；账密或通行证登录时换取授权和账号会话凭据。完整说明见 [skland_daily.py.md](docs/scripts/skland_daily.py.md)。
- `scripts/skland_demo.py`：实际模式下明日方舟角色每日签到并领取奖励；实际模式下终末地角色每日签到并领取奖励。完整说明见 [skland_demo.py.md](docs/scripts/skland_demo.py.md)。
- `scripts/skyland.py`：向数美服务提交模拟浏览器指纹并生成设备凭据；通过鹰角授权接口生成登录授权并取得森空岛会话凭据。完整说明见 [skyland.py.md](docs/scripts/skyland.py.md)。
- `scripts/smzdm_checkin.js`：在什么值得买账号上执行每日签到并改变当日签到状态；满足条件时领取连续签到额外奖励并改变账号奖励状态。完整说明见 [smzdm_checkin.js.md](docs/scripts/smzdm_checkin.js.md)。
- `scripts/ssl_cert_check.py`：实际模式下通过青龙通知通道发送证书检查报告；不修改 Cloudflare DNS、证书或账号数据。完整说明见 [ssl_cert_check.py.md](docs/scripts/ssl_cert_check.py.md)。
- `scripts/sudojia_33agilestudio.js`：登录建立账户会话；提交每日签到，按服务端规则获得积分。完整说明见 [sudojia_33agilestudio.js.md](docs/scripts/sudojia_33agilestudio.js.md)。
- `scripts/sudojia_allgirls.js`：未签到时执行每日签到，可能获得平台签到积分。完整说明见 [sudojia_allgirls.js.md](docs/scripts/sudojia_allgirls.js.md)。
- `scripts/sudojia_amx.js`：未签到时执行每日签到，可能获得积分。完整说明见 [sudojia_amx.js.md](docs/scripts/sudojia_amx.js.md)。
- `scripts/sudojia_authcheck.js`：显式允许时，海澜之家游戏登录可能创建会话；已移除默认邀请人绑定；显式允许时，老板电器用户接口可能同步账号；请求已设置不需要同步。完整说明见 [sudojia_authcheck.js.md](docs/scripts/sudojia_authcheck.js.md)。
- `scripts/sudojia_bananavideo.js`：每日签到及任务奖励可能增加金币。；登记广告点击、下载请求、视频播放和二维码保存任务；不实际下载视频或保存二维码文件。。完整说明见 [sudojia_bananavideo.js.md](docs/scripts/sudojia_bananavideo.js.md)。
- `scripts/sudojia_beiyinmei.js`：实际执行每日签到，可能领取签到奖励。；开启通知且模块可用时发送脱敏任务摘要。。完整说明见 [sudojia_beiyinmei.js.md](docs/scripts/sudojia_beiyinmei.js.md)。
- `scripts/sudojia_botanystar.js`：正式执行登录以创建账号会话；提交每日签到并领取绿星币奖励。完整说明见 [sudojia_botanystar.js.md](docs/scripts/sudojia_botanystar.js.md)。
- `scripts/sudojia_bwtea.js`：未签到时提交新版每日签到，可能增加积分；启用通知时通过青龙通知渠道发送脱敏任务总结。完整说明见 [sudojia_bwtea.js.md](docs/scripts/sudojia_bwtea.js.md)。
- `scripts/sudojia_colorful_mall.js`：登录换取凭据并刷新登录时间；旧版和新版签到可能增加积分及改变签到记录。完整说明见 [sudojia_colorful_mall.js.md](docs/scripts/sudojia_colorful_mall.js.md)。
- `scripts/sudojia_flyant.js`：每日签到领取奖励；提供真实步数后兑换环保豆。完整说明见 [sudojia_flyant.js.md](docs/scripts/sudojia_flyant.js.md)。
- `scripts/sudojia_fnnas.js`：执行本站每日打卡，可能获得论坛奖励；通知启用且模块可用时发送任务摘要。完整说明见 [sudojia_fnnas.js.md](docs/scripts/sudojia_fnnas.js.md)。
- `scripts/sudojia_hgf.js`：每日签到会更新签到记录并可能获得酒币。；提交浏览任务并领取相应任务奖励。。完整说明见 [sudojia_hgf.js.md](docs/scripts/sudojia_hgf.js.md)。
- `scripts/sudojia_hlzj_game.js`：领取每日游戏电力奖励。；执行每日签到并领取奖励。。完整说明见 [sudojia_hlzj_game.js.md](docs/scripts/sudojia_hlzj_game.js.md)。
- `scripts/sudojia_hzhfp.js`：调用每日签到接口，更新签到记录并可能获得签到积分；正式执行且通知开启时，通过青龙通知模块发送任务汇总。完整说明见 [sudojia_hzhfp.js.md](docs/scripts/sudojia_hzhfp.js.md)。
- `scripts/sudojia_instax.js`：签到改变服务端签到记录，并可能增加积分；显式开启抽奖后消耗抽奖机会，并产生中奖记录。完整说明见 [sudojia_instax.js.md](docs/scripts/sudojia_instax.js.md)。
- `scripts/sudojia_jhcard.js`：签到并领取服务端发放的积分；仅在账号显式追加 #true 时发表五次公开评论。完整说明见 [sudojia_jhcard.js.md](docs/scripts/sudojia_jhcard.js.md)。
- `scripts/sudojia_jiangshan.js`：签到及阅读可能增加积分、经验和任务进度；显式启用 share 后上报分享任务并改变进度。完整说明见 [sudojia_jiangshan.js.md](docs/scripts/sudojia_jiangshan.js.md)。
- `scripts/sudojia_jindian.js`：对尚未签到的账号执行每日签到，可能增加积分。完整说明见 [sudojia_jindian.js.md](docs/scripts/sudojia_jindian.js.md)。
- `scripts/sudojia_jlc_yj.js`：开源平台每日签到增加积分；下单助手每日签到增加金豆。完整说明见 [sudojia_jlc_yj.js.md](docs/scripts/sudojia_jlc_yj.js.md)。
- `scripts/sudojia_juejin.js`：尚未签到时提交每日签到，领取矿石奖励；显式启用后在免费次数大于零时提交一次抽奖，使用一次免费机会。完整说明见 [sudojia_juejin.js.md](docs/scripts/sudojia_juejin.js.md)。
- `scripts/sudojia_kozbs.js`：未签到时提交每日签到，可能增加账号积分和签到记录。；通知开启且模块可用时向已配置的通知渠道发送脱敏任务汇总。。完整说明见 [sudojia_kozbs.js.md](docs/scripts/sudojia_kozbs.js.md)。
- `scripts/sudojia_ktgzs.js`：正式运行调用每日签到接口，产生签到记录及服务端奖励积分。完整说明见 [sudojia_ktgzs.js.md](docs/scripts/sudojia_ktgzs.js.md)。
- `scripts/sudojia_kukahome.js`：每日签到可能增加账号积分并更新连续签到记录；正式模式通过青龙发送脱敏任务结果通知（可关闭）。完整说明见 [sudojia_kukahome.js.md](docs/scripts/sudojia_kukahome.js.md)。
- `scripts/sudojia_kuro.js`：社区签到并领取签到库洛币；鸣潮角色每日签到。完整说明见 [sudojia_kuro.js.md](docs/scripts/sudojia_kuro.js.md)。
- `scripts/sudojia_laoban.js`：执行每日签到并增加服务端核定积分；领取可领取的连续签到积分奖励。完整说明见 [sudojia_laoban.js.md](docs/scripts/sudojia_laoban.js.md)。
- `scripts/sudojia_longfor.js`：每日签到可能增加成长值；启用抽奖流程后，抽奖签到可能增加抽奖机会。完整说明见 [sudojia_longfor.js.md](docs/scripts/sudojia_longfor.js.md)。
- `scripts/sudojia_mallcoo.js`：执行每日签到并按服务规则获得积分；正式运行时通过青龙通知渠道发送任务摘要。完整说明见 [sudojia_mallcoo.js.md](docs/scripts/sudojia_mallcoo.js.md)。
- `scripts/sudojia_mawuwang.js`：未签到时参与签到活动，可能获得积分或签到奖励；正式模式通过青龙已配置渠道发送脱敏通知。完整说明见 [sudojia_mawuwang.js.md](docs/scripts/sudojia_mawuwang.js.md)。
- `scripts/sudojia_midea.js`：正式执行时提交每日签到，可能获得积分或成长值；通知开启且模块可用时，向青龙配置的通知渠道发送脱敏摘要。完整说明见 [sudojia_midea.js.md](docs/scripts/sudojia_midea.js.md)。
- `scripts/sudojia_moto.js`：正式运行提交每日签到，可能获得能量奖励；不自动重试提交；正式运行时通过青龙通知模块发送脱敏任务摘要（可关闭）。完整说明见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。
- `scripts/sudojia_mxbc.js`：正式运行执行蜜雪冰城每日签到，可能增加雪王币并更新连续签到天数。；正式运行通过青龙通知模块向用户配置的通知通道发送脱敏任务摘要（可关闭）。。完整说明见 [sudojia_mxbc.js.md](docs/scripts/sudojia_mxbc.js.md)。
- `scripts/sudojia_naixue.js`：未签到时提交每日签到，可能增加签到记录及奖励。；开启通知时通过现有青龙通知模块发送脱敏任务总结。。完整说明见 [sudojia_naixue.js.md](docs/scripts/sudojia_naixue.js.md)。
- `scripts/sudojia_nestle.js`：显式配置 NESTLE_TASK_GUIDS 后，向任务完成接口提交授权任务，可能改变任务完成状态和巢币奖励。；正式运行且通知开启时，通过青龙通知模块发送脱敏任务摘要。。完整说明见 [sudojia_nestle.js.md](docs/scripts/sudojia_nestle.js.md)。
- `scripts/sudojia_nfhk.js`：执行每日签到并领取服务端对应签到权益；启用通知时发送脱敏任务总结。完整说明见 [sudojia_nfhk.js.md](docs/scripts/sudojia_nfhk.js.md)。
- `scripts/sudojia_opposhop.js`：每日签到可能增加积分；显式启用白名单任务后上报完成状态并领取积分奖励。完整说明见 [sudojia_opposhop.js.md](docs/scripts/sudojia_opposhop.js.md)。
- `scripts/sudojia_pangge.js`：每日签到并领取服务端发放的积分；正式运行时按通知开关发送青龙结果通知。完整说明见 [sudojia_pangge.js.md](docs/scripts/sudojia_pangge.js.md)。
- `scripts/sudojia_paotea.js`：对明确配置的活动执行每日签到；启用通知时通过青龙通知模块发送脱敏总结。完整说明见 [sudojia_paotea.js.md](docs/scripts/sudojia_paotea.js.md)。
- `scripts/sudojia_shmedia.js`：签到及阅读、视频任务可能增加账号积分并改变任务进度；显式开启后收藏文章并可能获取积分。完整说明见 [sudojia_shmedia.js.md](docs/scripts/sudojia_shmedia.js.md)。
- `scripts/sudojia_shuifei.js`：未签到时提交签到，可能增加积分及连续签到天数；正式运行时按通知开关发送青龙通知。完整说明见 [sudojia_shuifei.js.md](docs/scripts/sudojia_shuifei.js.md)。
- `scripts/sudojia_sspanel.js`：登录创建站点会话；执行每日签到并可能获得站点流量奖励。完整说明见 [sudojia_sspanel.js.md](docs/scripts/sudojia_sspanel.js.md)。
- `scripts/sudojia_starmom.js`：每日签到及获取积分；提交五项浏览任务的开始和完成记录并领取积分。完整说明见 [sudojia_starmom.js.md](docs/scripts/sudojia_starmom.js.md)。
- `scripts/sudojia_tebu.js`：正式执行时提交每日签到并可能获得积分；启用通知且模块可用时发送任务汇总通知。完整说明见 [sudojia_tebu.js.md](docs/scripts/sudojia_tebu.js.md)。
- `scripts/sudojia_tilta.js`：未签到时提交每日签到并可能获得积分；浏览商品及提交阅读任务会改变任务进度并可能获得积分。完整说明见 [sudojia_tilta.js.md](docs/scripts/sudojia_tilta.js.md)。
- `scripts/sudojia_tuchong.js`：正式运行登录会建立服务端会话。；正式运行每日签到会改变签到状态并可能增加积分。。完整说明见 [sudojia_tuchong.js.md](docs/scripts/sudojia_tuchong.js.md)。
- `scripts/sudojia_v2ex.js`：领取 V2EX 每日登录奖励，增加账号余额；正式运行且通知开启时发送青龙任务结果通知。完整说明见 [sudojia_v2ex.js.md](docs/scripts/sudojia_v2ex.js.md)。
- `scripts/sudojia_wnna.js`：未签到时执行每日签到并获得服务端发放的奖励；正式运行且通知启用时发送青龙任务通知。完整说明见 [sudojia_wnna.js.md](docs/scripts/sudojia_wnna.js.md)。
- `scripts/sudojia_xhn.js`：登录产生授权会话；每日签到可能增加账号积分。完整说明见 [sudojia_xhn.js.md](docs/scripts/sudojia_xhn.js.md)。
- `scripts/sudojia_xiangwan.js`：正式运行使用账号密码登录，可能创建服务端会话；正式运行每日签到并领取玩豆。完整说明见 [sudojia_xiangwan.js.md](docs/scripts/sudojia_xiangwan.js.md)。
- `scripts/sudojia_xiaomi_community.js`：每日调用微信签到接口增加成长值；启用通知且正式执行时，通过青龙已配置通知渠道发送脱敏结果。完整说明见 [sudojia_xiaomi_community.js.md](docs/scripts/sudojia_xiaomi_community.js.md)。
- `scripts/sudojia_xinxi.js`：每日签到并可能获得喜点；启用免费抽奖后消耗一次免费机会并可能获得奖励。完整说明见 [sudojia_xinxi.js.md](docs/scripts/sudojia_xinxi.js.md)。
- `scripts/sudojia_xpfarm.js`：每日签到及其奖励入账；显式启用后变更所选任务完成状态并领取奖励。完整说明见 [sudojia_xpfarm.js.md](docs/scripts/sudojia_xpfarm.js.md)。
- `scripts/sudojia_znds.js`：正式运行执行每日签到，可能获得积分或奖励；仅配置 ZNDS_VISIT_UID 时访问指定他人空间，可能产生足迹或访问奖励。完整说明见 [sudojia_znds.js.md](docs/scripts/sudojia_znds.js.md)。
- `scripts/sudojia_zxice.js`：未签到时提交每日签到并领取奶滴奖励；正式模式按通知配置发送任务结果通知。完整说明见 [sudojia_zxice.js.md](docs/scripts/sudojia_zxice.js.md)。
- `scripts/supertopicsign.py`：对关注的超话执行签到，改变签到状态。完整说明见 [supertopicsign.py.md](docs/scripts/supertopicsign.py.md)。
- `scripts/synspoint.py`：会员签到及接口对应积分变化；提交浏览会员商城任务并可能获取积分。完整说明见 [synspoint.py.md](docs/scripts/synspoint.py.md)。
- `scripts/task_ef2d3863.js`：正式运行刷新账号访问会话，服务端可能轮换刷新令牌。；正式运行提交阿里云盘每日签到。。完整说明见 [task_ef2d3863.js.md](docs/scripts/task_ef2d3863.js.md)。
- `scripts/tencent_video_checkin.py`：实际执行时提交每日签到，可能增加 V力值；实际执行时领取每日观看奖励，可能增加 V力值。完整说明见 [tencent_video_checkin.py.md](docs/scripts/tencent_video_checkin.py.md)。
- `scripts/tieba_checkin.py`：正式执行时提交关注贴吧签到，改变对应贴吧当日签到状态及可能产生签到奖励。；仅显式开启成长任务且 Cookie 同时含 BDUSS 和 CUID 时提交 APP 成长每日签到，改变当日成长签到状态及可能产生的成长奖励。。完整说明见 [tieba_checkin.py.md](docs/scripts/tieba_checkin.py.md)。
- `scripts/tjd_daily.py`：社区签到增加金币和经验；浏览帖子增加阅读及任务进度。完整说明见 [tjd_daily.py.md](docs/scripts/tjd_daily.py.md)。
- `scripts/trae_checkin.py`：签到领取积分；续期在服务端轮换刷新凭据。完整说明见 [trae_checkin.py.md](docs/scripts/trae_checkin.py.md)。
- `scripts/tsthb_checkin.py`：向官方签到接口提交每日签到，可能获得积分或奖励；正式运行且通知开启时，通过已有青龙通知模块发送脱敏结果。完整说明见 [tsthb_checkin.py.md](docs/scripts/tsthb_checkin.py.md)。
- `scripts/ty_netdisk_checkin.py`：正式模式每日签到可能增加账号奖励空间；启用签到奖励开关后，正式模式可能消耗当天已有签到抽奖机会并增加奖励空间。完整说明见 [ty_netdisk_checkin.py.md](docs/scripts/ty_netdisk_checkin.py.md)。
- `scripts/tyqhdraw.py`：登录创建账号会话；显式开启时兑换抽奖，可能消耗资产或抽奖机会并获得奖品。完整说明见 [tyqhdraw.py.md](docs/scripts/tyqhdraw.py.md)。
- `scripts/valorantstore.py`：实时模式调用认证接口刷新账号票据，仅保存在当前独立会话内存中。；通知开启时向已配置青龙通知渠道发送脱敏商店与任务总结。。完整说明见 [valorantstore.py.md](docs/scripts/valorantstore.py.md)。
- `scripts/vortexa_free_claim.js`：使用密码或刷新 Cookie 登录时创建或续期服务端登录会话；更新的访问 Token 和 Cookie 仅保存在本次进程内，不写文件。；仅在 VORTEXA_CLAIM 开启且产品套餐明确免费时提交免费主机领取，创建账号免费主机服务。。完整说明见 [vortexa_free_claim.js.md](docs/scripts/vortexa_free_claim.js.md)。
- `scripts/wangchao.py`：实时登录会建立账号及活动服务会话；默认浏览未读文章并提交阅读记录，改变每日阅读进度。完整说明见 [wangchao.py.md](docs/scripts/wangchao.py.md)。
- `scripts/wentiweilaihui.py`：未签到时执行文体未来荟每日签到，可能增加积分；正式模式启用通知时发送脱敏任务总结。完整说明见 [wentiweilaihui.py.md](docs/scripts/wentiweilaihui.py.md)。
- `scripts/workbuddy.py`：每日签到及服务端积分、连签奖励状态变更。；配置刷新令牌且访问令牌过期时向服务端申请续期，仅在进程内更新凭据。。完整说明见 [workbuddy.py.md](docs/scripts/workbuddy.py.md)。
- `scripts/workbuddy_daily.py`：默认进行每日签到、领取已完成成长任务奖励、领取旅行奖励或派遣Buddy旅行；显式成长任务可能创建模型对话、消耗积分并发送模拟活跃事件，变更任务登记与成长进度；上报成功不代表真实桌面操作成功。完整说明见 [workbuddy_daily.py.md](docs/scripts/workbuddy_daily.py.md)。
- `scripts/wps_clock_in.py`：见详单。完整说明见 [wps_clock_in.py.md](docs/scripts/wps_clock_in.py.md)。
- `scripts/wyycg.py`：执行每日签到，可能领取云游戏时长；真实执行时通过已配置的通知渠道发送脱敏任务总结。完整说明见 [wyycg.py.md](docs/scripts/wyycg.py.md)。
- `scripts/yht.py`：参加种植活动；消耗活动肥料进行施肥。完整说明见 [yht.py.md](docs/scripts/yht.py.md)。
- `scripts/youdao.py`：刷新账号登录会话。；领取每日同步奖励并增加账号空间。。完整说明见 [youdao.py.md](docs/scripts/youdao.py.md)。
- `scripts/yyshuijuantime.py`：正式运行在显式配置路径创建或更新活动 JSON 文件，必要时创建其父目录；正式运行通知开启时，通过青龙现有通知模块发送任务摘要。完整说明见 [yyshuijuantime.py.md](docs/scripts/yyshuijuantime.py.md)。
- `scripts/zcode_cn_daily.py`：实际领取时发放或变更账号套餐权益。；仅 ZCODE_ACTIVATION=1 且非只读、非预演时补报启动和日活事件，可能影响套餐资格。。完整说明见 [zcode_cn_daily.py.md](docs/scripts/zcode_cn_daily.py.md)。
- `scripts/zippo.py`：签到增加积分；收藏商品及领取积分。完整说明见 [zippo.py.md](docs/scripts/zippo.py.md)。
- `scripts/zodgame_test.py`：提交每日签到；首次加入 Bux 广告任务。完整说明见 [zodgame_test.py.md](docs/scripts/zodgame_test.py.md)。

使用测试账号先行验证。停止使用时应禁用任务、删除订阅和敏感环境变量；怀疑凭据泄漏时立即在对应平台撤销会话。

## 许可证与来源

仓库发布许可证：`GPL-3.0-only`。每个脚本仍保留准确来源：

- `scripts/139_yunduo.py`：上游 `deeplee/personal-scripts` / `139_yunduo.py` / `c8c7c0f4fd1802df86c32a86c26b5c26cfef5023`。 详见 [139_yunduo.py.md](docs/scripts/139_yunduo.py.md)。
- `scripts/2cycdx.py`：上游 `Tgkkez/2cycdx_Autosignin` / `autosignin.py` / `9afc3b1513b1f0c683e0eda992c1c33d627d9996`。 详见 [2cycdx.py.md](docs/scripts/2cycdx.py.md)。
- `scripts/51cto_sign.js`：上游 `huwangkeji/51cto_sign_authed` / `51cto_sign.js` / `c8231e0c5a52fdcd5c6020a3522c7b2c65a1aa84`。 详见 [51cto_sign.js.md](docs/scripts/51cto_sign.js.md)。
- `scripts/52pojie.js`：上游 `NobyDa/Script` / `52pojie-DailyBonus/52pojie.js` / `0b8d083d444f4476700cb9d5d059c07b42da85eb`。 详见 [52pojie.js.md](docs/scripts/52pojie.js.md)。
- `scripts/999.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/999/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [999.py.md](docs/scripts/999.py.md)。
- `scripts/acfun.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/acfun/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [acfun.py.md](docs/scripts/acfun.py.md)。
- `scripts/agentrouter.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/agentrouter/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [agentrouter.py.md](docs/scripts/agentrouter.py.md)。
- `scripts/airport.py`：上游 `CN-Grace/QinglongScripts` / `Airport.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [airport.py.md](docs/scripts/airport.py.md)。
- `scripts/akile_checkin.py`：上游 `GGBondHere/QingLongScripts` / `scripts/akile_checkin.py` / `79238495c2489b52a6cc001ba9d6703ae6d57955`。 详见 [akile_checkin.py.md](docs/scripts/akile_checkin.py.md)。
- `scripts/aliyun_web.js`：上游 `llle0x/qinglong` / `aliyun_web.js` / `5bee6cd9f18635d3dd4f96f9c1057f6ef5798c67`。 详见 [aliyun_web.js.md](docs/scripts/aliyun_web.js.md)。
- `scripts/aliyundrive_checkin.js`：上游 `huwangkeji/aliyundrive_checkin` / `aliyundrive_checkin.js` / `267ee025840c5b55dce5b5e1e365fb52ac500fce`。 详见 [aliyundrive_checkin.js.md](docs/scripts/aliyundrive_checkin.js.md)。
- `scripts/aliyunpan_checkin.py`：上游 `agluo/ql-script-hub` / `aliyunpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [aliyunpan_checkin.py.md](docs/scripts/aliyunpan_checkin.py.md)。
- `scripts/aolaxing.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/aolaxing/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [aolaxing.py.md](docs/scripts/aolaxing.py.md)。
- `scripts/api_hax.py`：上游 `OreosLab/checkinpanel` / `api_hax.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [api_hax.py.md](docs/scripts/api_hax.py.md)。
- `scripts/arknightsbanner.py`：上游 `CN-Grace/QinglongScripts` / `ArknightsBanner.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [arknightsbanner.py.md](docs/scripts/arknightsbanner.py.md)。
- `scripts/atxyq.py`：上游 `Rookie-wb-WH/ql_scripts` / `atxyq.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [atxyq.py.md](docs/scripts/atxyq.py.md)。
- `scripts/auto_buy.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/shyp/auto_buy.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [auto_buy.py.md](docs/scripts/auto_buy.py.md)。
- `scripts/autoclaw_cn_daily.py`：上游 `L0NE-6/AutoClaw-Daily` / `autoclaw_cn_daily.py` / `745a15b42d58bcaf9bb50920f5405e04b4f4964b`。 详见 [autoclaw_cn_daily.py.md](docs/scripts/autoclaw_cn_daily.py.md)。
- `scripts/autosignin.js`：上游 `wang-st/aliyunSignIn` / `autoSignin.js` / `e81b2732652aadea5ee9920eb0d0adfe07dffa91`。 详见 [autosignin.js.md](docs/scripts/autosignin.js.md)。
- `scripts/autosignin.py`：上游 `AkiyaKiko/EhentaiAutoSignIn` / `autosignin.py` / `c00c3d42a61b7f526dd41b8df157444380898e57`。 详见 [autosignin.py.md](docs/scripts/autosignin.py.md)。
- `scripts/baidu.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/baidu/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [baidu.py.md](docs/scripts/baidu.py.md)。
- `scripts/baiduwangpan_checkin.py`：上游 `agluo/ql-script-hub` / `baiduwangpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [baiduwangpan_checkin.py.md](docs/scripts/baiduwangpan_checkin.py.md)。
- `scripts/baiduwp.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/baiduwp/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [baiduwp.py.md](docs/scripts/baiduwp.py.md)。
- `scripts/bilibili.py`：上游 `CN-Grace/QinglongScripts` / `Bilibili.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [bilibili.py.md](docs/scripts/bilibili.py.md)。
- `scripts/bsly_draw.py`：上游 `cloudcranes/some_scripts` / `bsly_draw.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [bsly_draw.py.md](docs/scripts/bsly_draw.py.md)。
- `scripts/bugutv.py`：上游 `MonjackWon/bugutv_AutoSignin` / `bugutv.py` / `32af515b2ae28a2cb7bf0051966804936d4ae897`。 详见 [bugutv.py.md](docs/scripts/bugutv.py.md)。
- `scripts/bwcj.py`：上游 `Rookie-wb-WH/ql_scripts` / `bwcj.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [bwcj.py.md](docs/scripts/bwcj.py.md)。
- `scripts/caigamer.js`：上游 `unitaryhighs/ql_sign_script` / `sign/caigamer.js` / `caa96862c9a31521347217b3b20b8ba3f6413c18`。 详见 [caigamer.js.md](docs/scripts/caigamer.js.md)。
- `scripts/cdrail.py`：上游 `agluo/ql-script-hub` / `CDRail.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [cdrail.py.md](docs/scripts/cdrail.py.md)。
- `scripts/cfmoto_checkin.py`：作者自有来源 `shaco_autowork/cf_sign.py`。 详见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/cg163_autocheckin.py`：上游 `Riku1998/cg163-autocheckin` / `cg163-autocheckin.py` / `d509ef623787ef39cef475a4b76405145e50997c`。 详见 [cg163_autocheckin.py.md](docs/scripts/cg163_autocheckin.py.md)。
- `scripts/chevrolet.js`：上游 `NaroisCool/naro-scripts` / `chevrolet.js` / `c2ffa8af2089bd98e1ed623c7a25d49b60ca0fdd`。 详见 [chevrolet.js.md](docs/scripts/chevrolet.js.md)。
- `scripts/ck_2nzz.py`：上游 `yuxian158/check` / `dailycheckin_scripts/ck_2nzz.py` / `723c834f121ff4eef2dec7afe521071a7efff1a9`。 详见 [ck_2nzz.py.md](docs/scripts/ck_2nzz.py.md)。
- `scripts/ck_acfun.py`：上游 `OreosLab/checkinpanel` / `ck_acfun.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_acfun.py.md](docs/scripts/ck_acfun.py.md)。
- `scripts/ck_airport.py`：上游 `OreosLab/checkinpanel` / `ck_airport.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_airport.py.md](docs/scripts/ck_airport.py.md)。
- `scripts/ck_aqc.js`：上游 `OreosLab/checkinpanel` / `ck_aqc.js` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_aqc.js.md](docs/scripts/ck_aqc.js.md)。
- `scripts/ck_baidu_url_submit.py`：上游 `OreosLab/checkinpanel` / `ck_baidu_url_submit.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_baidu_url_submit.py.md](docs/scripts/ck_baidu_url_submit.py.md)。
- `scripts/ck_bilibili.py`：上游 `OreosLab/checkinpanel` / `ck_bilibili.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_bilibili.py.md](docs/scripts/ck_bilibili.py.md)。
- `scripts/ck_ccava.py`：上游 `OreosLab/checkinpanel` / `ck_ccava.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_ccava.py.md](docs/scripts/ck_ccava.py.md)。
- `scripts/ck_csdn.py`：上游 `OreosLab/checkinpanel` / `ck_csdn.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_csdn.py.md](docs/scripts/ck_csdn.py.md)。
- `scripts/ck_du163.js`：上游 `OreosLab/checkinpanel` / `ck_du163.js` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_du163.js.md](docs/scripts/ck_du163.js.md)。
- `scripts/ck_duokan.py`：上游 `OreosLab/checkinpanel` / `ck_duokan.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_duokan.py.md](docs/scripts/ck_duokan.py.md)。
- `scripts/ck_everphoto.py`：上游 `OreosLab/checkinpanel` / `ck_everphoto.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_everphoto.py.md](docs/scripts/ck_everphoto.py.md)。
- `scripts/ck_fmapp.py`：上游 `OreosLab/checkinpanel` / `ck_fmapp.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_fmapp.py.md](docs/scripts/ck_fmapp.py.md)。
- `scripts/ck_freenom.py`：上游 `OreosLab/checkinpanel` / `ck_freenom.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_freenom.py.md](docs/scripts/ck_freenom.py.md)。
- `scripts/ck_game163.py`：上游 `OreosLab/checkinpanel` / `ck_game163.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。 详见 [ck_game163.py.md](docs/scripts/ck_game163.py.md)。
- `scripts/ck_meizu.py`：上游 `yuxian158/check` / `dailycheckin_scripts/ck_meizu.py` / `723c834f121ff4eef2dec7afe521071a7efff1a9`。 详见 [ck_meizu.py.md](docs/scripts/ck_meizu.py.md)。
- `scripts/ck_mgtv.py`：上游 `yuxian158/check` / `dailycheckin_scripts/ck_mgtv.py` / `723c834f121ff4eef2dec7afe521071a7efff1a9`。 详见 [ck_mgtv.py.md](docs/scripts/ck_mgtv.py.md)。
- `scripts/ck_mimotion.py`：上游 `yuxian158/check` / `dailycheckin_scripts/ck_mimotion.py` / `723c834f121ff4eef2dec7afe521071a7efff1a9`。 详见 [ck_mimotion.py.md](docs/scripts/ck_mimotion.py.md)。
- `scripts/ck_oneplusbbs.py`：上游 `yuxian158/check` / `dailycheckin_scripts/ck_oneplusBBS.py` / `723c834f121ff4eef2dec7afe521071a7efff1a9`。 详见 [ck_oneplusbbs.py.md](docs/scripts/ck_oneplusbbs.py.md)。
- `scripts/codearts_daily.py`：上游 `L0NE-6/CodeArts-Daily` / `codearts_daily.py` / `c337a9340877cdf7afef0a679f3d020d28183140`。 详见 [codearts_daily.py.md](docs/scripts/codearts_daily.py.md)。
- `scripts/comicai_ai_cookie.py`：上游 `CSDN2024/QianDaoMZH` / `comicai-ai-cookie.py` / `b99c67e46d1e74d2fd3a0bff7cac3f83e5ee6903`。 详见 [comicai_ai_cookie.py.md](docs/scripts/comicai_ai_cookie.py.md)。
- `scripts/crealitycloud_checkin.py`：上游 `xz0609/crealitycloud-checkin-ql` / `crealitycloud_checkin.py` / `ba2872b75372f62157b1f0cdcdf57ed59f9bd1fb`。 详见 [crealitycloud_checkin.py.md](docs/scripts/crealitycloud_checkin.py.md)。
- `scripts/dachao.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/dachao/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [dachao.py.md](docs/scripts/dachao.py.md)。
- `scripts/dahai.js`：上游 `unitaryhighs/ql_sign_script` / `sign/dahai.js` / `caa96862c9a31521347217b3b20b8ba3f6413c18`。 详见 [dahai.js.md](docs/scripts/dahai.js.md)。
- `scripts/daily_benefits.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/wps/daily_benefits.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [daily_benefits.py.md](docs/scripts/daily_benefits.py.md)。
- `scripts/dailynewscn.js`：上游 `unitaryhighs/ql_sign_script` / `hot/dailynewscn.js` / `caa96862c9a31521347217b3b20b8ba3f6413c18`。 详见 [dailynewscn.js.md](docs/scripts/dailynewscn.js.md)。
- `scripts/ddnsto.py`：上游 `cloudcranes/some_scripts` / `ddnsto.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [ddnsto.py.md](docs/scripts/ddnsto.py.md)。
- `scripts/deepflood_checkin.py`：上游 `agluo/ql-script-hub` / `deepflood_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [deepflood_checkin.py.md](docs/scripts/deepflood_checkin.py.md)。
- `scripts/durex.py`：上游 `Rookie-wb-WH/ql_scripts` / `durex.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [durex.py.md](docs/scripts/durex.py.md)。
- `scripts/enshan_checkin.py`：上游 `agluo/ql-script-hub` / `enshan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [enshan_checkin.py.md](docs/scripts/enshan_checkin.py.md)。
- `scripts/epicfreegames.py`：上游 `CN-Grace/QinglongScripts` / `EpicFreeGames.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [epicfreegames.py.md](docs/scripts/epicfreegames.py.md)。
- `scripts/erke.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/erke/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [erke.py.md](docs/scripts/erke.py.md)。
- `scripts/f1owkang_qingskyland_skyland.py`：上游 `f1owkang/QingSkyland` / `skyland.py` / `563c86c9d5965b5fc622e1cb33963346b661f26c`。 详见 [f1owkang_qingskyland_skyland.py.md](docs/scripts/f1owkang_qingskyland_skyland.py.md)。
- `scripts/fnnasclub.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/fnnasclub/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [fnnasclub.py.md](docs/scripts/fnnasclub.py.md)。
- `scripts/forum_download.py`：上游 `nuthx/auto-sign` / `src/general/forum_download.py` / `a8d2c229bac693daebe1535bca4cfd49733b632d`。 详见 [forum_download.py.md](docs/scripts/forum_download.py.md)。
- `scripts/fwxs_checkin.js`：上游 `zhui-zi/fwcheckin` / `fwxs_checkin.js` / `7793a795d603df34f0ebdbc7d6810427f84f59c6`。 详见 [fwxs_checkin.js.md](docs/scripts/fwxs_checkin.js.md)。
- `scripts/fxh.js`：上游 `xingly-cn/QLPanelScript` / `fxh.js` / `8c0323999253b7a0d8e47ff1136a562fedb3c980`。 详见 [fxh.js.md](docs/scripts/fxh.js.md)。
- `scripts/get_yys_cgvideo.py`：上游 `qluser-alan/some_scripts` / `阴阳师/get_yys_cgvideo.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [get_yys_cgvideo.py.md](docs/scripts/get_yys_cgvideo.py.md)。
- `scripts/get_yys_imagelinks.py`：上游 `cloudcranes/some_scripts` / `阴阳师/get_yys_imagelinks.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [get_yys_imagelinks.py.md](docs/scripts/get_yys_imagelinks.py.md)。
- `scripts/hellogithub.py`：上游 `CN-Grace/QinglongScripts` / `HelloGithub.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [hellogithub.py.md](docs/scripts/hellogithub.py.md)。
- `scripts/hifiti_checkin.py`：上游 `agluo/ql-script-hub` / `HiFiti_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [hifiti_checkin.py.md](docs/scripts/hifiti_checkin.py.md)。
- `scripts/hlyl.py`：上游 `cloudcranes/some_scripts` / `hlyl.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [hlyl.py.md](docs/scripts/hlyl.py.md)。
- `scripts/hsay.py`：上游 `Rookie-wb-WH/ql_scripts` / `hsay.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [hsay.py.md](docs/scripts/hsay.py.md)。
- `scripts/huaruntong_wx.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/huaruntong_wx/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [huaruntong_wx.py.md](docs/scripts/huaruntong_wx.py.md)。
- `scripts/hykb_gamesign.js`：上游 `qidouhai/checkbox` / `scripts/hykb_gamesign.js` / `048a5d58b54a90489e6508ae1f90525d6b21b8b1`。 详见 [hykb_gamesign.js.md](docs/scripts/hykb_gamesign.js.md)。
- `scripts/ikuuu_checkin.py`：上游 `agluo/ql-script-hub` / `ikuuu_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [ikuuu_checkin.py.md](docs/scripts/ikuuu_checkin.py.md)。
- `scripts/imaotai.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/imaotai/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [imaotai.py.md](docs/scripts/imaotai.py.md)。
- `scripts/index.js`：上游 `cloudcranes/some_scripts` / `Download_pixiv/index.js` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [index.js.md](docs/scripts/index.js.md)。
- `scripts/iqiyi_checkin.py`：上游 `deeplee/personal-scripts` / `iqiyi_checkin.py` / `c8c7c0f4fd1802df86c32a86c26b5c26cfef5023`。 详见 [iqiyi_checkin.py.md](docs/scripts/iqiyi_checkin.py.md)。
- `scripts/jc_checkin.py`：上游 `kerncoola/JC_CheckIn` / `JC_CheckIn.py` / `71362b20abdad2711ddc2e4321ef33b3ebcc64c5`。 详见 [jc_checkin.py.md](docs/scripts/jc_checkin.py.md)。
- `scripts/jcqd.py`：上游 `Rookie-wb-WH/ql_scripts` / `jcqd.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [jcqd.py.md](docs/scripts/jcqd.py.md)。
- `scripts/jingyiluntan_sign.py`：上游 `CSDN2024/QianDaoMZH` / `JingYiLunTan-sign.py` / `b99c67e46d1e74d2fd3a0bff7cac3f83e5ee6903`。 详见 [jingyiluntan_sign.py.md](docs/scripts/jingyiluntan_sign.py.md)。
- `scripts/jissbon.py`：上游 `Rookie-wb-WH/ql_scripts` / `jissbon.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [jissbon.py.md](docs/scripts/jissbon.py.md)。
- `scripts/jyj.py`：上游 `Rookie-wb-WH/ql_scripts` / `jingyoujia/jyj.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [jyj.py.md](docs/scripts/jyj.py.md)。
- `scripts/kanxue.js`：上游 `unitaryhighs/ql_sign_script` / `sign/kanxue.js` / `caa96862c9a31521347217b3b20b8ba3f6413c18`。 详见 [kanxue.js.md](docs/scripts/kanxue.js.md)。
- `scripts/kgqq.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/kgqq/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [kgqq.py.md](docs/scripts/kgqq.py.md)。
- `scripts/kjwj.py`：上游 `cloudcranes/some_scripts` / `kjwj.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [kjwj.py.md](docs/scripts/kjwj.py.md)。
- `scripts/kuaishou_reward_status.py`：洁净室独立实现 `candidates/ks_cleanroom_v1/kuaishou_reward_status.py`；行为规格 `specs/kuaishou-reward-status.md`；隔离证据 `reviews/clean-room/kuaishou-reward-status.md`。 详见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/kuku_daily.py`：上游 `L0NE-6/KukuAI-Daily` / `kuku_daily.py` / `6912419c6b29365bb7b3172cc3c18bf7b763812d`。 详见 [kuku_daily.py.md](docs/scripts/kuku_daily.py.md)。
- `scripts/kurobbs_sign.py`：上游 `yongyeym/AutoSign_QingLong` / `kurobbs_sign.py` / `f13a88e488c2d396e24cce8e9b6e27eefcbccad6`。 详见 [kurobbs_sign.py.md](docs/scripts/kurobbs_sign.py.md)。
- `scripts/l.py`：上游 `lzylipu/l-checkin` / `main.py` / `2c71083614d6ef87c8b502e1440fec3b08ab59c3`。 详见 [l.py.md](docs/scripts/l.py.md)。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`：上游 `agluo/ql-script-hub` / `archive/leaflow_checkin.pyleaflow_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [leaflow_checkin_pyleaflow_checkin.py.md](docs/scripts/leaflow_checkin_pyleaflow_checkin.py.md)。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`：上游 `LittleWuh/qinglongbox` / `dailycheckin_scripts/ck_2nzz.py` / `02e1c7a0788a62a7434f686118506ca5702fba24`。 详见 [littlewuh_qinglongbox_dailycheckin_scripts.py.md](docs/scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md)。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`：上游 `lizhixu/ql-script-hub` / `nodeseek_checkin.py` / `ac591a320092dcaeaf236b7c2b6acfd28981e589`。 详见 [lizhixu_ql_script_hub_nodeseek.py.md](docs/scripts/lizhixu_ql_script_hub_nodeseek.py.md)。
- `scripts/lizhixu_ql_script_hub_youdao.py`：上游 `lizhixu/ql-script-hub` / `youdao.py` / `ac591a320092dcaeaf236b7c2b6acfd28981e589`。 详见 [lizhixu_ql_script_hub_youdao.py.md](docs/scripts/lizhixu_ql_script_hub_youdao.py.md)。
- `scripts/lobsterai_checkin.py`：上游 `L0NE-6/LobsterAI-AutoCheckin` / `lobsterai_checkin.py` / `4e4c291a2f616ef865e18a1c8026939754bfc712`。 详见 [lobsterai_checkin.py.md](docs/scripts/lobsterai_checkin.py.md)。
- `scripts/loomy_daily.py`：上游 `L0NE-6/Loomy-Daily` / `loomy_daily.py` / `3d0f19b0b6486ff9096507805a5f9d061604058f`。 详见 [loomy_daily.py.md](docs/scripts/loomy_daily.py.md)。
- `scripts/lynkco_qinglong_single.py`：上游 `zhaosongbing/LynkCoHelper-QingLong` / `qinglong/lynkco_qinglong_single.py` / `7b9330aeae5e458f00de92b46bbd31bbf99c95aa`。 详见 [lynkco_qinglong_single.py.md](docs/scripts/lynkco_qinglong_single.py.md)。
- `scripts/main.py`：上游 `cloudcranes/some_scripts` / `Download_wallhaven/main.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [main.py.md](docs/scripts/main.py.md)。
- `scripts/mifan_optimized.py`：上游 `eggv/MeeFan-DailyCheckIn` / `mifan_optimized.py` / `dd3668c8b870fe172ac97bcf96055ddcfceb6d49`。 详见 [mifan_optimized.py.md](docs/scripts/mifan_optimized.py.md)。
- `scripts/mimotion.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/mimotion/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [mimotion.py.md](docs/scripts/mimotion.py.md)。
- `scripts/netease_task.py`：上游 `Han-cy77/Qinglong_auto` / `netease_task.py` / `4bac7c4f709db60a648c4bd498e99f9c7e66b63b`。 详见 [netease_task.py.md](docs/scripts/netease_task.py.md)。
- `scripts/nga_checkin.py`：上游 `agluo/ql-script-hub` / `nga_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [nga_checkin.py.md](docs/scripts/nga_checkin.py.md)。
- `scripts/nodeseek.py`：上游 `CN-Grace/QinglongScripts` / `Nodeseek.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [nodeseek.py.md](docs/scripts/nodeseek.py.md)。
- `scripts/nodeseek_checkin.py`：上游 `agluo/ql-script-hub` / `nodeseek_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [nodeseek_checkin.py.md](docs/scripts/nodeseek_checkin.py.md)。
- `scripts/nte.py`：上游 `Candy-QAQ/NTE-Auto-Sign` / `nte.py` / `38d77e1f7dc784f2baeb49c41cd4352deadf2b24`。 详见 [nte.py.md](docs/scripts/nte.py.md)。
- `scripts/officeace_daily.py`：上游 `L0NE-6/OfficeAce-Daily` / `officeace_daily.py` / `a6759a929b20a64fa44914f5115a1d3fc230ce54`。 详见 [officeace_daily.py.md](docs/scripts/officeace_daily.py.md)。
- `scripts/ole.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/ole/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [ole.py.md](docs/scripts/ole.py.md)。
- `scripts/passnat_checkin.py`：上游 `agluo/ql-script-hub` / `passnat_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [passnat_checkin.py.md](docs/scripts/passnat_checkin.py.md)。
- `scripts/psnine.py`：上游 `nuthx/auto-sign` / `src/special/psnine.py` / `a8d2c229bac693daebe1535bca4cfd49733b632d`。 详见 [psnine.py.md](docs/scripts/psnine.py.md)。
- `scripts/pt_sign_v5.js`：上游 `Flyingpen/PT-sign` / `PT-sign-V5.js` / `5c6cf9d38020c327f9a30c3977eb7765e4d2c5c2`。 详见 [pt_sign_v5.js.md](docs/scripts/pt_sign_v5.js.md)。
- `scripts/qoder_airscript.js`：上游 `wallechfox/qoder-checkin` / `qoder-checkin-金山云文档/Qoder签到-金山文档AirScript.js` / `19ab6365c1f0759bb424a3d69e7de8dca89bf75d`。 详见 [qoder_airscript.js.md](docs/scripts/qoder_airscript.js.md)。
- `scripts/quark_signin.py`：上游 `agluo/ql-script-hub` / `quark_signin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [quark_signin.py.md](docs/scripts/quark_signin.py.md)。
- `scripts/raccoon_daily.py`：上游 `L0NE-6/Raccoon-Daily` / `raccoon_daily.py` / `4e99a3b53829faf3ae228755b0f4c32859d25425`。 详见 [raccoon_daily.py.md](docs/scripts/raccoon_daily.py.md)。
- `scripts/rainyun.py`：上游 `cloudcranes/some_scripts` / `rainyun.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [rainyun.py.md](docs/scripts/rainyun.py.md)。
- `scripts/rousi_checkin.js`：上游 `373065025/rousi-checkin` / `rousi_checkin.js` / `627ec698dc9d35f69f44e479366a7c31dd46489c`。 详见 [rousi_checkin.js.md](docs/scripts/rousi_checkin.js.md)。
- `scripts/sf.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/sf/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [sf.py.md](docs/scripts/sf.py.md)。
- `scripts/sfsu_checkin.py`：上游 `agluo/ql-script-hub` / `SFSU_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [sfsu_checkin.py.md](docs/scripts/sfsu_checkin.py.md)。
- `scripts/sgs.py`：上游 `Rookie-wb-WH/ql_scripts` / `sgs.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [sgs.py.md](docs/scripts/sgs.py.md)。
- `scripts/shuyi.py`：上游 `Rookie-wb-WH/ql_scripts` / `shuyi.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [shuyi.py.md](docs/scripts/shuyi.py.md)。
- `scripts/sign_in.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/kanxue/sign_in.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [sign_in.py.md](docs/scripts/sign_in.py.md)。
- `scripts/skland_daily.py`：上游 `siwuli/skland-daily` / `skland_daily.py` / `c6159b4ca574b4493ae8b94e56a861c7e9e06955`。 详见 [skland_daily.py.md](docs/scripts/skland_daily.py.md)。
- `scripts/skland_demo.py`：上游 `nuthx/auto-sign` / `skland/skland-demo.py` / `a8d2c229bac693daebe1535bca4cfd49733b632d`。 详见 [skland_demo.py.md](docs/scripts/skland_demo.py.md)。
- `scripts/skyland.py`：上游 `CN-Grace/QinglongScripts` / `skyland.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [skyland.py.md](docs/scripts/skyland.py.md)。
- `scripts/smzdm_checkin.js`：上游 `ump45nose/smzdm-checkin-ql` / `checkin.js` / `6b9eaced964c348efb46d2c13a45ab5c66caaea8`。 详见 [smzdm_checkin.js.md](docs/scripts/smzdm_checkin.js.md)。
- `scripts/ssl_cert_check.py`：上游 `CN-Grace/QinglongScripts` / `SSL.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [ssl_cert_check.py.md](docs/scripts/ssl_cert_check.py.md)。
- `scripts/sudojia_33agilestudio.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_33agilestudio.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_33agilestudio.js.md](docs/scripts/sudojia_33agilestudio.js.md)。
- `scripts/sudojia_allgirls.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_allGirls.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_allgirls.js.md](docs/scripts/sudojia_allgirls.js.md)。
- `scripts/sudojia_amx.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_amx.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_amx.js.md](docs/scripts/sudojia_amx.js.md)。
- `scripts/sudojia_authcheck.js`：上游 `sudojia/AutoTaskScript` / `src/other/sudojia_authCheck.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_authcheck.js.md](docs/scripts/sudojia_authcheck.js.md)。
- `scripts/sudojia_bananavideo.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_bananaVideo.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_bananavideo.js.md](docs/scripts/sudojia_bananavideo.js.md)。
- `scripts/sudojia_beiyinmei.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_beiyinmei.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_beiyinmei.js.md](docs/scripts/sudojia_beiyinmei.js.md)。
- `scripts/sudojia_botanystar.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_botanyStar.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_botanystar.js.md](docs/scripts/sudojia_botanystar.js.md)。
- `scripts/sudojia_bwtea.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_bwtea.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_bwtea.js.md](docs/scripts/sudojia_bwtea.js.md)。
- `scripts/sudojia_colorful_mall.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_colorful_mall.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_colorful_mall.js.md](docs/scripts/sudojia_colorful_mall.js.md)。
- `scripts/sudojia_flyant.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_flyant.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_flyant.js.md](docs/scripts/sudojia_flyant.js.md)。
- `scripts/sudojia_fnnas.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_fnnas.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_fnnas.js.md](docs/scripts/sudojia_fnnas.js.md)。
- `scripts/sudojia_hgf.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_hgf.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_hgf.js.md](docs/scripts/sudojia_hgf.js.md)。
- `scripts/sudojia_hlzj_game.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_hlzj_game.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_hlzj_game.js.md](docs/scripts/sudojia_hlzj_game.js.md)。
- `scripts/sudojia_hzhfp.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_hzhfp.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_hzhfp.js.md](docs/scripts/sudojia_hzhfp.js.md)。
- `scripts/sudojia_instax.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_instax.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_instax.js.md](docs/scripts/sudojia_instax.js.md)。
- `scripts/sudojia_jhcard.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_jhcard.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_jhcard.js.md](docs/scripts/sudojia_jhcard.js.md)。
- `scripts/sudojia_jiangshan.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_jiangshan.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_jiangshan.js.md](docs/scripts/sudojia_jiangshan.js.md)。
- `scripts/sudojia_jindian.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_jindian.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_jindian.js.md](docs/scripts/sudojia_jindian.js.md)。
- `scripts/sudojia_jlc_yj.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_jlc_yj.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_jlc_yj.js.md](docs/scripts/sudojia_jlc_yj.js.md)。
- `scripts/sudojia_juejin.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_juejin.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_juejin.js.md](docs/scripts/sudojia_juejin.js.md)。
- `scripts/sudojia_kozbs.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_kozbs.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_kozbs.js.md](docs/scripts/sudojia_kozbs.js.md)。
- `scripts/sudojia_ktgzs.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_ktgzs.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_ktgzs.js.md](docs/scripts/sudojia_ktgzs.js.md)。
- `scripts/sudojia_kukahome.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_kukahome.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_kukahome.js.md](docs/scripts/sudojia_kukahome.js.md)。
- `scripts/sudojia_kuro.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_kuro.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_kuro.js.md](docs/scripts/sudojia_kuro.js.md)。
- `scripts/sudojia_laoban.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_laoban.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_laoban.js.md](docs/scripts/sudojia_laoban.js.md)。
- `scripts/sudojia_longfor.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_longfor.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_longfor.js.md](docs/scripts/sudojia_longfor.js.md)。
- `scripts/sudojia_mallcoo.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_mallcoo.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_mallcoo.js.md](docs/scripts/sudojia_mallcoo.js.md)。
- `scripts/sudojia_mawuwang.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_mawuwang.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_mawuwang.js.md](docs/scripts/sudojia_mawuwang.js.md)。
- `scripts/sudojia_midea.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_midea.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_midea.js.md](docs/scripts/sudojia_midea.js.md)。
- `scripts/sudojia_moto.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_moto.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。
- `scripts/sudojia_mxbc.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_mxbc.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_mxbc.js.md](docs/scripts/sudojia_mxbc.js.md)。
- `scripts/sudojia_naixue.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_naixue.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_naixue.js.md](docs/scripts/sudojia_naixue.js.md)。
- `scripts/sudojia_nestle.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_nestle.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_nestle.js.md](docs/scripts/sudojia_nestle.js.md)。
- `scripts/sudojia_nfhk.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_nfhk.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_nfhk.js.md](docs/scripts/sudojia_nfhk.js.md)。
- `scripts/sudojia_opposhop.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_opposhop.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_opposhop.js.md](docs/scripts/sudojia_opposhop.js.md)。
- `scripts/sudojia_pangge.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_pangGe.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_pangge.js.md](docs/scripts/sudojia_pangge.js.md)。
- `scripts/sudojia_paotea.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_paotea.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_paotea.js.md](docs/scripts/sudojia_paotea.js.md)。
- `scripts/sudojia_shmedia.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_shmedia.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_shmedia.js.md](docs/scripts/sudojia_shmedia.js.md)。
- `scripts/sudojia_shuifei.js`：上游 `sudojia/AutoTaskScript` / `src/public/sudojia_shuifei.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_shuifei.js.md](docs/scripts/sudojia_shuifei.js.md)。
- `scripts/sudojia_sspanel.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_sspanel.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_sspanel.js.md](docs/scripts/sudojia_sspanel.js.md)。
- `scripts/sudojia_starmom.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_starMom.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_starmom.js.md](docs/scripts/sudojia_starmom.js.md)。
- `scripts/sudojia_tebu.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_tebu.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_tebu.js.md](docs/scripts/sudojia_tebu.js.md)。
- `scripts/sudojia_tilta.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_tilta.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_tilta.js.md](docs/scripts/sudojia_tilta.js.md)。
- `scripts/sudojia_tuchong.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_tuchong.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_tuchong.js.md](docs/scripts/sudojia_tuchong.js.md)。
- `scripts/sudojia_v2ex.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_v2ex.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_v2ex.js.md](docs/scripts/sudojia_v2ex.js.md)。
- `scripts/sudojia_wnna.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_wnna.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_wnna.js.md](docs/scripts/sudojia_wnna.js.md)。
- `scripts/sudojia_xhn.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_xhn.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_xhn.js.md](docs/scripts/sudojia_xhn.js.md)。
- `scripts/sudojia_xiangwan.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_xiangwan.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_xiangwan.js.md](docs/scripts/sudojia_xiangwan.js.md)。
- `scripts/sudojia_xiaomi_community.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_xiaomi_community.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_xiaomi_community.js.md](docs/scripts/sudojia_xiaomi_community.js.md)。
- `scripts/sudojia_xinxi.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_xinxi.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_xinxi.js.md](docs/scripts/sudojia_xinxi.js.md)。
- `scripts/sudojia_xpfarm.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_xpfarm.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_xpfarm.js.md](docs/scripts/sudojia_xpfarm.js.md)。
- `scripts/sudojia_znds.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_znds.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_znds.js.md](docs/scripts/sudojia_znds.js.md)。
- `scripts/sudojia_zxice.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_zxice.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_zxice.js.md](docs/scripts/sudojia_zxice.js.md)。
- `scripts/supertopicsign.py`：上游 `Hellager/weibo_supertopic_sign` / `supertopicsign.py` / `66e46ec082cc87100e7d99e8ed8e6c478c5e3833`。 详见 [supertopicsign.py.md](docs/scripts/supertopicsign.py.md)。
- `scripts/synspoint.py`：上游 `Rookie-wb-WH/ql_scripts` / `synspoint.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [synspoint.py.md](docs/scripts/synspoint.py.md)。
- `scripts/task_ef2d3863.js`：上游 `yunzimo/APChinkin` / `autoSignin.js` / `017f5685f1b59a8695bbb3a0a35a80cf5f7f5e79`。 详见 [task_ef2d3863.js.md](docs/scripts/task_ef2d3863.js.md)。
- `scripts/tencent_video_checkin.py`：上游 `deeplee/personal-scripts` / `tencent_video_checkin.py` / `c8c7c0f4fd1802df86c32a86c26b5c26cfef5023`。 详见 [tencent_video_checkin.py.md](docs/scripts/tencent_video_checkin.py.md)。
- `scripts/tieba_checkin.py`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_tieba.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [tieba_checkin.py.md](docs/scripts/tieba_checkin.py.md)。
- `scripts/tjd_daily.py`：上游 `SkyBlue997/tjd-daily` / `tjd_daily.py` / `1df775d4c5eea379111edecf53a62b447b756770`。 详见 [tjd_daily.py.md](docs/scripts/tjd_daily.py.md)。
- `scripts/trae_checkin.py`：上游 `L0NE-6/Trae-AutoCheckin` / `trae_checkin.py` / `38b1d919760ed9a36dfe6873be8765f8cafaff3f`。 详见 [trae_checkin.py.md](docs/scripts/trae_checkin.py.md)。
- `scripts/tsthb_checkin.py`：上游 `agluo/ql-script-hub` / `tsthb_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [tsthb_checkin.py.md](docs/scripts/tsthb_checkin.py.md)。
- `scripts/ty_netdisk_checkin.py`：上游 `agluo/ql-script-hub` / `ty_netdisk_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。 详见 [ty_netdisk_checkin.py.md](docs/scripts/ty_netdisk_checkin.py.md)。
- `scripts/tyqhdraw.py`：上游 `Rookie-wb-WH/ql_scripts` / `tyqhDraw.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [tyqhdraw.py.md](docs/scripts/tyqhdraw.py.md)。
- `scripts/valorantstore.py`：上游 `CN-Grace/QinglongScripts` / `ValorantStore.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [valorantstore.py.md](docs/scripts/valorantstore.py.md)。
- `scripts/vortexa_free_claim.js`：上游 `lizhixu/ql-script-hub` / `vortexa_free_claim.js` / `ac591a320092dcaeaf236b7c2b6acfd28981e589`。 详见 [vortexa_free_claim.js.md](docs/scripts/vortexa_free_claim.js.md)。
- `scripts/wangchao.py`：上游 `Rookie-wb-WH/ql_scripts` / `wangchao.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [wangchao.py.md](docs/scripts/wangchao.py.md)。
- `scripts/wentiweilaihui.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/wentiweilaihui/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [wentiweilaihui.py.md](docs/scripts/wentiweilaihui.py.md)。
- `scripts/workbuddy.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/workbuddy/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。 详见 [workbuddy.py.md](docs/scripts/workbuddy.py.md)。
- `scripts/workbuddy_daily.py`：上游 `L0NE-6/WorkBuddy-Daily` / `workbuddy_daily.py` / `e030ebde37411a90e0a3e35b88993e5686c7e1dd`。 详见 [workbuddy_daily.py.md](docs/scripts/workbuddy_daily.py.md)。
- `scripts/wps_clock_in.py`：上游 `cloudcranes/some_scripts` / `invalid/wps_clock_in.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。 详见 [wps_clock_in.py.md](docs/scripts/wps_clock_in.py.md)。
- `scripts/wyycg.py`：上游 `GamerNoTitle/wyycg-autocheckin` / `main.py` / `e12f44c306948430272c54152b04a11da917b92d`。 详见 [wyycg.py.md](docs/scripts/wyycg.py.md)。
- `scripts/yht.py`：上游 `Rookie-wb-WH/ql_scripts` / `yht.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [yht.py.md](docs/scripts/yht.py.md)。
- `scripts/youdao.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/youdao/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。 详见 [youdao.py.md](docs/scripts/youdao.py.md)。
- `scripts/yyshuijuantime.py`：上游 `CN-Grace/QinglongScripts` / `YysHuijuanTime.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。 详见 [yyshuijuantime.py.md](docs/scripts/yyshuijuantime.py.md)。
- `scripts/zcode_cn_daily.py`：上游 `L0NE-6/ZCode-Daily` / `zcode_cn_daily.py` / `68e3adf4b5deb036f2a992a5aca24f02f3a64ade`。 详见 [zcode_cn_daily.py.md](docs/scripts/zcode_cn_daily.py.md)。
- `scripts/zippo.py`：上游 `Rookie-wb-WH/ql_scripts` / `zippo.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。 详见 [zippo.py.md](docs/scripts/zippo.py.md)。
- `scripts/zodgame_test.py`：上游 `miaonai/zodgame-ql` / `zodgame-test.py` / `6494977a250c71a8fcd00b48a4cf3e1249da4e4c`。 详见 [zodgame_test.py.md](docs/scripts/zodgame_test.py.md)。
