# 完整定时任务表

业务 Cron 已错峰排布。返回 [`目录首页`](README.md)。

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron | 管理状态 | 详单 |
| --- | --- | --- | --- | --- | --- |
| 依赖安装 | `scripts/install_dependencies.sh` | `task scripts/install_dependencies.sh` | `23 4 * * 1` | 维护任务 | — |
| 春风动力签到 | `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `5 0 * * *` | 上架 | [cfmoto_checkin.py.md](../scripts/cfmoto_checkin.py.md)（`docs/scripts/cfmoto_checkin.py.md`） |
| 快手奖励任务 | `scripts/kuaishou_reward_status.py` | `python3 scripts/kuaishou_reward_status.py` | `22 8,14,20 * * *` | 上架 | [kuaishou_reward_status.py.md](../scripts/kuaishou_reward_status.py.md)（`docs/scripts/kuaishou_reward_status.py.md`） |
| 摩托范每日签到 | `scripts/sudojia_moto.js` | `node scripts/sudojia_moto.js` | `26 0 * * *` | 上架 | [sudojia_moto.js.md](../scripts/sudojia_moto.js.md)（`docs/scripts/sudojia_moto.js.md`） |
| 百度贴吧签到 | `scripts/tieba_checkin.py` | `python3 scripts/tieba_checkin.py` | `39 2 * * *` | 上架 | [tieba_checkin.py.md](../scripts/tieba_checkin.py.md)（`docs/scripts/tieba_checkin.py.md`） |
| 139云盘云朵任务 | `scripts/139_yunduo.py` | `python3 scripts/139_yunduo.py` | `11 0 * * *` | 待检查 | [139_yunduo.py.md](../scripts/139_yunduo.py.md)（`docs/scripts/139_yunduo.py.md`） |
| 2cycd 论坛自动签到 | `scripts/2cycd.py` | `python3 scripts/2cycd.py` | `0 0 * * *` | 待检查 | [2cycd.py.md](../scripts/2cycd.py.md)（`docs/scripts/2cycd.py.md`） |
| 2cycdx自动签到 | `scripts/2cycdx.py` | `python3 scripts/2cycdx.py` | `45 0 * * *` | 待检查 | [2cycdx.py.md](../scripts/2cycdx.py.md)（`docs/scripts/2cycdx.py.md`） |
| 51CTO博客每日签到 | `scripts/51cto_sign.js` | `node scripts/51cto_sign.js` | `17 2 * * *` | 待检查 | [51cto_sign.js.md](../scripts/51cto_sign.js.md)（`docs/scripts/51cto_sign.js.md`） |
| 吾爱破解每日签到 | `scripts/52pojie.js` | `node scripts/52pojie.js` | `8 0 * * *` | 待检查 | [52pojie.js.md](../scripts/52pojie.js.md)（`docs/scripts/52pojie.js.md`） |
| 55188论坛签到 | `scripts/55188auto.py` | `python3 scripts/55188auto.py` | `27 8 * * *` | 待检查 | [55188auto.py.md](../scripts/55188auto.py.md)（`docs/scripts/55188auto.py.md`） |
| 69云签到 | `scripts/69yun_checkin.py` | `python3 scripts/69yun_checkin.py` | `20 0 * * *` | 待检查 | [69yun_checkin.py.md](../scripts/69yun_checkin.py.md)（`docs/scripts/69yun_checkin.py.md`） |
| 华润通999答题 | `scripts/999.py` | `python3 scripts/999.py` | `49 1 1 1 1` | 待检查 | [999.py.md](../scripts/999.py.md)（`docs/scripts/999.py.md`） |
| 爱上ASMR每日签到 | `scripts/a3asmr.js` | `node scripts/a3asmr.js` | `15 9 * * *` | 待检查 | [a3asmr.js.md](../scripts/a3asmr.js.md)（`docs/scripts/a3asmr.js.md`） |
| AcFun每日任务 | `scripts/acfun.py` | `python3 scripts/acfun.py` | `9 0 * * *` | 待检查 | [acfun.py.md](../scripts/acfun.py.md)（`docs/scripts/acfun.py.md`） |
| CordCloud 每日签到 | `scripts/action.py` | `python3 scripts/action.py` | `38 8 * * *` | 待检查 | [action.py.md](../scripts/action.py.md)（`docs/scripts/action.py.md`） |
| NewAPI 活动中心签到 | `scripts/activity_checkin.py` | `python3 scripts/activity_checkin.py` | `22 8 * * *` | 待检查 | [activity_checkin.py.md](../scripts/activity_checkin.py.md)（`docs/scripts/activity_checkin.py.md`） |
| AgentRouter签到 | `scripts/agentrouter.py` | `python3 scripts/agentrouter.py` | `17 1 * * *` | 待检查 | [agentrouter.py.md](../scripts/agentrouter.py.md)（`docs/scripts/agentrouter.py.md`） |
| 安徽工业大学晚寝签到 | `scripts/ahut.py` | `python3 scripts/ahut.py` | `20 21 * * *` | 待检查 | [ahut.py.md](../scripts/ahut.py.md)（`docs/scripts/ahut.py.md`） |
| 机场签到（速鹰666） | `scripts/airport.py` | `python3 scripts/airport.py` | `27 1 * * *` | 待检查 | [airport.py.md](../scripts/airport.py.md)（`docs/scripts/airport.py.md`） |
| 机场自动登录签到 | `scripts/aitport.js` | `node scripts/aitport.js` | `1 8 * * *` | 待检查 | [aitport.js.md](../scripts/aitport.js.md)（`docs/scripts/aitport.js.md`） |
| AkileCloud 签到与保活 | `scripts/akile_checkin.py` | `python3 scripts/akile_checkin.py` | `44 0 * * *` | 待检查 | [akile_checkin.py.md](../scripts/akile_checkin.py.md)（`docs/scripts/akile_checkin.py.md`） |
| 阿里云社区 | `scripts/aliyun_web.js` | `node scripts/aliyun_web.js` | `36 7,13 * * *` | 待检查 | [aliyun_web.js.md](../scripts/aliyun_web.js.md)（`docs/scripts/aliyun_web.js.md`） |
| 阿里云盘签到 | `scripts/aliyunpan_checkin.py` | `python3 scripts/aliyunpan_checkin.py` | `47 1 * * *` | 待检查 | [aliyunpan_checkin.py.md](../scripts/aliyunpan_checkin.py.md)（`docs/scripts/aliyunpan_checkin.py.md`） |
| AnyRouter 每日签到 | `scripts/anyrouter_signin.py` | `python3 scripts/anyrouter_signin.py` | `6 9 * * *` | 待检查 | [anyrouter_signin.py.md](../scripts/anyrouter_signin.py.md)（`docs/scripts/anyrouter_signin.py.md`） |
| 奥拉星每日任务与积分 | `scripts/aolaxing.py` | `python3 scripts/aolaxing.py` | `38 0 * * *` | 待检查 | [aolaxing.py.md](../scripts/aolaxing.py.md)（`docs/scripts/aolaxing.py.md`） |
| Hax 与 Woiden 可开通区域监控 | `scripts/api_hax.py` | `python3 scripts/api_hax.py` | `44 */6 * * *` | 待检查 | [api_hax.py.md](../scripts/api_hax.py.md)（`docs/scripts/api_hax.py.md`） |
| APICloud每日签到 | `scripts/apicloud.js` | `node scripts/apicloud.js` | `12 9 * * *` | 待检查 | [apicloud.js.md](../scripts/apicloud.js.md)（`docs/scripts/apicloud.js.md`） |
| apk.tw每日签到 | `scripts/apktw.py` | `python3 scripts/apktw.py` | `19 9 * * *` | 待检查 | [apktw.py.md](../scripts/apktw.py.md)（`docs/scripts/apktw.py.md`） |
| Arctime每日签到 | `scripts/arctime_auto_sign.py` | `python3 scripts/arctime_auto_sign.py` | `56 8 * * *` | 待检查 | [arctime_auto_sign.py.md](../scripts/arctime_auto_sign.py.md)（`docs/scripts/arctime_auto_sign.py.md`） |
| 明日方舟寻访公告 | `scripts/arknightsbanner.py` | `python3 scripts/arknightsbanner.py` | `29 1 * * *` | 待检查 | [arknightsbanner.py.md](../scripts/arknightsbanner.py.md)（`docs/scripts/arknightsbanner.py.md`） |
| AStudio 每日登录积分观测 | `scripts/astudio_daily.py` | `python3 scripts/astudio_daily.py` | `17 9 * * *` | 待检查 | [astudio_daily.py.md](../scripts/astudio_daily.py.md)（`docs/scripts/astudio_daily.py.md`） |
| 艾特校园圈 | `scripts/atxyq.py` | `python3 scripts/atxyq.py` | `21 10,23 * * *` | 待检查 | [atxyq.py.md](../scripts/atxyq.py.md)（`docs/scripts/atxyq.py.md`） |
| 上海杨浦商城定时抢购 | `scripts/auto_buy.py` | `python3 scripts/auto_buy.py` | `0 0 10 * * *` | 待检查 | [auto_buy.py.md](../scripts/auto_buy.py.md)（`docs/scripts/auto_buy.py.md`） |
| 厦门大学畅课自动签到 | `scripts/auto_checkin.py` | `python3 scripts/auto_checkin.py` | `*/2 8-18 * * 1-5` | 待检查 | [auto_checkin.py.md](../scripts/auto_checkin.py.md)（`docs/scripts/auto_checkin.py.md`） |
| 天使动漫签到打工 | `scripts/auto_sign.py` | `python3 scripts/auto_sign.py` | `31 9 * * *` | 待检查 | [auto_sign.py.md](../scripts/auto_sign.py.md)（`docs/scripts/auto_sign.py.md`） |
| SakuraFRP每日签到 | `scripts/auto_signin_http.py` | `python3 scripts/auto_signin_http.py` | `7 9 * * *` | 待检查 | [auto_signin_http.py.md](../scripts/auto_signin_http.py.md)（`docs/scripts/auto_signin_http.py.md`） |
| AutoClaw 国内版每日签到 | `scripts/autoclaw_cn_daily.py` | `python3 scripts/autoclaw_cn_daily.py` | `15 8 * * *` | 待检查 | [autoclaw_cn_daily.py.md](../scripts/autoclaw_cn_daily.py.md)（`docs/scripts/autoclaw_cn_daily.py.md`） |
| E-Hentai 自动签到 | `scripts/autosignin.py` | `python3 scripts/autosignin.py` | `18 */6 * * *` | 待检查 | [autosignin.py.md](../scripts/autosignin.py.md)（`docs/scripts/autosignin.py.md`） |
| 广州信息技术职校微信签到 | `scripts/autosignin_base.py` | `python3 scripts/autosignin_base.py` | `30 7 * * *` | 待检查 | [autosignin_base.py.md](../scripts/autosignin_base.py.md)（`docs/scripts/autosignin_base.py.md`） |
| 薄荷公益站每日签到 | `scripts/background.js` | `node scripts/background.js` | `4 8 * * *` | 待检查 | [background.js.md](../scripts/background.js.md)（`docs/scripts/background.js.md`） |
| 百度站点提交 | `scripts/baidu.py` | `python3 scripts/baidu.py` | `36 2 * * *` | 待检查 | [baidu.py.md](../scripts/baidu.py.md)（`docs/scripts/baidu.py.md`） |
| 百度网盘签到 | `scripts/baiduwangpan_checkin.py` | `python3 scripts/baiduwangpan_checkin.py` | `27 2 * * *` | 待检查 | [baiduwangpan_checkin.py.md](../scripts/baiduwangpan_checkin.py.md)（`docs/scripts/baiduwangpan_checkin.py.md`） |
| Bailanjo 自动签到 | `scripts/bailanjo_checkin.py` | `python3 scripts/bailanjo_checkin.py` | `31 2 * * *` | 待检查 | [bailanjo_checkin.py.md](../scripts/bailanjo_checkin.py.md)（`docs/scripts/bailanjo_checkin.py.md`） |
| AcFun Cookie每日任务 | `scripts/beacherz_dailycheckin_plus_acfun.py` | `python3 scripts/beacherz_dailycheckin_plus_acfun.py` | `21 0 * * *` | 待检查 | [beacherz_dailycheckin_plus_acfun.py.md](../scripts/beacherz_dailycheckin_plus_acfun.py.md)（`docs/scripts/beacherz_dailycheckin_plus_acfun.py.md`） |
| B站每日任务 | `scripts/bilibili.py` | `python3 scripts/bilibili.py` | `6 2 * * *` | 待检查 | [bilibili.py.md](../scripts/bilibili.py.md)（`docs/scripts/bilibili.py.md`） |
| Holmes AI 每日签到 | `scripts/bot.py` | `python3 scripts/bot.py` | `14 8 * * *` | 待检查 | [bot.py.md](../scripts/bot.py.md)（`docs/scripts/bot.py.md`） |
| 百事乐元抽奖 | `scripts/bsly_draw.py` | `python3 scripts/bsly_draw.py` | `23 0 * * *` | 待检查 | [bsly_draw.py.md](../scripts/bsly_draw.py.md)（`docs/scripts/bsly_draw.py.md`） |
| BT吧签到 | `scripts/btbar.py` | `python3 scripts/btbar.py` | `46 8 * * *` | 待检查 | [btbar.py.md](../scripts/btbar.py.md)（`docs/scripts/btbar.py.md`） |
| 布谷TV每日签到 | `scripts/bugutv.py` | `python3 scripts/bugutv.py` | `12 1 * * *` | 待检查 | [bugutv.py.md](../scripts/bugutv.py.md)（`docs/scripts/bugutv.py.md`） |
| 霸王茶姬签到 | `scripts/bwcj.py` | `python3 scripts/bwcj.py` | `31 9,18 * * *` | 待检查 | [bwcj.py.md](../scripts/bwcj.py.md)（`docs/scripts/bwcj.py.md`） |
| 菜玩社区每日签到 | `scripts/caigamer.js` | `node scripts/caigamer.js` | `0 20 11 * * *` | 待检查 | [caigamer.js.md](../scripts/caigamer.js.md)（`docs/scripts/caigamer.js.md`） |
| 成都地铁签到 | `scripts/cdrail.py` | `python3 scripts/cdrail.py` | `3 1 * * *` | 待检查 | [cdrail.py.md](../scripts/cdrail.py.md)（`docs/scripts/cdrail.py.md`） |
| 超星学习通巡课签到 | `scripts/chaoxing_assistant.js` | `node scripts/chaoxing_assistant.js` | `*/10 7-22 * * *` | 待检查 | [chaoxing_assistant.js.md](../scripts/chaoxing_assistant.js.md)（`docs/scripts/chaoxing_assistant.js.md`） |
| 智谱清言每日签到 | `scripts/chatglm_daily.py` | `python3 scripts/chatglm_daily.py` | `23 1 * * *` | 待检查 | [chatglm_daily.py.md](../scripts/chatglm_daily.py.md)（`docs/scripts/chatglm_daily.py.md`） |
| VManAPI 每日签到 | `scripts/check_in.py` | `python3 scripts/check_in.py` | `23 8 * * *` | 待检查 | [check_in.py.md](../scripts/check_in.py.md)（`docs/scripts/check_in.py.md`） |
| LaTeX工作室签到 | `scripts/checkin_latex.py` | `python3 scripts/checkin_latex.py` | `10 1 * * *` | 待检查 | [checkin_latex.py.md](../scripts/checkin_latex.py.md)（`docs/scripts/checkin_latex.py.md`） |
| 雪佛兰APP签到 | `scripts/chevrolet.js` | `node scripts/chevrolet.js` | `55 0 * * *` | 待检查 | [chevrolet.js.md](../scripts/chevrolet.js.md)（`docs/scripts/chevrolet.js.md`） |
| 词霸每日一句 | `scripts/ciba.js` | `node scripts/ciba.js` | `0 25 11 * * *` | 待检查 | [ciba.js.md](../scripts/ciba.js.md)（`docs/scripts/ciba.js.md`） |
| 机场签到 | `scripts/ck_airport.py` | `python3 scripts/ck_airport.py` | `16 2 * * *` | 待检查 | [ck_airport.py.md](../scripts/ck_airport.py.md)（`docs/scripts/ck_airport.py.md`） |
| 爱企查每日任务 | `scripts/ck_aqc.js` | `node scripts/ck_aqc.js` | `9 0-23/8 * * *` | 待检查 | [ck_aqc.js.md](../scripts/ck_aqc.js.md)（`docs/scripts/ck_aqc.js.md`） |
| 百度站点提交 | `scripts/ck_baidu.py` | `python3 scripts/ck_baidu.py` | `6 0 * * *` | 待检查 | [ck_baidu.py.md](../scripts/ck_baidu.py.md)（`docs/scripts/ck_baidu.py.md`） |
| 百度搜索资源平台 | `scripts/ck_baidu_url_submit.py` | `python3 scripts/ck_baidu_url_submit.py` | `8 2 * * *` | 待检查 | [ck_baidu_url_submit.py.md](../scripts/ck_baidu_url_submit.py.md)（`docs/scripts/ck_baidu_url_submit.py.md`） |
| CCAVA每日签到 | `scripts/ck_ccava.py` | `python3 scripts/ck_ccava.py` | `31 1 * * *` | 待检查 | [ck_ccava.py.md](../scripts/ck_ccava.py.md)（`docs/scripts/ck_ccava.py.md`） |
| CSDN签到与可选抽奖 | `scripts/ck_csdn.py` | `python3 scripts/ck_csdn.py` | `38 1 * * *` | 待检查 | [ck_csdn.py.md](../scripts/ck_csdn.py.md)（`docs/scripts/ck_csdn.py.md`） |
| 网易蜗牛读书 | `scripts/ck_du163.js` | `node scripts/ck_du163.js` | `42 2 * * *` | 待检查 | [ck_du163.js.md](../scripts/ck_du163.js.md)（`docs/scripts/ck_du163.js.md`） |
| EUserv 自动续期 | `scripts/ck_euserv.py` | `python3 scripts/ck_euserv.py` | `56 10 */7 * *` | 待检查 | [ck_euserv.py.md](../scripts/ck_euserv.py.md)（`docs/scripts/ck_euserv.py.md`） |
| 时光相册每日签到 | `scripts/ck_everphoto.py` | `python3 scripts/ck_everphoto.py` | `3 0 * * *` | 待检查 | [ck_everphoto.py.md](../scripts/ck_everphoto.py.md)（`docs/scripts/ck_everphoto.py.md`） |
| Fa米家每日签到与发米粒查询 | `scripts/ck_fmapp.py` | `python3 scripts/ck_fmapp.py` | `57 1 * * *` | 待检查 | [ck_fmapp.py.md](../scripts/ck_fmapp.py.md)（`docs/scripts/ck_fmapp.py.md`） |
| FreeNom 域名续期维护 | `scripts/ck_freenom.py` | `python3 scripts/ck_freenom.py` | `30 7 */10 * *` | 待检查 | [ck_freenom.py.md](../scripts/ck_freenom.py.md)（`docs/scripts/ck_freenom.py.md`） |
| 全民K歌每日任务 | `scripts/ck_kgqq.py` | `python3 scripts/ck_kgqq.py` | `35 2 * * *` | 待检查 | [ck_kgqq.py.md](../scripts/ck_kgqq.py.md)（`docs/scripts/ck_kgqq.py.md`） |
| 魅族社区签到 | `scripts/ck_meizu.py` | `python3 scripts/ck_meizu.py` | `30 1 * * *` | 待检查 | [ck_meizu.py.md](../scripts/ck_meizu.py.md)（`docs/scripts/ck_meizu.py.md`） |
| 芒果TV每日签到 | `scripts/ck_mgtv.py` | `python3 scripts/ck_mgtv.py` | `36 0 * * *` | 待检查 | [ck_mgtv.py.md](../scripts/ck_mgtv.py.md)（`docs/scripts/ck_mgtv.py.md`） |
| 小米运动 | `scripts/ck_mimotion.py` | `python3 scripts/ck_mimotion.py` | `1 0 * * *` | 待检查 | [ck_mimotion.py.md](../scripts/ck_mimotion.py.md)（`docs/scripts/ck_mimotion.py.md`） |
| 一加手机社区官方论坛 | `scripts/ck_oneplusbbs.py` | `python3 scripts/ck_oneplusbbs.py` | `40 2 * * *` | 待检查 | [ck_oneplusbbs.py.md](../scripts/ck_oneplusbbs.py.md)（`docs/scripts/ck_oneplusbbs.py.md`） |
| 中山大学人脸签到 | `scripts/cli.py` | `python3 scripts/cli.py` | `*/5 7-22 * * *` | 待检查 | [cli.py.md](../scripts/cli.py.md)（`docs/scripts/cli.py.md`） |
| 云原神每日签到 | `scripts/cloud_genshin.py` | `python3 scripts/cloud_genshin.py` | `30 9 * * *` | 待检查 | [cloud_genshin.py.md](../scripts/cloud_genshin.py.md)（`docs/scripts/cloud_genshin.py.md`） |
| CodeArts 每日福利领取 | `scripts/codearts_daily.py` | `python3 scripts/codearts_daily.py` | `16 8 * * *` | 待检查 | [codearts_daily.py.md](../scripts/codearts_daily.py.md)（`docs/scripts/codearts_daily.py.md`） |
| ComicAI 每日签到 | `scripts/comicai_ai_cookie.py` | `python3 scripts/comicai_ai_cookie.py` | `46 1 * * *` | 待检查 | [comicai_ai_cookie.py.md](../scripts/comicai_ai_cookie.py.md)（`docs/scripts/comicai_ai_cookie.py.md`） |
| 创想云国内站签到 | `scripts/crealitycloud_checkin.py` | `python3 scripts/crealitycloud_checkin.py` | `44 2 * * *` | 待检查 | [crealitycloud_checkin.py.md](../scripts/crealitycloud_checkin.py.md)（`docs/scripts/crealitycloud_checkin.py.md`） |
| 大潮App签到阅读 | `scripts/dachao.py` | `python3 scripts/dachao.py` | `22 10,14,18 * * *` | 待检查 | [dachao.py.md](../scripts/dachao.py.md)（`docs/scripts/dachao.py.md`） |
| 大海资源站每日签到 | `scripts/dahai.js` | `node scripts/dahai.js` | `0 30 11 * * *` | 待检查 | [dahai.js.md](../scripts/dahai.js.md)（`docs/scripts/dahai.js.md`） |
| WPS天天领福利（可选任务中心） | `scripts/daily_benefits.py` | `python3 scripts/daily_benefits.py` | `47 1 1 1 1` | 待检查 | [daily_benefits.py.md](../scripts/daily_benefits.py.md)（`docs/scripts/daily_benefits.py.md`） |
| PSY 每日签到 | `scripts/daily_checkin.py` | `python3 scripts/daily_checkin.py` | `21 8 * * *` | 待检查 | [daily_checkin.py.md](../scripts/daily_checkin.py.md)（`docs/scripts/daily_checkin.py.md`） |
| 京东每日签到领京豆 | `scripts/daily_sign.py` | `python3 scripts/daily_sign.py` | `40 8 * * *` | 待检查 | [daily_sign.py.md](../scripts/daily_sign.py.md)（`docs/scripts/daily_sign.py.md`） |
| 二重螺旋皎皎角每日任务 | `scripts/daily_tasks.py` | `python3 scripts/daily_tasks.py` | `3 8 * * *` | 待检查 | [daily_tasks.py.md](../scripts/daily_tasks.py.md)（`docs/scripts/daily_tasks.py.md`） |
| 今日校园信息收集 | `scripts/dailycp.py` | `python3 scripts/dailycp.py` | `57 8 * * *` | 待检查 | [dailycp.py.md](../scripts/dailycp.py.md)（`docs/scripts/dailycp.py.md`） |
| 中国日报 | `scripts/dailynewscn.js` | `node scripts/dailynewscn.js` | `0 15 9 * * *` | 待检查 | [dailynewscn.js.md](../scripts/dailynewscn.js.md)（`docs/scripts/dailynewscn.js.md`） |
| 大物是也签到 | `scripts/dawushiye.py` | `python3 scripts/dawushiye.py` | `7 8 * * *` | 待检查 | [dawushiye.py.md](../scripts/dawushiye.py.md)（`docs/scripts/dawushiye.py.md`） |
| PHPWind论坛每日任务 | `scripts/day.py` | `python3 scripts/day.py` | `58 8 * * *` | 待检查 | [day.py.md](../scripts/day.py.md)（`docs/scripts/day.py.md`） |
| DDNSTO七天免费续费 | `scripts/ddnsto.py` | `python3 scripts/ddnsto.py` | `32 2 * * *` | 待检查 | [ddnsto.py.md](../scripts/ddnsto.py.md)（`docs/scripts/ddnsto.py.md`） |
| DeepFlood 签到 | `scripts/deepflood_checkin.py` | `python3 scripts/deepflood_checkin.py` | `0 0 * * *` | 待检查 | [deepflood_checkin.py.md](../scripts/deepflood_checkin.py.md)（`docs/scripts/deepflood_checkin.py.md`） |
| 豆包天天领额度签到 | `scripts/doubao_daily.py` | `python3 scripts/doubao_daily.py` | `23 9 * * *` | 待检查 | [doubao_daily.py.md](../scripts/doubao_daily.py.md)（`docs/scripts/doubao_daily.py.md`） |
| Doyoudo每日签到发言 | `scripts/doyoudo_auto_sign.py` | `python3 scripts/doyoudo_auto_sign.py` | `59 8 * * *` | 待检查 | [doyoudo_auto_sign.py.md](../scripts/doyoudo_auto_sign.py.md)（`docs/scripts/doyoudo_auto_sign.py.md`） |
| 杜蕾斯会员中心 | `scripts/durex.py` | `python3 scripts/durex.py` | `52 0 * * *` | 待检查 | [durex.py.md](../scripts/durex.py.md)（`docs/scripts/durex.py.md`） |
| 神经研究所每日任务 | `scripts/easonfans_daily.py` | `python3 scripts/easonfans_daily.py` | `0 20 * * *` | 待检查 | [easonfans_daily.py.md](../scripts/easonfans_daily.py.md)（`docs/scripts/easonfans_daily.py.md`） |
| 头歌平台课堂签到 | `scripts/educoder.py` | `python3 scripts/educoder.py` | `54 8,10,14,16 * * 1-5` | 待检查 | [educoder.py.md](../scripts/educoder.py.md)（`docs/scripts/educoder.py.md`） |
| EMOS 每日签到 | `scripts/emos_sign.py` | `python3 scripts/emos_sign.py` | `30 8 * * *` | 待检查 | [emos_sign.py.md](../scripts/emos_sign.py.md)（`docs/scripts/emos_sign.py.md`） |
| 终末地签到 | `scripts/endfield_auto_signin.py` | `python3 scripts/endfield_auto_signin.py` | `35 8 * * *` | 待检查 | [endfield_auto_signin.py.md](../scripts/endfield_auto_signin.py.md)（`docs/scripts/endfield_auto_signin.py.md`） |
| 恩山论坛签到 | `scripts/enshan_checkin.py` | `python3 scripts/enshan_checkin.py` | `59 1 * * *` | 待检查 | [enshan_checkin.py.md](../scripts/enshan_checkin.py.md)（`docs/scripts/enshan_checkin.py.md`） |
| EOP官网签到 | `scripts/eop.py` | `python3 scripts/eop.py` | `11 9 * * *` | 待检查 | [eop.py.md](../scripts/eop.py.md)（`docs/scripts/eop.py.md`） |
| Epic免费游戏 | `scripts/epicfreegames.py` | `python3 scripts/epicfreegames.py` | `11 8 * * 6` | 待检查 | [epicfreegames.py.md](../scripts/epicfreegames.py.md)（`docs/scripts/epicfreegames.py.md`） |
| 鸿星尔克签到 | `scripts/erke.py` | `python3 scripts/erke.py` | `12 1 1 1 1` | 待检查 | [erke.py.md](../scripts/erke.py.md)（`docs/scripts/erke.py.md`） |
| 电子科大晚安成电打卡 | `scripts/faq_daily_checkin.py` | `python3 scripts/faq_daily_checkin.py` | `25 21 * * *` | 待检查 | [faq_daily_checkin.py.md](../scripts/faq_daily_checkin.py.md)（`docs/scripts/faq_daily_checkin.py.md`） |
| 飞牛Nas论坛签到 | `scripts/fnnasclub.py` | `python3 scripts/fnnasclub.py` | `49 1 * * *` | 待检查 | [fnnasclub.py.md](../scripts/fnnasclub.py.md)（`docs/scripts/fnnasclub.py.md`） |
| Discuz 论坛日常维护 | `scripts/forum_download.py` | `python3 scripts/forum_download.py` | `29 2 * * *` | 待检查 | [forum_download.py.md](../scripts/forum_download.py.md)（`docs/scripts/forum_download.py.md`） |
| 废文网签到 | `scripts/fwxs_checkin.js` | `node scripts/fwxs_checkin.js` | `57 1 * * *` | 待检查 | [fwxs_checkin.js.md](../scripts/fwxs_checkin.js.md)（`docs/scripts/fwxs_checkin.js.md`） |
| 芬享汇每日签到 | `scripts/fxh.js` | `node scripts/fxh.js` | `18 1 * * *` | 待检查 | [fxh.js.md](../scripts/fxh.js.md)（`docs/scripts/fxh.js.md`） |
| 智汇福大晚点名签到 | `scripts/fzu.py` | `python3 scripts/fzu.py` | `35 21 * * *` | 待检查 | [fzu.py.md](../scripts/fzu.py.md)（`docs/scripts/fzu.py.md`） |
| 吉利汽车签到 | `scripts/geely.js` | `node scripts/geely.js` | `37 0 * * *` | 待检查 | [geely.js.md](../scripts/geely.js.md)（`docs/scripts/geely.js.md`） |
| 阴阳师官网视频与原画 | `scripts/get_yys_cgvideo.py` | `python3 scripts/get_yys_cgvideo.py` | `11 9 * * 0` | 待检查 | [get_yys_cgvideo.py.md](../scripts/get_yys_cgvideo.py.md)（`docs/scripts/get_yys_cgvideo.py.md`） |
| 阴阳师官网原画与CG素材 | `scripts/get_yys_imagelinks.py` | `python3 scripts/get_yys_imagelinks.py` | `28 9 * * 0` | 待检查 | [get_yys_imagelinks.py.md](../scripts/get_yys_imagelinks.py.md)（`docs/scripts/get_yys_imagelinks.py.md`） |
| GLaDOS每日签到 | `scripts/glados.py` | `python3 scripts/glados.py` | `58 0 * * *` | 待检查 | [glados.py.md](../scripts/glados.py.md)（`docs/scripts/glados.py.md`） |
| 好豆每日签到 | `scripts/haodou.py` | `python3 scripts/haodou.py` | `14 9 * * *` | 待检查 | [haodou.py.md](../scripts/haodou.py.md)（`docs/scripts/haodou.py.md`） |
| HelloGitHub月刊提醒 | `scripts/hellogithub.py` | `python3 scripts/hellogithub.py` | `31 8 1 * *` | 待检查 | [hellogithub.py.md](../scripts/hellogithub.py.md)（`docs/scripts/hellogithub.py.md`） |
| HiFiTi与HiFiHi签到 | `scripts/hifiti_checkin.py` | `python3 scripts/hifiti_checkin.py` | `14 1 * * *` | 待检查 | [hifiti_checkin.py.md](../scripts/hifiti_checkin.py.md)（`docs/scripts/hifiti_checkin.py.md`） |
| 活力伊利 | `scripts/hlyl.py` | `python3 scripts/hlyl.py` | `32 0 * * *` | 待检查 | [hlyl.py.md](../scripts/hlyl.py.md)（`docs/scripts/hlyl.py.md`） |
| HoYoLAB 多游戏每日签到 | `scripts/hoyolab_checkin.py` | `python3 scripts/hoyolab_checkin.py` | `25 8 * * *` | 待检查 | [hoyolab_checkin.py.md](../scripts/hoyolab_checkin.py.md)（`docs/scripts/hoyolab_checkin.py.md`） |
| 沪上阿姨签到 | `scripts/hsay.py` | `python3 scripts/hsay.py` | `21 9,18 * * *` | 待检查 | [hsay.py.md](../scripts/hsay.py.md)（`docs/scripts/hsay.py.md`） |
| 华润通微信版签到 | `scripts/huaruntong_wx.py` | `python3 scripts/huaruntong_wx.py` | `18 1 1 1 1` | 待检查 | [huaruntong_wx.py.md](../scripts/huaruntong_wx.py.md)（`docs/scripts/huaruntong_wx.py.md`） |
| 华住会签到 | `scripts/huazhu.py` | `python3 scripts/huazhu.py` | `5 9 * * *` | 待检查 | [huazhu.py.md](../scripts/huazhu.py.md)（`docs/scripts/huazhu.py.md`） |
| 好游快爆游戏签到 | `scripts/hykb_gamesign.js` | `node scripts/hykb_gamesign.js` | `50 1 * * *` | 待检查 | [hykb_gamesign.js.md](../scripts/hykb_gamesign.js.md)（`docs/scripts/hykb_gamesign.js.md`） |
| ikuuu 签到 | `scripts/ikuuu_checkin.py` | `python3 scripts/ikuuu_checkin.py` | `20 1 * * *` | 待检查 | [ikuuu_checkin.py.md](../scripts/ikuuu_checkin.py.md)（`docs/scripts/ikuuu_checkin.py.md`） |
| SF轻小说签到 | `scripts/illustar0_sf_autocheckin.py` | `python3 scripts/illustar0_sf_autocheckin.py` | `16 9 * * *` | 待检查 | [illustar0_sf_autocheckin.py.md](../scripts/illustar0_sf_autocheckin.py.md)（`docs/scripts/illustar0_sf_autocheckin.py.md`） |
| i茅台申购与耐力 | `scripts/imaotai.py` | `python3 scripts/imaotai.py` | `38 2 * * *` | 待检查 | [imaotai.py.md](../scripts/imaotai.py.md)（`docs/scripts/imaotai.py.md`） |
| Pixiv 收藏图片下载 | `scripts/index.js` | `node scripts/index.js` | `48 1 * * *` | 待检查 | [index.js.md](../scripts/index.js.md)（`docs/scripts/index.js.md`） |
| 智慧树共享课每日习惯分 | `scripts/internal.py` | `python3 scripts/internal.py` | `20 7 * * *` | 待检查 | [internal.py.md](../scripts/internal.py.md)（`docs/scripts/internal.py.md`） |
| 爱奇艺签到 | `scripts/iqiyi_checkin.py` | `python3 scripts/iqiyi_checkin.py` | `8 1 * * *` | 待检查 | [iqiyi_checkin.py.md](../scripts/iqiyi_checkin.py.md)（`docs/scripts/iqiyi_checkin.py.md`） |
| 机场面板每日签到 | `scripts/jc_checkin.py` | `python3 scripts/jc_checkin.py` | `45 2 * * *` | 待检查 | [jc_checkin.py.md](../scripts/jc_checkin.py.md)（`docs/scripts/jc_checkin.py.md`） |
| jcqd 多站签到 | `scripts/jcqd.py` | `python3 scripts/jcqd.py` | `5 1 * * *` | 待检查 | [jcqd.py.md](../scripts/jcqd.py.md)（`docs/scripts/jcqd.py.md`） |
| 精易论坛签到 | `scripts/jingyiluntan_sign.py` | `python3 scripts/jingyiluntan_sign.py` | `2 2 * * *` | 待检查 | [jingyiluntan_sign.py.md](../scripts/jingyiluntan_sign.py.md)（`docs/scripts/jingyiluntan_sign.py.md`） |
| 技实习自动签到 | `scripts/jishixi.js` | `node scripts/jishixi.js` | `42 8 * * *` | 待检查 | [jishixi.js.md](../scripts/jishixi.js.md)（`docs/scripts/jishixi.js.md`） |
| 杰士邦安心福利社 | `scripts/jissbon.py` | `python3 scripts/jissbon.py` | `21 2 * * *` | 待检查 | [jissbon.py.md](../scripts/jissbon.py.md)（`docs/scripts/jissbon.py.md`） |
| 劲友家日常任务 | `scripts/jyj.py` | `python3 scripts/jyj.py` | `12 2 * * *` | 待检查 | [jyj.py.md](../scripts/jyj.py.md)（`docs/scripts/jyj.py.md`） |
| 看雪论坛签到 | `scripts/kanxue.js` | `node scripts/kanxue.js` | `0 35 11 * * *` | 待检查 | [kanxue.js.md](../scripts/kanxue.js.md)（`docs/scripts/kanxue.js.md`） |
| 夸父资源社签到 | `scripts/kfzy.js` | `node scripts/kfzy.js` | `0 40 11 * * *` | 待检查 | [kfzy.js.md](../scripts/kfzy.js.md)（`docs/scripts/kfzy.js.md`） |
| 全民K歌签到与奖励 | `scripts/kgqq.py` | `python3 scripts/kgqq.py` | `13 2 * * *` | 待检查 | [kgqq.py.md](../scripts/kgqq.py.md)（`docs/scripts/kgqq.py.md`） |
| 科技玩家签到 | `scripts/kjwj.py` | `python3 scripts/kjwj.py` | `41 2 * * *` | 待检查 | [kjwj.py.md](../scripts/kjwj.py.md)（`docs/scripts/kjwj.py.md`） |
| KukuAI 每日积分 | `scripts/kuku_daily.py` | `python3 scripts/kuku_daily.py` | `0 8 * * *` | 待检查 | [kuku_daily.py.md](../scripts/kuku_daily.py.md)（`docs/scripts/kuku_daily.py.md`） |
| 鸣潮·库街区 每日签到 | `scripts/kurobbs_sign.py` | `python3 scripts/kurobbs_sign.py` | `16 1 * * *` | 待检查 | [kurobbs_sign.py.md](../scripts/kurobbs_sign.py.md)（`docs/scripts/kurobbs_sign.py.md`） |
| LINUX DO 登录与浏览统计 | `scripts/l.py` | `python3 scripts/l.py` | `37 */5 * * *` | 待检查 | [l.py.md](../scripts/l.py.md)（`docs/scripts/l.py.md`） |
| Leaflow 签到 | `scripts/leaflow_checkin_pyleaflow_checkin.py` | `python3 scripts/leaflow_checkin_pyleaflow_checkin.py` | `14 0 * * *` | 待检查 | [leaflow_checkin_pyleaflow_checkin.py.md](../scripts/leaflow_checkin_pyleaflow_checkin.py.md)（`docs/scripts/leaflow_checkin_pyleaflow_checkin.py.md`） |
| LeetCode 中文站每日一题自动打卡 | `scripts/leetcode_daily.py` | `python3 scripts/leetcode_daily.py` | `30 0 * * *` | 待检查 | [leetcode_daily.py.md](../scripts/leetcode_daily.py.md)（`docs/scripts/leetcode_daily.py.md`） |
| 量界智算签到 | `scripts/liangjie.py` | `python3 scripts/liangjie.py` | `10 9 * * *` | 待检查 | [liangjie.py.md](../scripts/liangjie.py.md)（`docs/scripts/liangjie.py.md`） |
| 咔叽网单每日签到 | `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py` | `python3 scripts/littlewuh_qinglongbox_dailycheckin_scripts.py` | `16 2 * * *` | 待检查 | [littlewuh_qinglongbox_dailycheckin_scripts.py.md](../scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md)（`docs/scripts/littlewuh_qinglongbox_dailycheckin_scripts.py.md`） |
| LobsterAI 每日签到 | `scripts/lobsterai_checkin.py` | `python3 scripts/lobsterai_checkin.py` | `27 0 * * *` | 待检查 | [lobsterai_checkin.py.md](../scripts/lobsterai_checkin.py.md)（`docs/scripts/lobsterai_checkin.py.md`） |
| 龙湖天街签到 | `scripts/longhu.py` | `python3 scripts/longhu.py` | `5 8 * * *` | 待检查 | [longhu.py.md](../scripts/longhu.py.md)（`docs/scripts/longhu.py.md`） |
| Loomy 每日积分与新手任务 | `scripts/loomy_daily.py` | `python3 scripts/loomy_daily.py` | `54 0 * * *` | 待检查 | [loomy_daily.py.md](../scripts/loomy_daily.py.md)（`docs/scripts/loomy_daily.py.md`） |
| 领克App每日签到分享 | `scripts/lynkco_qinglong_single.py` | `python3 scripts/lynkco_qinglong_single.py` | `1 2 * * *` | 待检查 | [lynkco_qinglong_single.py.md](../scripts/lynkco_qinglong_single.py.md)（`docs/scripts/lynkco_qinglong_single.py.md`） |
| Wallhaven最新壁纸下载 | `scripts/main.py` | `python3 scripts/main.py` | `0 2 * * *` | 待检查 | [main.py.md](../scripts/main.py.md)（`docs/scripts/main.py.md`） |
| 影视飓风会员签到 | `scripts/mediastorm_club.py` | `python3 scripts/mediastorm_club.py` | `3 9 * * *` | 待检查 | [mediastorm_club.py.md](../scripts/mediastorm_club.py.md)（`docs/scripts/mediastorm_club.py.md`） |
| 喵御宅每日签到 | `scripts/mfuns_sign.py` | `python3 scripts/mfuns_sign.py` | `9 9 * * *` | 待检查 | [mfuns_sign.py.md](../scripts/mfuns_sign.py.md)（`docs/scripts/mfuns_sign.py.md`） |
| HDSky签到 | `scripts/mian.py` | `python3 scripts/mian.py` | `20 9 * * *` | 待检查 | [mian.py.md](../scripts/mian.py.md)（`docs/scripts/mian.py.md`） |
| 米饭APP日常维护 | `scripts/mifan_optimized.py` | `python3 scripts/mifan_optimized.py` | `59 0 * * *` | 待检查 | [mifan_optimized.py.md](../scripts/mifan_optimized.py.md)（`docs/scripts/mifan_optimized.py.md`） |
| 小米运动账号验证与步数上传 | `scripts/mimotion.py` | `python3 scripts/mimotion.py` | `46 0 * * *` | 待检查 | [mimotion.py.md](../scripts/mimotion.py.md)（`docs/scripts/mimotion.py.md`） |
| Discuz k_misign 每日签到 | `scripts/misign.js` | `node scripts/misign.js` | `19 8 * * *` | 待检查 | [misign.js.md](../scripts/misign.js.md)（`docs/scripts/misign.js.md`） |
| 米游社游戏签到 | `scripts/miyoushe_sign.py` | `python3 scripts/miyoushe_sign.py` | `11 8 * * *` | 待检查 | [miyoushe_sign.py.md](../scripts/miyoushe_sign.py.md)（`docs/scripts/miyoushe_sign.py.md`） |
| ModelScope 魔搭每日签到 | `scripts/modelscope_daily.py` | `python3 scripts/modelscope_daily.py` | `0 9 * * *` | 待检查 | [modelscope_daily.py.md](../scripts/modelscope_daily.py.md)（`docs/scripts/modelscope_daily.py.md`） |
| mybt 每日签到与访问积分 | `scripts/mybt.py` | `python3 scripts/mybt.py` | `2 8 * * *` | 待检查 | [mybt.py.md](../scripts/mybt.py.md)（`docs/scripts/mybt.py.md`） |
| NDNU第二课堂签到签退 | `scripts/ndnu.py` | `python3 scripts/ndnu.py` | `*/5 7-22 * * *` | 待检查 | [ndnu.py.md](../scripts/ndnu.py.md)（`docs/scripts/ndnu.py.md`） |
| 网易云全能打卡 | `scripts/netease_task.py` | `python3 scripts/netease_task.py` | `53 1 * * *` | 待检查 | [netease_task.py.md](../scripts/netease_task.py.md)（`docs/scripts/netease_task.py.md`） |
| NewAPI 自动签到 | `scripts/newapi.py` | `python3 scripts/newapi.py` | `18 8 * * *` | 待检查 | [newapi.py.md](../scripts/newapi.py.md)（`docs/scripts/newapi.py.md`） |
| NGA 论坛签到 | `scripts/nga_checkin.py` | `python3 scripts/nga_checkin.py` | `49 0 * * *` | 待检查 | [nga_checkin.py.md](../scripts/nga_checkin.py.md)（`docs/scripts/nga_checkin.py.md`） |
| 九号出行每日签到 | `scripts/nine_bot_checkin.py` | `python3 scripts/nine_bot_checkin.py` | `0 7 * * *` | 待检查 | [nine_bot_checkin.py.md](../scripts/nine_bot_checkin.py.md)（`docs/scripts/nine_bot_checkin.py.md`） |
| NodeSeek 论坛签到 | `scripts/nodeseek_checkin.py` | `python3 scripts/nodeseek_checkin.py` | `41 0 * * *` | 待检查 | [nodeseek_checkin.py.md](../scripts/nodeseek_checkin.py.md)（`docs/scripts/nodeseek_checkin.py.md`） |
| NSSCTF 签到 | `scripts/nssctf_checkin.py` | `python3 scripts/nssctf_checkin.py` | `8 8 * * *` | 待检查 | [nssctf_checkin.py.md](../scripts/nssctf_checkin.py.md)（`docs/scripts/nssctf_checkin.py.md`） |
| 塔吉多（异环）自动签到 | `scripts/nte.py` | `python3 scripts/nte.py` | `0 1 * * *` | 待检查 | [nte.py.md](../scripts/nte.py.md)（`docs/scripts/nte.py.md`） |
| OfficeAce 果办每日奖励 | `scripts/officeace_daily.py` | `python3 scripts/officeace_daily.py` | `57 0 * * *` | 待检查 | [officeace_daily.py.md](../scripts/officeace_daily.py.md)（`docs/scripts/officeace_daily.py.md`） |
| 华润通Ole签到 | `scripts/ole.py` | `python3 scripts/ole.py` | `6 1 1 1 1` | 待检查 | [ole.py.md](../scripts/ole.py.md)（`docs/scripts/ole.py.md`） |
| 欧文 Soul-Mates 每日签到 | `scripts/ouwen.py` | `python3 scripts/ouwen.py` | `0 18 * * *` | 待检查 | [ouwen.py.md](../scripts/ouwen.py.md)（`docs/scripts/ouwen.py.md`） |
| PassNAT 签到 | `scripts/passnat_checkin.py` | `python3 scripts/passnat_checkin.py` | `13 1 * * *` | 待检查 | [passnat_checkin.py.md](../scripts/passnat_checkin.py.md)（`docs/scripts/passnat_checkin.py.md`） |
| 哔咔漫画每日打卡 | `scripts/pica_punch.py` | `python3 scripts/pica_punch.py` | `45 5 * * *` | 待检查 | [pica_punch.py.md](../scripts/pica_punch.py.md)（`docs/scripts/pica_punch.py.md`） |
| PSNINE 每日祈祷 | `scripts/psnine.py` | `python3 scripts/psnine.py` | `16 0 * * *` | 待检查 | [psnine.py.md](../scripts/psnine.py.md)（`docs/scripts/psnine.py.md`） |
| PT 多站签到（SafeLine 兼容维护版） | `scripts/pt_sign_v5.js` | `node scripts/pt_sign_v5.js` | `46 2 * * *` | 待检查 | [pt_sign_v5.js.md](../scripts/pt_sign_v5.js.md)（`docs/scripts/pt_sign_v5.js.md`） |
| Qoder每日签到 | `scripts/qoder_airscript.js` | `node scripts/qoder_airscript.js` | `17 8 * * *` | 待检查 | [qoder_airscript.js.md](../scripts/qoder_airscript.js.md)（`docs/scripts/qoder_airscript.js.md`） |
| QQ音乐超级会员福利站签到 | `scripts/qqmusic_checkin.py` | `python3 scripts/qqmusic_checkin.py` | `22 9 * * *` | 待检查 | [qqmusic_checkin.py.md](../scripts/qqmusic_checkin.py.md)（`docs/scripts/qqmusic_checkin.py.md`） |
| 夸克网盘每日签到 | `scripts/quark_signin.py` | `python3 scripts/quark_signin.py` | `15 0 * * *` | 待检查 | [quark_signin.py.md](../scripts/quark_signin.py.md)（`docs/scripts/quark_signin.py.md`） |
| 小浣熊每日积分 | `scripts/raccoon_daily.py` | `python3 scripts/raccoon_daily.py` | `2 9 * * *` | 待检查 | [raccoon_daily.py.md](../scripts/raccoon_daily.py.md)（`docs/scripts/raccoon_daily.py.md`） |
| 一亩三分地每日签到答题 | `scripts/raw_requests.py` | `python3 scripts/raw_requests.py` | `51 8 * * *` | 待检查 | [raw_requests.py.md](../scripts/raw_requests.py.md)（`docs/scripts/raw_requests.py.md`） |
| Rousi 签到 | `scripts/rousi_checkin.js` | `node scripts/rousi_checkin.js` | `42 0 * * *` | 待检查 | [rousi_checkin.js.md](../scripts/rousi_checkin.js.md)（`docs/scripts/rousi_checkin.js.md`） |
| eatASMR每日签到 | `scripts/scf_eat.py` | `python3 scripts/scf_eat.py` | `37 8 * * *` | 待检查 | [scf_eat.py.md](../scripts/scf_eat.py.md)（`docs/scripts/scf_eat.py.md`） |
| 成都大学ISP每日登记 | `scripts/services.js` | `node scripts/services.js` | `1 7 * * *` | 待检查 | [services.js.md](../scripts/services.js.md)（`docs/scripts/services.js.md`） |
| 顺丰快递积分任务 | `scripts/sf.py` | `python3 scripts/sf.py` | `16 1 1 1 1` | 待检查 | [sf.py.md](../scripts/sf.py.md)（`docs/scripts/sf.py.md`） |
| 顺丰速运签到 | `scripts/sfsu_checkin.py` | `python3 scripts/sfsu_checkin.py` | `17 0 * * *` | 待检查 | [sfsu_checkin.py.md](../scripts/sfsu_checkin.py.md)（`docs/scripts/sfsu_checkin.py.md`） |
| 申工社每日任务 | `scripts/sgs.py` | `python3 scripts/sgs.py` | `43 0 * * *` | 待检查 | [sgs.py.md](../scripts/sgs.py.md)（`docs/scripts/sgs.py.md`） |
| 书亦烧仙草签到 | `scripts/shuyi.py` | `python3 scripts/shuyi.py` | `51 0 * * *` | 待检查 | [shuyi.py.md](../scripts/shuyi.py.md)（`docs/scripts/shuyi.py.md`） |
| 上马官网每日签到 | `scripts/sign_in.js` | `node scripts/sign_in.js` | `24 8 * * *` | 待检查 | [sign_in.js.md](../scripts/sign_in.js.md)（`docs/scripts/sign_in.js.md`） |
| 森空岛每日任务 | `scripts/skland_daily.py` | `python3 scripts/skland_daily.py` | `33 1 * * *` | 待检查 | [skland_daily.py.md](../scripts/skland_daily.py.md)（`docs/scripts/skland_daily.py.md`） |
| 什么值得买签到 | `scripts/smzdm_checkin.js` | `node scripts/smzdm_checkin.js` | `15 1 * * *` | 待检查 | [smzdm_checkin.js.md](../scripts/smzdm_checkin.js.md)（`docs/scripts/smzdm_checkin.js.md`） |
| SSL证书检查 | `scripts/ssl_cert_check.py` | `python3 scripts/ssl_cert_check.py` | `10 2 * * *` | 待检查 | [ssl_cert_check.py.md](../scripts/ssl_cert_check.py.md)（`docs/scripts/ssl_cert_check.py.md`） |
| 长江雨课堂课堂签到 | `scripts/startup.py` | `python3 scripts/startup.py` | `*/5 8-18 * * 1-5` | 待检查 | [startup.py.md](../scripts/startup.py.md)（`docs/scripts/startup.py.md`） |
| 33台词每日签到 | `scripts/sudojia_33agilestudio.js` | `node scripts/sudojia_33agilestudio.js` | `24 0 * * *` | 待检查 | [sudojia_33agilestudio.js.md](../scripts/sudojia_33agilestudio.js.md)（`docs/scripts/sudojia_33agilestudio.js.md`） |
| 所有女生会员签到 | `scripts/sudojia_allgirls.js` | `node scripts/sudojia_allgirls.js` | `33 2 * * *` | 待检查 | [sudojia_allgirls.js.md](../scripts/sudojia_allgirls.js.md)（`docs/scripts/sudojia_allgirls.js.md`） |
| 安慕希每日签到 | `scripts/sudojia_amx.js` | `node scripts/sudojia_amx.js` | `25 0 * * *` | 待检查 | [sudojia_amx.js.md](../scripts/sudojia_amx.js.md)（`docs/scripts/sudojia_amx.js.md`） |
| 多合一账号失效检测 | `scripts/sudojia_authcheck.js` | `node scripts/sudojia_authcheck.js` | `32 12,21 * * *` | 待检查 | [sudojia_authcheck.js.md](../scripts/sudojia_authcheck.js.md)（`docs/scripts/sudojia_authcheck.js.md`） |
| 香蕉视频每日任务 | `scripts/sudojia_bananavideo.js` | `node scripts/sudojia_bananavideo.js` | `19 0 * * *` | 待检查 | [sudojia_bananavideo.js.md](../scripts/sudojia_bananavideo.js.md)（`docs/scripts/sudojia_bananavideo.js.md`） |
| 贝因美每日签到 | `scripts/sudojia_beiyinmei.js` | `node scripts/sudojia_beiyinmei.js` | `25 2 * * *` | 待检查 | [sudojia_beiyinmei.js.md](../scripts/sudojia_beiyinmei.js.md)（`docs/scripts/sudojia_beiyinmei.js.md`） |
| 植物星球 | `scripts/sudojia_botanystar.js` | `node scripts/sudojia_botanystar.js` | `33 0 * * *` | 待检查 | [sudojia_botanystar.js.md](../scripts/sudojia_botanystar.js.md)（`docs/scripts/sudojia_botanystar.js.md`） |
| 霸王茶姬每日签到与积分提醒 | `scripts/sudojia_bwtea.js` | `node scripts/sudojia_bwtea.js` | `53 0 * * *` | 待检查 | [sudojia_bwtea.js.md](../scripts/sudojia_bwtea.js.md)（`docs/scripts/sudojia_bwtea.js.md`） |
| 七彩虹商城 | `scripts/sudojia_colorful_mall.js` | `node scripts/sudojia_colorful_mall.js` | `22 0 * * *` | 待检查 | [sudojia_colorful_mall.js.md](../scripts/sudojia_colorful_mall.js.md)（`docs/scripts/sudojia_colorful_mall.js.md`） |
| 飞蚂蚁旧衣回收 | `scripts/sudojia_flyant.js` | `node scripts/sudojia_flyant.js` | `50 0 * * *` | 待检查 | [sudojia_flyant.js.md](../scripts/sudojia_flyant.js.md)（`docs/scripts/sudojia_flyant.js.md`） |
| 飞牛私有云签到 | `scripts/sudojia_fnnas.js` | `node scripts/sudojia_fnnas.js` | `54 1 * * *` | 待检查 | [sudojia_fnnas.js.md](../scripts/sudojia_fnnas.js.md)（`docs/scripts/sudojia_fnnas.js.md`） |
| 厚工坊签到与任务 | `scripts/sudojia_hgf.js` | `node scripts/sudojia_hgf.js` | `44 1 * * *` | 待检查 | [sudojia_hgf.js.md](../scripts/sudojia_hgf.js.md)（`docs/scripts/sudojia_hgf.js.md`） |
| 海澜之家-游戏 | `scripts/sudojia_hlzj_game.js` | `node scripts/sudojia_hlzj_game.js` | `20 8,15,20 * * *` | 待检查 | [sudojia_hlzj_game.js.md](../scripts/sudojia_hlzj_game.js.md)（`docs/scripts/sudojia_hlzj_game.js.md`） |
| 媓钻护肤品 | `scripts/sudojia_hzhfp.js` | `node scripts/sudojia_hzhfp.js` | `40 0 * * *` | 待检查 | [sudojia_hzhfp.js.md](../scripts/sudojia_hzhfp.js.md)（`docs/scripts/sudojia_hzhfp.js.md`） |
| 玩拍由我俱乐部 | `scripts/sudojia_instax.js` | `node scripts/sudojia_instax.js` | `26 2 * * *` | 待检查 | [sudojia_instax.js.md](../scripts/sudojia_instax.js.md)（`docs/scripts/sudojia_instax.js.md`） |
| 江淮卡友 | `scripts/sudojia_jhcard.js` | `node scripts/sudojia_jhcard.js` | `7 0 * * *` | 待检查 | [sudojia_jhcard.js.md](../scripts/sudojia_jhcard.js.md)（`docs/scripts/sudojia_jhcard.js.md`） |
| 多娇江山 | `scripts/sudojia_jiangshan.js` | `node scripts/sudojia_jiangshan.js` | `20 2 * * *` | 待检查 | [sudojia_jiangshan.js.md](../scripts/sudojia_jiangshan.js.md)（`docs/scripts/sudojia_jiangshan.js.md`） |
| 金典有机生活+ | `scripts/sudojia_jindian.js` | `node scripts/sudojia_jindian.js` | `18 0 * * *` | 待检查 | [sudojia_jindian.js.md](../scripts/sudojia_jindian.js.md)（`docs/scripts/sudojia_jindian.js.md`） |
| 嘉立创硬件开源平台 | `scripts/sudojia_jlc_yj.js` | `node scripts/sudojia_jlc_yj.js` | `31 0 * * *` | 待检查 | [sudojia_jlc_yj.js.md](../scripts/sudojia_jlc_yj.js.md)（`docs/scripts/sudojia_jlc_yj.js.md`） |
| 稀土掘金每日签到 | `scripts/sudojia_juejin.js` | `node scripts/sudojia_juejin.js` | `43 2 * * *` | 待检查 | [sudojia_juejin.js.md](../scripts/sudojia_juejin.js.md)（`docs/scripts/sudojia_juejin.js.md`） |
| 植白说官方商城 | `scripts/sudojia_kozbs.js` | `node scripts/sudojia_kozbs.js` | `28 0 * * *` | 待检查 | [sudojia_kozbs.js.md](../scripts/sudojia_kozbs.js.md)（`docs/scripts/sudojia_kozbs.js.md`） |
| 开天工作室 | `scripts/sudojia_ktgzs.js` | `node scripts/sudojia_ktgzs.js` | `35 0 * * *` | 待检查 | [sudojia_ktgzs.js.md](../scripts/sudojia_ktgzs.js.md)（`docs/scripts/sudojia_ktgzs.js.md`） |
| 顾家家居签到 | `scripts/sudojia_kukahome.js` | `node scripts/sudojia_kukahome.js` | `9 2 * * *` | 待检查 | [sudojia_kukahome.js.md](../scripts/sudojia_kukahome.js.md)（`docs/scripts/sudojia_kukahome.js.md`） |
| 库街区每日签到 | `scripts/sudojia_kuro.js` | `node scripts/sudojia_kuro.js` | `4 2 * * *` | 待检查 | [sudojia_kuro.js.md](../scripts/sudojia_kuro.js.md)（`docs/scripts/sudojia_kuro.js.md`） |
| 老板电器服务微商城 | `scripts/sudojia_laoban.js` | `node scripts/sudojia_laoban.js` | `6 1 * * *` | 待检查 | [sudojia_laoban.js.md](../scripts/sudojia_laoban.js.md)（`docs/scripts/sudojia_laoban.js.md`） |
| 龙湖天街 | `scripts/sudojia_longfor.js` | `node scripts/sudojia_longfor.js` | `39 1 * * *` | 待检查 | [sudojia_longfor.js.md](../scripts/sudojia_longfor.js.md)（`docs/scripts/sudojia_longfor.js.md`） |
| 欣都龙城每日签到 | `scripts/sudojia_mallcoo.js` | `node scripts/sudojia_mallcoo.js` | `9 1 * * *` | 待检查 | [sudojia_mallcoo.js.md](../scripts/sudojia_mallcoo.js.md)（`docs/scripts/sudojia_mallcoo.js.md`） |
| 馬伍旺饮料厂 | `scripts/sudojia_mawuwang.js` | `node scripts/sudojia_mawuwang.js` | `13 0 * * *` | 待检查 | [sudojia_mawuwang.js.md](../scripts/sudojia_mawuwang.js.md)（`docs/scripts/sudojia_mawuwang.js.md`） |
| 美的会员 | `scripts/sudojia_midea.js` | `node scripts/sudojia_midea.js` | `48 0 * * *` | 待检查 | [sudojia_midea.js.md](../scripts/sudojia_midea.js.md)（`docs/scripts/sudojia_midea.js.md`） |
| 蜜雪冰城每日签到 | `scripts/sudojia_mxbc.js` | `node scripts/sudojia_mxbc.js` | `22 1 * * *` | 待检查 | [sudojia_mxbc.js.md](../scripts/sudojia_mxbc.js.md)（`docs/scripts/sudojia_mxbc.js.md`） |
| 奈雪点单 | `scripts/sudojia_naixue.js` | `node scripts/sudojia_naixue.js` | `32 1 * * *` | 待检查 | [sudojia_naixue.js.md](../scripts/sudojia_naixue.js.md)（`docs/scripts/sudojia_naixue.js.md`） |
| 雀巢会员 | `scripts/sudojia_nestle.js` | `node scripts/sudojia_nestle.js` | `30 2 * * *` | 待检查 | [sudojia_nestle.js.md](../scripts/sudojia_nestle.js.md)（`docs/scripts/sudojia_nestle.js.md`） |
| 南方航空 | `scripts/sudojia_nfhk.js` | `node scripts/sudojia_nfhk.js` | `26 1 * * *` | 待检查 | [sudojia_nfhk.js.md](../scripts/sudojia_nfhk.js.md)（`docs/scripts/sudojia_nfhk.js.md`） |
| OPPO商城每日签到与任务领奖 | `scripts/sudojia_opposhop.js` | `node scripts/sudojia_opposhop.js` | `12 0 * * *` | 待检查 | [sudojia_opposhop.js.md](../scripts/sudojia_opposhop.js.md)（`docs/scripts/sudojia_opposhop.js.md`） |
| 胖哥俩肉蟹煲 | `scripts/sudojia_pangge.js` | `node scripts/sudojia_pangge.js` | `7 1 * * *` | 待检查 | [sudojia_pangge.js.md](../scripts/sudojia_pangge.js.md)（`docs/scripts/sudojia_pangge.js.md`） |
| 爷爷不泡茶 | `scripts/sudojia_paotea.js` | `node scripts/sudojia_paotea.js` | `58 1 * * *` | 待检查 | [sudojia_paotea.js.md](../scripts/sudojia_paotea.js.md)（`docs/scripts/sudojia_paotea.js.md`） |
| 上海杨浦 | `scripts/sudojia_shmedia.js` | `node scripts/sudojia_shmedia.js` | `53 1 * * *` | 待检查 | [sudojia_shmedia.js.md](../scripts/sudojia_shmedia.js.md)（`docs/scripts/sudojia_shmedia.js.md`） |
| 水费易签到 | `scripts/sudojia_shuifei.js` | `node scripts/sudojia_shuifei.js` | `4 0 * * *` | 待检查 | [sudojia_shuifei.js.md](../scripts/sudojia_shuifei.js.md)（`docs/scripts/sudojia_shuifei.js.md`） |
| SSPANEL面板签到 | `scripts/sudojia_sspanel.js` | `node scripts/sudojia_sspanel.js` | `34 0 * * *` | 待检查 | [sudojia_sspanel.js.md](../scripts/sudojia_sspanel.js.md)（`docs/scripts/sudojia_sspanel.js.md`） |
| 星妈优选 | `scripts/sudojia_starmom.js` | `node scripts/sudojia_starmom.js` | `42 0 * * *` | 待检查 | [sudojia_starmom.js.md](../scripts/sudojia_starmom.js.md)（`docs/scripts/sudojia_starmom.js.md`） |
| 特步会员中心 | `scripts/sudojia_tebu.js` | `node scripts/sudojia_tebu.js` | `37 1 * * *` | 待检查 | [sudojia_tebu.js.md](../scripts/sudojia_tebu.js.md)（`docs/scripts/sudojia_tebu.js.md`） |
| TILTA影像城 | `scripts/sudojia_tilta.js` | `node scripts/sudojia_tilta.js` | `24 1 * * *` | 待检查 | [sudojia_tilta.js.md](../scripts/sudojia_tilta.js.md)（`docs/scripts/sudojia_tilta.js.md`） |
| 图虫每日签到 | `scripts/sudojia_tuchong.js` | `node scripts/sudojia_tuchong.js` | `2 0 * * *` | 待检查 | [sudojia_tuchong.js.md](../scripts/sudojia_tuchong.js.md)（`docs/scripts/sudojia_tuchong.js.md`） |
| V2EX每日签到 | `scripts/sudojia_v2ex.js` | `node scripts/sudojia_v2ex.js` | `1 1 * * *` | 待检查 | [sudojia_v2ex.js.md](../scripts/sudojia_v2ex.js.md)（`docs/scripts/sudojia_v2ex.js.md`） |
| 薇诺娜专柜商城 | `scripts/sudojia_wnna.js` | `node scripts/sudojia_wnna.js` | `29 0 * * *` | 待检查 | [sudojia_wnna.js.md](../scripts/sudojia_wnna.js.md)（`docs/scripts/sudojia_wnna.js.md`） |
| 新湖南每日签到 | `scripts/sudojia_xhn.js` | `node scripts/sudojia_xhn.js` | `51 1 * * *` | 待检查 | [sudojia_xhn.js.md](../scripts/sudojia_xhn.js.md)（`docs/scripts/sudojia_xhn.js.md`） |
| 享玩游戏APP | `scripts/sudojia_xiangwan.js` | `node scripts/sudojia_xiangwan.js` | `15 2 * * *` | 待检查 | [sudojia_xiangwan.js.md](../scripts/sudojia_xiangwan.js.md)（`docs/scripts/sudojia_xiangwan.js.md`） |
| 小米社区-小程序 | `scripts/sudojia_xiaomi_community.js` | `node scripts/sudojia_xiaomi_community.js` | `25 1 * * *` | 待检查 | [sudojia_xiaomi_community.js.md](../scripts/sudojia_xiaomi_community.js.md)（`docs/scripts/sudojia_xiaomi_community.js.md`） |
| 心喜签到 | `scripts/sudojia_xinxi.js` | `node scripts/sudojia_xinxi.js` | `20 1 * * *` | 待检查 | [sudojia_xinxi.js.md](../scripts/sudojia_xinxi.js.md)（`docs/scripts/sudojia_xinxi.js.md`） |
| 小牛电动社区任务（安全维护版） | `scripts/sudojia_xniu.js` | `node scripts/sudojia_xniu.js` | `40 1 * * *` | 待检查 | [sudojia_xniu.js.md](../scripts/sudojia_xniu.js.md)（`docs/scripts/sudojia_xniu.js.md`） |
| 兴攀农场 | `scripts/sudojia_xpfarm.js` | `node scripts/sudojia_xpfarm.js` | `36 11,18 * * *` | 待检查 | [sudojia_xpfarm.js.md](../scripts/sudojia_xpfarm.js.md)（`docs/scripts/sudojia_xpfarm.js.md`） |
| 智能电视签到 | `scripts/sudojia_znds.js` | `node scripts/sudojia_znds.js` | `31 2 * * *` | 待检查 | [sudojia_znds.js.md](../scripts/sudojia_znds.js.md)（`docs/scripts/sudojia_znds.js.md`） |
| 甄稀冰淇淋每日签到 | `scripts/sudojia_zxice.js` | `node scripts/sudojia_zxice.js` | `34 2 * * *` | 待检查 | [sudojia_zxice.js.md](../scripts/sudojia_zxice.js.md)（`docs/scripts/sudojia_zxice.js.md`） |
| 微博超话签到 | `scripts/supertopicsign.py` | `python3 scripts/supertopicsign.py` | `41 1 * * *` | 待检查 | [supertopicsign.py.md](../scripts/supertopicsign.py.md)（`docs/scripts/supertopicsign.py.md`） |
| 所有女生会员服务中心积分版 | `scripts/synspoint.py` | `python3 scripts/synspoint.py` | `16 8,12 * * *` | 待检查 | [synspoint.py.md](../scripts/synspoint.py.md)（`docs/scripts/synspoint.py.md`） |
| Tabbit 国内版每日签到 | `scripts/tabbit_cn_daily.py` | `python3 scripts/tabbit_cn_daily.py` | `18 9 * * *` | 待检查 | [tabbit_cn_daily.py.md](../scripts/tabbit_cn_daily.py.md)（`docs/scripts/tabbit_cn_daily.py.md`） |
| Taker每日挖矿 | `scripts/taker.js` | `node scripts/taker.js` | `26 8 * * *` | 待检查 | [taker.js.md](../scripts/taker.js.md)（`docs/scripts/taker.js.md`） |
| 掘金好好生活计划打卡 | `scripts/task_0e52328d.py` | `python3 scripts/task_0e52328d.py` | `2 1 * * *` | 待检查 | [task_0e52328d.py.md](../scripts/task_0e52328d.py.md)（`docs/scripts/task_0e52328d.py.md`） |
| 洛谷签到 | `scripts/task_198bae30.py` | `python3 scripts/task_198bae30.py` | `0 10 * * *` | 待检查 | [task_198bae30.py.md](../scripts/task_198bae30.py.md)（`docs/scripts/task_198bae30.py.md`） |
| OpenLayer每日签到 | `scripts/task_1d90366e.js` | `node scripts/task_1d90366e.js` | `23 8,20 * * *` | 待检查 | [task_1d90366e.js.md](../scripts/task_1d90366e.js.md)（`docs/scripts/task_1d90366e.js.md`） |
| HayFrp每日签到 | `scripts/task_2c89474a.js` | `node scripts/task_2c89474a.js` | `35 1 * * *` | 待检查 | [task_2c89474a.js.md](../scripts/task_2c89474a.js.md)（`docs/scripts/task_2c89474a.js.md`） |
| 蘑菇钉工学云打卡 | `scripts/task_3827d2e0.js` | `node scripts/task_3827d2e0.js` | `3 8,18 * * *` | 待检查 | [task_3827d2e0.js.md](../scripts/task_3827d2e0.js.md)（`docs/scripts/task_3827d2e0.js.md`） |
| 雨云签到与安全续费 | `scripts/task_3aae8a25.py` | `python3 scripts/task_3aae8a25.py` | `47 0 * * *` | 待检查 | [task_3aae8a25.py.md](../scripts/task_3aae8a25.py.md)（`docs/scripts/task_3aae8a25.py.md`） |
| 昆明医科大疫情健康填报 | `scripts/task_4f815667.py` | `python3 scripts/task_4f815667.py` | `43 8 * * *` | 待检查 | [task_4f815667.py.md](../scripts/task_4f815667.py.md)（`docs/scripts/task_4f815667.py.md`） |
| 百度知道签到 | `scripts/task_51f65d9b.py` | `python3 scripts/task_51f65d9b.py` | `30 10 * * *` | 待检查 | [task_51f65d9b.py.md](../scripts/task_51f65d9b.py.md)（`docs/scripts/task_51f65d9b.py.md`） |
| 阅次元论坛签到 | `scripts/task_5254d901.py` | `python3 scripts/task_5254d901.py` | `44 8 * * *` | 待检查 | [task_5254d901.py.md](../scripts/task_5254d901.py.md)（`docs/scripts/task_5254d901.py.md`） |
| OA实习签到 | `scripts/task_62e6cbbd.py` | `python3 scripts/task_62e6cbbd.py` | `34 8 * * *` | 待检查 | [task_62e6cbbd.py.md](../scripts/task_62e6cbbd.py.md)（`docs/scripts/task_62e6cbbd.py.md`） |
| 工软校园健康填报 | `scripts/task_64f5e3fd.py` | `python3 scripts/task_64f5e3fd.py` | `47 8 * * *` | 待检查 | [task_64f5e3fd.py.md](../scripts/task_64f5e3fd.py.md)（`docs/scripts/task_64f5e3fd.py.md`） |
| LinkHub 每日签到 | `scripts/task_70123c59.py` | `python3 scripts/task_70123c59.py` | `54 8 * * *` | 待检查 | [task_70123c59.py.md](../scripts/task_70123c59.py.md)（`docs/scripts/task_70123c59.py.md`） |
| hao4k每日签到 | `scripts/task_7a56bf21.py` | `python3 scripts/task_7a56bf21.py` | `41 8 * * *` | 待检查 | [task_7a56bf21.py.md](../scripts/task_7a56bf21.py.md)（`docs/scripts/task_7a56bf21.py.md`） |
| 班级魔法自动签到 | `scripts/task_7be4b090.py` | `python3 scripts/task_7be4b090.py` | `44 8 * * 1-5` | 待检查 | [task_7be4b090.py.md](../scripts/task_7be4b090.py.md)（`docs/scripts/task_7be4b090.py.md`） |
| 草榴社区每日签到 | `scripts/task_845c9306.js` | `node scripts/task_845c9306.js` | `31 8 * * *` | 待检查 | [task_845c9306.js.md](../scripts/task_845c9306.js.md)（`docs/scripts/task_845c9306.js.md`） |
| 昆医大疫情防控填报 | `scripts/task_8f8ad2c5.py` | `python3 scripts/task_8f8ad2c5.py` | `53 7,15 * * *` | 待检查 | [task_8f8ad2c5.py.md](../scripts/task_8f8ad2c5.py.md)（`docs/scripts/task_8f8ad2c5.py.md`） |
| MT论坛签到 | `scripts/task_9a14e9eb.py` | `python3 scripts/task_9a14e9eb.py` | `39 0 * * *` | 待检查 | [task_9a14e9eb.py.md](../scripts/task_9a14e9eb.py.md)（`docs/scripts/task_9a14e9eb.py.md`） |
| FF14石之家签到 | `scripts/task_a4b5c493.py` | `python3 scripts/task_a4b5c493.py` | `47 2 * * *` | 待检查 | [task_a4b5c493.py.md](../scripts/task_a4b5c493.py.md)（`docs/scripts/task_a4b5c493.py.md`） |
| AbyssWorld每日签到 | `scripts/task_ad4c4f3a.js` | `node scripts/task_ad4c4f3a.js` | `39 8 * * *` | 待检查 | [task_ad4c4f3a.js.md](../scripts/task_ad4c4f3a.js.md)（`docs/scripts/task_ad4c4f3a.js.md`） |
| TJUPT每日签到 | `scripts/task_b80894cb.py` | `python3 scripts/task_b80894cb.py` | `13 9 * * *` | 待检查 | [task_b80894cb.py.md](../scripts/task_b80894cb.py.md)（`docs/scripts/task_b80894cb.py.md`） |
| 今日校园辅导员签到 | `scripts/task_c04cea4d.py` | `python3 scripts/task_c04cea4d.py` | `0 21 * * *` | 待检查 | [task_c04cea4d.py.md](../scripts/task_c04cea4d.py.md)（`docs/scripts/task_c04cea4d.py.md`） |
| 又拍云签到与每日任务 | `scripts/task_d09de588.py` | `python3 scripts/task_d09de588.py` | `45 8 * * *` | 待检查 | [task_d09de588.py.md](../scripts/task_d09de588.py.md)（`docs/scripts/task_d09de588.py.md`） |
| 爱桌游每日签到 | `scripts/task_d530fa58.py` | `python3 scripts/task_d530fa58.py` | `0 5 * * *` | 待检查 | [task_d530fa58.py.md](../scripts/task_d530fa58.py.md)（`docs/scripts/task_d530fa58.py.md`） |
| hao4k每日签到 | `scripts/task_e5c5d07b.py` | `python3 scripts/task_e5c5d07b.py` | `55 8 * * *` | 待检查 | [task_e5c5d07b.py.md](../scripts/task_e5c5d07b.py.md)（`docs/scripts/task_e5c5d07b.py.md`） |
| FZQOJ每日签到 | `scripts/task_ed4d6d4d.py` | `python3 scripts/task_ed4d6d4d.py` | `53 8 * * *` | 待检查 | [task_ed4d6d4d.py.md](../scripts/task_ed4d6d4d.py.md)（`docs/scripts/task_ed4d6d4d.py.md`） |
| M-SEC 每日签到 | `scripts/task_f37fb5e9.py` | `python3 scripts/task_f37fb5e9.py` | `6 8 * * *` | 待检查 | [task_f37fb5e9.py.md](../scripts/task_f37fb5e9.py.md)（`docs/scripts/task_f37fb5e9.py.md`） |
| 网易云音乐人签到 | `scripts/task_f7e4fa18.py` | `python3 scripts/task_f7e4fa18.py` | `21 9 * * *` | 待检查 | [task_f7e4fa18.py.md](../scripts/task_f7e4fa18.py.md)（`docs/scripts/task_f7e4fa18.py.md`） |
| 重庆工程职院顶岗实习 | `scripts/task_f8f6237c.py` | `python3 scripts/task_f8f6237c.py` | `49 8 * * *` | 待检查 | [task_f8f6237c.py.md](../scripts/task_f8f6237c.py.md)（`docs/scripts/task_f8f6237c.py.md`） |
| 起点阅读 App 签到 | `scripts/task_fbfb17a0.py` | `python3 scripts/task_fbfb17a0.py` | `4 1 * * *` | 待检查 | [task_fbfb17a0.py.md](../scripts/task_fbfb17a0.py.md)（`docs/scripts/task_fbfb17a0.py.md`） |
| Telegram每日Bot签到 | `scripts/telegram_daily_checkin.py` | `python3 scripts/telegram_daily_checkin.py` | `33 8 * * *` | 待检查 | [telegram_daily_checkin.py.md](../scripts/telegram_daily_checkin.py.md)（`docs/scripts/telegram_daily_checkin.py.md`） |
| 腾讯视频签到 | `scripts/tencent_video_checkin.py` | `python3 scripts/tencent_video_checkin.py` | `11 1 * * *` | 待检查 | [tencent_video_checkin.py.md](../scripts/tencent_video_checkin.py.md)（`docs/scripts/tencent_video_checkin.py.md`） |
| 塔吉多每日任务 | `scripts/tjd_daily.py` | `python3 scripts/tjd_daily.py` | `24 2 * * *` | 待检查 | [tjd_daily.py.md](../scripts/tjd_daily.py.md)（`docs/scripts/tjd_daily.py.md`） |
| 东方 Portal 每日签到 | `scripts/touhouhelper.py` | `python3 scripts/touhouhelper.py` | `50 8 * * *` | 待检查 | [touhouhelper.py.md](../scripts/touhouhelper.py.md)（`docs/scripts/touhouhelper.py.md`） |
| Trae 每日签到与积分查询 | `scripts/trae_checkin.py` | `python3 scripts/trae_checkin.py` | `7,23,37 * * * *` | 待检查 | [trae_checkin.py.md](../scripts/trae_checkin.py.md)（`docs/scripts/trae_checkin.py.md`） |
| 塔斯汀汉堡签到 | `scripts/tsthb_checkin.py` | `python3 scripts/tsthb_checkin.py` | `19 1 * * *` | 待检查 | [tsthb_checkin.py.md](../scripts/tsthb_checkin.py.md)（`docs/scripts/tsthb_checkin.py.md`） |
| ViewTurbo 每日签到 | `scripts/turbo.py` | `python3 scripts/turbo.py` | `10 8 * * *` | 待检查 | [turbo.py.md](../scripts/turbo.py.md)（`docs/scripts/turbo.py.md`） |
| 天翼云盘签到 | `scripts/ty_netdisk_checkin.py` | `python3 scripts/ty_netdisk_checkin.py` | `6 1 * * *` | 待检查 | [ty_netdisk_checkin.py.md](../scripts/ty_netdisk_checkin.py.md)（`docs/scripts/ty_netdisk_checkin.py.md`） |
| V次元论坛签到 | `scripts/tybbs.py` | `python3 scripts/tybbs.py` | `30 6 * * *` | 待检查 | [tybbs.py.md](../scripts/tybbs.py.md)（`docs/scripts/tybbs.py.md`） |
| 统一茄皇集市抽奖 | `scripts/tyqhdraw.py` | `python3 scripts/tyqhdraw.py` | `0 0 0 * * *` | 待检查 | [tyqhdraw.py.md](../scripts/tyqhdraw.py.md)（`docs/scripts/tyqhdraw.py.md`） |
| 掌瓦每日商店推送 | `scripts/valorantstore.py` | `python3 scripts/valorantstore.py` | `10 0 * * *` | 待检查 | [valorantstore.py.md](../scripts/valorantstore.py.md)（`docs/scripts/valorantstore.py.md`） |
| Vortexa 免费主机检查与领取 | `scripts/vortexa_free_claim.js` | `node scripts/vortexa_free_claim.js` | `1,11,21,31,41,51 * * * *` | 待检查 | [vortexa_free_claim.js.md](../scripts/vortexa_free_claim.js.md)（`docs/scripts/vortexa_free_claim.js.md`） |
| 望潮阅读有礼 | `scripts/wangchao.py` | `python3 scripts/wangchao.py` | `11 2 * * *` | 待检查 | [wangchao.py.md](../scripts/wangchao.py.md)（`docs/scripts/wangchao.py.md`） |
| 微博超话关注批量签到 | `scripts/wb.py` | `python3 scripts/wb.py` | `20 8 * * *` | 待检查 | [wb.py.md](../scripts/wb.py.md)（`docs/scripts/wb.py.md`） |
| Web3Go每日签到 | `scripts/web3go.js` | `node scripts/web3go.js` | `48 8 * * *` | 待检查 | [web3go.js.md](../scripts/web3go.js.md)（`docs/scripts/web3go.js.md`） |
| CC98 WebVPN 每日签到 | `scripts/webvpn_fixed_api.py` | `python3 scripts/webvpn_fixed_api.py` | `12 8 * * *` | 待检查 | [webvpn_fixed_api.py.md](../scripts/webvpn_fixed_api.py.md)（`docs/scripts/webvpn_fixed_api.py.md`） |
| 微博超话网页签到评论 | `scripts/weibo_checkin.py` | `python3 scripts/weibo_checkin.py` | `28 8 * * *` | 待检查 | [weibo_checkin.py.md](../scripts/weibo_checkin.py.md)（`docs/scripts/weibo_checkin.py.md`） |
| 蔚来APP每日签到 | `scripts/weilai_auto_checkin.js` | `node scripts/weilai_auto_checkin.js` | `8 9 * * *` | 待检查 | [weilai_auto_checkin.js.md](../scripts/weilai_auto_checkin.js.md)（`docs/scripts/weilai_auto_checkin.js.md`） |
| 华润通文体未来荟签到 | `scripts/wentiweilaihui.py` | `python3 scripts/wentiweilaihui.py` | `31 1 1 1 1` | 待检查 | [wentiweilaihui.py.md](../scripts/wentiweilaihui.py.md)（`docs/scripts/wentiweilaihui.py.md`） |
| 网际快车每日签到 | `scripts/wjkc.js` | `node scripts/wjkc.js` | `4 9 * * *` | 待检查 | [wjkc.js.md](../scripts/wjkc.js.md)（`docs/scripts/wjkc.js.md`） |
| 万能福利吧每日签到 | `scripts/wnflb.js` | `node scripts/wnflb.js` | `0 45 11 * * *` | 待检查 | [wnflb.js.md](../scripts/wnflb.js.md)（`docs/scripts/wnflb.js.md`） |
| WorkBuddy签到 | `scripts/workbuddy.py` | `python3 scripts/workbuddy.py` | `45 1 * * *` | 待检查 | [workbuddy.py.md](../scripts/workbuddy.py.md)（`docs/scripts/workbuddy.py.md`） |
| WorkBuddy 国内版日常维护 | `scripts/workbuddy_daily.py` | `python3 scripts/workbuddy_daily.py` | `15 7,12 * * *` | 待检查 | [workbuddy_daily.py.md](../scripts/workbuddy_daily.py.md)（`docs/scripts/workbuddy_daily.py.md`） |
| 科研通 AbleSci 每日签到 | `scripts/worker.js` | `node scripts/worker.js` | `9 8 * * *` | 待检查 | [worker.js.md](../scripts/worker.js.md)（`docs/scripts/worker.js.md`） |
| AI打卡机四平台签到 | `scripts/wps_airscript.js` | `node scripts/wps_airscript.js` | `31 10 * * *` | 待检查 | [wps_airscript.js.md](../scripts/wps_airscript.js.md)（`docs/scripts/wps_airscript.js.md`） |
| WPS打卡活动信息 | `scripts/wps_clock_in.py` | `python3 scripts/wps_clock_in.py` | `43 1 * * *` | 待检查 | [wps_clock_in.py.md](../scripts/wps_clock_in.py.md)（`docs/scripts/wps_clock_in.py.md`） |
| 网易云游戏自动签到 | `scripts/wyycg.py` | `python3 scripts/wyycg.py` | `42 1 * * *` | 待检查 | [wyycg.py.md](../scripts/wyycg.py.md)（`docs/scripts/wyycg.py.md`） |
| 小米VIP会员签到 | `scripts/xiaomi_sign.py` | `python3 scripts/xiaomi_sign.py` | `29 8 * * *` | 待检查 | [xiaomi_sign.py.md](../scripts/xiaomi_sign.py.md)（`docs/scripts/xiaomi_sign.py.md`） |
| 喜马拉雅每日签到 | `scripts/xmly.js` | `node scripts/xmly.js` | `10 0 12 * * *` | 待检查 | [xmly.js.md](../scripts/xmly.js.md)（`docs/scripts/xmly.js.md`） |
| 新南方职培学院签到 | `scripts/xnfedu_checkin.py` | `python3 scripts/xnfedu_checkin.py` | `13 8 * * *` | 待检查 | [xnfedu_checkin.py.md](../scripts/xnfedu_checkin.py.md)（`docs/scripts/xnfedu_checkin.py.md`） |
| 学姐吧每日签到 | `scripts/xuejieba.js` | `node scripts/xuejieba.js` | `0 50 11 * * *` | 待检查 | [xuejieba.js.md](../scripts/xuejieba.js.md)（`docs/scripts/xuejieba.js.md`） |
| 益禾堂手机点单 | `scripts/yht.py` | `python3 scripts/yht.py` | `27 2 * * *` | 待检查 | [yht.py.md](../scripts/yht.py.md)（`docs/scripts/yht.py.md`） |
| 羿文教育积分签到 | `scripts/yiwenjiaoyu.py` | `python3 scripts/yiwenjiaoyu.py` | `52 8 * * *` | 待检查 | [yiwenjiaoyu.py.md](../scripts/yiwenjiaoyu.py.md)（`docs/scripts/yiwenjiaoyu.py.md`） |
| 有道云笔记每日空间奖励 | `scripts/youdao.py` | `python3 scripts/youdao.py` | `55 0 * * *` | 待检查 | [youdao.py.md](../scripts/youdao.py.md)（`docs/scripts/youdao.py.md`） |
| 多看阅读 | `scripts/yuxian158_check_duokan.py` | `python3 scripts/yuxian158_check_duokan.py` | `28 2 * * *` | 待检查 | [yuxian158_check_duokan.py.md](../scripts/yuxian158_check_duokan.py.md)（`docs/scripts/yuxian158_check_duokan.py.md`） |
| 阴阳师绘卷时间获取 | `scripts/yyshuijuantime.py` | `python3 scripts/yyshuijuantime.py` | `39 2 * * *` | 待检查 | [yyshuijuantime.py.md](../scripts/yyshuijuantime.py.md)（`docs/scripts/yyshuijuantime.py.md`） |
| ZCode 国内版领套餐 | `scripts/zcode_cn_daily.py` | `python3 scripts/zcode_cn_daily.py` | `1 9 * * *` | 待检查 | [zcode_cn_daily.py.md](../scripts/zcode_cn_daily.py.md)（`docs/scripts/zcode_cn_daily.py.md`） |
| 极核ZEEHO每日签到 | `scripts/zeeho_signin.py` | `python3 scripts/zeeho_signin.py` | `32 8 * * *` | 待检查 | [zeeho_signin.py.md](../scripts/zeeho_signin.py.md)（`docs/scripts/zeeho_signin.py.md`） |
| Zippo会员中心 | `scripts/zippo.py` | `python3 scripts/zippo.py` | `56 0 * * *` | 待检查 | [zippo.py.md](../scripts/zippo.py.md)（`docs/scripts/zippo.py.md`） |
| 知末签到 | `scripts/znzmo.js` | `node scripts/znzmo.js` | `0 55 11 * * *` | 待检查 | [znzmo.js.md](../scripts/znzmo.js.md)（`docs/scripts/znzmo.js.md`） |
| Zodgame签到与广告任务 | `scripts/zodgame_test.py` | `python3 scripts/zodgame_test.py` | `35 2 * * *` | 待检查 | [zodgame_test.py.md](../scripts/zodgame_test.py.md)（`docs/scripts/zodgame_test.py.md`） |
| STC国芯论坛签到 | `scripts/zqlj_sign.py` | `python3 scripts/zqlj_sign.py` | `36 8 * * *` | 待检查 | [zqlj_sign.py.md](../scripts/zqlj_sign.py.md)（`docs/scripts/zqlj_sign.py.md`） |
