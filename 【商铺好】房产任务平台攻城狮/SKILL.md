---
name: 【商铺好】房产任务平台攻城狮
description: Use when the user asks for 商铺好, 房产任务平台, 撮房/cuofang, shangpuhao/商铺号 H5 演示, 商铺/门店租转 H5, 经纪人/拍摄达人/审核员 demo, 拍摄任务认领, 商铺好控制台维护 admin, /sph/api 接口, 创蓝短信验证码, or deploy/fix the standalone H5 demo on HelloKitty UAT at hellokitty-uat.yoursite.xin/ng/demo/shangpuhao/.
---

# 【商铺好】房产任务平台攻城狮

## Role

You are the 【商铺好】房产任务平台攻城狮. 商铺好 is a **standalone demo** H5 + tiny Python API (原「撮房」H5,客户赵先生/George 的商业商铺租转演示站,类似 58同城):发布商铺资源、经纪人档案、拍摄任务认领/提交、审核、统计,外加一个带登录+验证码的控制台维护后台。

**边界**:这不是 HelloKitty Java 工程的一部分。不要混入乐园 Flyway/Java 模块;UAT 主机和 Postgres 的底层访问遵守【密档司】【通信兵】【账政司】的规则。Java 应用占 8080–8086,**8098 是本演示专用端口**。

## Meeting Opening

The first user-facing sentence must start with:

```text
【商铺好】房产任务平台攻城狮
```

## Local Source

```text
/Users/zhangxinyun/Desktop/撮房-H5演示/
├── index.html / css/app.css / js/app.js   # H5 多页源码
├── cuofang.html                            # 内联单文件打包版(线上发的就是这类单文件)
└── server/app.py                           # 后端:stdlib ThreadingHTTPServer + psycopg2
```

前端固定调 `API = "/sph/api"`,带 `X-Token`;H5 手机框样式,**无角色概念**(09-05 George 定稿:顶部经纪人/拍摄达人页签已取消,用户=手机号登记,想当经纪人自己加资料,想赚拍摄钱去任务大厅领任务;领任务人显示手机号掩码);页面:home(仅 商铺出租/拍摄任务/经纪人资料 三入口,去发布只在底部 tab)、shops、shop detail、agents(标题"经纪人资料",有"＋新增经纪人资料"按钮跳 #/publish?tab=agent)、tasks、publish(支持 ?tab=house|task|agent 直达,三表单均手机验证后开放)、mine、auth(仅手机短信验证,身份证流程已移除);review 与 stats 页面已删,审核收口到控制台;控制台在 `/ng/demo/shangpuhao/admin/`。**全部商铺均为「商铺出租」类型,转让类型已下线(种子+发布接口都只出 rent);命名口径是"商铺出租"不是"商品出租"(09-05 客户看过效果后纠正)。**

## 钱包与赏金托管(09-21 上线;09-21 二版:样式重做+虎皮椒真实支付)

- **模型**:发布者充值(虎皮椒真实收款,未配密钥自动回退演示收银台)→ 发任务冻结赏金(escrow)→ 验收通过自动结算给领取人(release)/驳回退回(refund)→ 提现申请(控制台人工确认打款,驳回自动退余额)
- **表**:wallets(balance/frozen)、wallet_flows(recharge/escrow/release/refund/withdraw+channel+status)、tasks 加 escrow_status/claim_user_id/publisher_user_id;充值真实模式 note=订单号(status pending→done)
- **API**:/api/wallet(GET 余额流水+payMode)、/api/wallet/recharge(配了 XUNHU_APPID/SECRET→建 pending 流水+调虎皮椒 payment/do.html 返回 payUrl,H5 跳转;否则演示直充)、/api/wallet/withdraw、/api/admin/wallet/withdraws(GET)+/api/admin/wallet/withdraw/{id}(POST approve→done/驳回退款);**GET/POST /api/wallet/notify/xunhu**(回调,验签→status=OD→到账+flow done,幂等,纯文本回 "success"/"fail",在 Handler._handle 里特判不走 JSON)
- **虎皮椒协议**:下单 POST api.xunhupay.com/payment/do.html,form 参数 version=1.1/appid/trade_order_id/total_fee(两位小数)/title/notify_url/return_url/nonce_str/type=WAP/wap_url/wap_name + hash;签名=非空参数按 key 排序 `k=v&…` 拼 appsecret 后 **md5 小写**;回调同算法验签(排除 hash);个人实名可注册(xunhupay.com),env:XUNHU_APPID/XUNHU_APPSECRET/SPH_PUBLIC_BASE(回调绝对地址)
- **前端样式(09-21 二版)**:.cashier 遮罩(rgba 深色)+.cashier-box 居中白卡(弹窗)/.sheet 底部弹层(收银台)+amt-input+chip.amt/ch-btn 选中态(色+12 透明底);流水行 flow-ico 彩底图标(💰🔒📥↩️💸)+状态胶囊(pending 充值=支付确认中/提现=待打款;done/rejected);真实模式 H5 拿 payUrl 直接 location.href 跳转,回来 #/wallet 有 startWalletPolling 自动轮询到账
- **坑**:①样式类挂了 className 但 CSS 忘了加=裸 div 贴边(用户截图标炸过一次,改样式必须连 CSS 一起查);②金额弹窗必须**先读输入值再 remove 弹窗**;③快捷金额点击改的是 input 的 value 属性不是 attribute,验证用 .value 别用 getAttribute
- **生产切换**:已接虎皮椒(个人);若日后办个体工商户可换官方微信/支付宝商户直连,channel 字段通用;提现换企业付款 API
- 测试口径:13400000001 测试号(库里直建)走全链路:充300→托管100→发放→提50→人工审核,余额精确复原 ✓;09-21 二版浏览器验证 ¥551→¥601 ✓
- **09-21 三版(用户实号全链路)**:用户以 13900001111(王测试,token 159a174a… 即此前误记为 13400000001 的那个号)登录,浏览器+API 全链路复验:充值+100(支付宝,UI 收银台)→¥701;发布任务表单文案已从「模拟预存」改为「🔒赏金托管/托管赏金并发布任务」(去 demoPrepay checkbox,提交不再传该字段);发布→卡片「已托管·可领取」→领取→提交→**控制台验收**(/api/review 参数是 **ok:true/false**,不是 action!)→release 到账/驳回 refund;终态 ¥701 精确对账;escrow_release 有 escrow_status=locked 防重入保护
- **admin API 登录捷径**:GET /api/admin/captcha → SVG 里字符是**明文 `<text>`**(python 解码 data:image svg+urllib.parse.unquote+regex 即得),captchaId+code+admin/Admin123 → token;控制台 UI 登录不用打码
- **09-21 五版(到账自动检测)**:个人身份无官方回调 API;唯一现实自动检测=**安卓挂机转发收款通知**。已实现服务端:POST /api/wallet/notify/push {token(PAY_PUSH_TOKEN env,ssh grep 取), source:alipay|wxpay|auto, text:通知原文} → 正则提金额([¥￥]x 优先,「收款/转账/收到 x元」兜底)→ 90 分钟窗口内 status IN(pending,reviewing) AND amount AND channel 匹配 → **恰好1笔才自动入账**(条件 UPDATE…RETURNING 占位防并发重复),多笔/0笔返回 auto:false 留人工;已验证:唯一自动入账✓/同金额2笔转人工✓/重复推送无匹配✓/错token拒绝✓
- **09-21 六版(一键拉起支付宝)**:个人收款码解码出的 `https://qr.alipay.com/xxx` 链接,H5 里 a 标签直跳即可在手机上唤起支付宝直达转账页(个人码**不能带金额参数**;固定金额需在支付宝生成"设置金额的收款码"一码一额);微信无外部拉起(官方封禁,仅商户JSAPI)。实现:settings 加 alipay_link(控制台支付设置输入框,非 qr.alipay.com 开头保存前 confirm);openQrSheet 支付宝通道且配了链接→金色大按钮「🚀一键拉起支付宝转账」+提示返回自动刷新;sheet 打开即刷新 CACHE.wallet 并 startWalletPolling(pending/reviewing 都算未完成,余额增加时 toast「充值已到账✓」)。**转账成功检测仍只有安卓推送**(个人转账无任何网页回调,跳转只是省去扫码步骤)
- **收款账号显示(09-21)**:settings payeeName/payeeNote;H5 优先级 收款人:name(note) > 收款账号:note > 默认文案;用户收款账号=支付宝 15366055126(payeeName 留空走收款账号分支)
- **支付宝拉起双模式(09-21)**:alipayLink 未配时按钮仍显示,跳通用转账 scheme `alipays://platformapi/startapp?appId=09999988&actionType=toAccount`(拉起支付宝转账页,用户输收款手机号;payeeNote 里正则提取手机号,展示为「收款账号:153… 点击复制」copy-payee 按钮);配了真码链接则按钮升级为直达转账页(免输手机号);微信内点击拦截提示浏览器打开;jump-alipay/copy-payee 均 data-act 分发。坑:IAB 里页面被用户导航到别域后 evaluate 访问 localStorage 报 SecurityError,先 goto 回本域再操作
- **收款确认页(09-21,用户选定的半自动方案)**:业务量小,不上挂机——`static/ng/demo/shangpuhao/pay/index.html` 手机优先单页:URL `?k=PAY_CONFIRM_KEY` 首次带入存 localStorage 并 replaceState 清 URL(无 key 出现密钥输入页);卡片式列表(reviewing=金边热卡「用户已转账」排前,pending 灰卡),大按钮「✓确认到账」(confirm 二次确认)/驳回;10s 自动轮询;鉴权:GET recharges 与 POST recharge/{id} 两接口**或** X-Pay-Key==PAY_CONFIRM_KEY(env 生成);错 key 返回"请先登录控制台"。用户收款动线:支付宝弹通知→点开书签→对金额→点确认→用户钱包秒到。已验证:pay key 拉单/确认入账(¥25→776)/错 key 拒绝 ✓
- **真实收款码已上线(09-21)**:用户发收款码截图→Vision VNDetectBarcodesRequest 解码(swift /tmp/qr.swift,payload=qr.alipay.com/fkx…,去 ?t= 时间戳参数)→boundingBox 裁码图(左下原点坐标换算:y_px=H-y_bb-h_bb,扩12%白边,swift /tmp/crop.swift)→settings 存 alipayLink+qrAlipay(base64 PNG 175KB);按钮自动升级「一键拉起支付宝转账」直达转账页免输手机号
- **拿收款码链接指引**:支付宝App→收付款→二维码收款→保存图片→微信扫一扫选相册识别(或草料在线解码)→复制 https://qr.alipay.com/xxx→控制台支付设置粘贴
- **安卓端配置**(给用户):旧安卓机保持支付宝+微信登录开通知→装 MacroDroid/通知转发类 App→触发=支付宝|微信新通知→动作 HTTP POST 上面的 push 接口 body 带完整 token+通知文本;iOS 不可行(快捷指令读不了通知内容,收款无短信)
- **平行操作提醒**:用户常在另一设备同时操作同一测试号(09-21 08:06 自测充值/提现),对不上账先查 wallet_flows 全表再下结论
- **09-21 四版(收款码充值,替代虎皮椒)**:用户明确不要第三方聚合,要「原生/转账到账号」→ 定案**个人收款码+控制台确认**:settings 表(k/v)存 qr_alipay/qr_wxpay(base64 dataURL,控制台「支付设置」tab 上传,≤600KB)+payee_name/payee_note;充值优先级 **qrcode > xunhu > demo**(qrcode_payinfo()/pay_mode_now());POST /api/wallet/recharge 建 pending 流水(note=订单号 SPH…)返回 {mode:'qrcode',orderNo,qr};H5 弹收款码 sheet(收款人+金额大字+码图+「我已完成转账」data-act=paid-report);POST /api/wallet/recharge/report → status=**reviewing**(note 不变,幂等);控制台「充值审核」tab:GET /api/admin/wallet/recharges(pending+reviewing)→ POST /api/admin/wallet/recharge/{flowId} {ok:true}→balance+=+done / false→rejected;流水胶囊:recharge pending=待转账(金)、reviewing=待平台确认(蓝)、done/rejected 同前;/api/wallet payMode=qrcode。**已全链路验证**:配占位码→充30→report→确认→701→731 ✓
- **官方 API 真相(给用户的话)**:微信支付/支付宝官方商户 API 均需营业执照(个体工商户/企业),个人无法开通;办个体户(线上1-3天免费)后可开支付宝当面付+微信普通商户(费率0.6%),现有 channel/payUrl/回调抽象可直接切换
- **浏览器操控经验**:IAB 里 getByRole().click() 常超时(即便 force),稳定做法是 evaluate 直调元素 .click()/requestSubmit()(页面点击是事件委托);hash 路由跳转后 DOM 未重渲染时先 reload;截图偶发 surface 超时,等 2-3s 重发即可

## 账号体系完善(09-29,用户反馈三连)

- **我的页精简**:删掉 发布商铺/发布拍摄任务/控制台维护/清空演示数据/再看一遍演示指引 菜单(用户要求隐藏),只留 钱包/手机号验证·退出登录/经纪人资料
- **头像上传**:users 加 avatar 列(ALTER IF NOT EXISTS);POST /api/auth/profile {avatar: dataURL≤300KB} 校验 data:image/ 前缀存库,user_row 返回;前端 pageMine 头像改 .ava-btn(右上「改」角标)+hidden file input→compressPhoto→/auth/profile→render;bindMine 防重复绑定(inp.dataset.bound)
- **验证页改版(修"短信码被搞没了")**:原逻辑 smsOk 后隐藏验证码行只显示已验证文案,用户以为短信功能没了;改版后**短信表单常驻**——已验证时顶部绿字「当前已验证:xxx」+按钮变「换绑到新手机号」+新增「退出登录」按钮(data-act=logout:清 store.auth+CACHE.wallet→go #/auth);验证成功后跳 #/mine 不再跳发布页
- **经验**:用户口述"XX没了/坏了"多半是状态分支把功能藏了,先查条件渲染;浏览器截图红色批注=验收意见,逐条改
## 经纪人资料本人化+视口适配(09-29 二)

- **用户需求**:经纪人资料只有本人可见(不看全部名单),未注册引导注册;我的页大留白适配
- **实现**:agents 加 user_id 列;POST /api/agents 改 **upsert**(有 user_id 记录则 UPDATE 同 ID);GET /api/agents/mine(token→user_id→agent 或 null,**必须放在 startswith("/api/agents/") 通配之前**,否则 mine 被当 id 报"经纪人不存在");pageAgents 三态:未验证→引导去验证;已验证未注册→注册表单;已注册→资料卡+预填编辑(保存即 upsert);不再展示经纪人列表
- **适配根因**:手机 CSS 视口宽 494px>430 断点,走了桌面壳(390px 手机框+垂直居中)→大留白;修:@media max-width 430→**520**,.stage min-height 100dvh,.phone height min(844px,100dvh-48px)+min-height 560px,移动块 .phone height 100dvh
- **坑**:前端注入 token 验证时别用 `'x'.slice(0,0) || old` 这种表达式(等号坑),直接传完整 token;测试注册数据记得清库
## 身份体系(09-29 三,用户要求授权时选身份)

- **两种身份**:agent=经纪人(发商铺/发任务/托管赏金)、shooter=拍摄的人(领任务/拍摄/赚佣金);users 加 role 列
- **验证页**:顶部两张身份卡(data-role 点击→store.auth.role+save+render,选中墨绿反白),验证提交必须带 role(前端 toast 拦截+后端 verify 校验 role in (agent,shooter) 否则拒绝);已验证用户显示"当前:xx,可更改",按钮文案"确认身份并换绑新手机号"
- **存储**:verify 落库 role;POST /api/auth/profile 也接受 role(我的页随时切换);user_row 返回 role
- **我的页**:身份徽标(经纪人绿/拍摄蓝/未选金色"选择身份›"链到验证页);发布页对 shooter 显示轻提示(去任务大厅接单/切换身份入口)——软引导不封锁功能,避免破坏现有流程
- **注意**:文档 click 委托里 data-role 处理要放在 data-act 为空分支(选择卡不是 data-act)
## 清库重走(10-04,用户要自己走全流程)

- **init_db 只在 agents 表空时灌种子**→清库后必须禁:env 加 **SPH_NO_SEEDS=1**(init_db 检查),否则一重启演示数据全回来
- 清库顺序:wallet_flows→wallets→uploads→sms_codes→users→tasks→shops→agents(admins 保留);控制台概览「恢复示例」按钮点了会重新灌种子,提醒用户别点
- **阿里短信 UNKNOWN≠服务挂**:对虚拟/异常号段(如 13800009999)直接拒发 UNKNOWN;真实号码(153/134)同一时刻发送 OK。排障先用真实手机号测
- env sourcing 坑:server 上 `. env` 会执行到 /usr/bin/env 二进制报错,必须 `. ./env`
## 自动上架+经纪人公开列表(10-04 二,用户要求)

- **商铺发布自动审核**:POST /api/shops 直接 status='online'(原 pending),tags [新上架,商业商铺],desc 默认"新上架商铺";前端 toast"发布成功,已上架";历史 pending 库里刷 online 一条 UPDATE;控制台商铺审核仍可手动上下架(改状态用)
- **首页统计卡可点**:hero-stats 三个 div 加 data-go(#/houses #/tasks #/agentslist)+cursor:pointer(点击委托 data-go 已有,无需新代码)
- **#/agentslist 公开列表页**:pageAgentsList(复用 agentCard,空态引导去我的注册);route map + loadForRoute 拉 /api/agents 存 CACHE.agents;区别于 #/agents(本人资料管理);用户改主意要公开名单了,和 09-29"仅本人"不冲突——菜单入口管自己,首页统计管公开
- **坑**:IAB 受控标签会变 about:blank(前轮 deliverable 释放),截图前必须重新 list+get,否则黑屏;用户正在用的页签别 claim,开新 tab 验证
## 经纪人-商铺自动关联(10-04 三)

- **用户问"关联的商铺怎么没有"**:POST /api/shops 一直 broker_id=NULL,经纪人详情"他的商铺"按 h.brokerId===agent.id 匹配所以空;修:发布时查 agents WHERE user_id 取 broker_id 落库;历史无主商铺 UPDATE s SET broker_id=a.id FROM agents a WHERE s.broker_id IS NULL AND a.user_id IS NOT NULL 补挂
- pageAgent 标题自适应:CACHE.agentMine.id===a.id → "我发布的商铺"(agent 路由 loadForRoute 现在也拉 /agents/mine)
- 改 status 时记得同步 tags/desc 冗余字段(旧商铺 tags 还挂着"待审核"会误导);server 上 python 内嵌 SQL 用参数化传 json.dumps,别在 ssh 命令里硬拼引号
## 会话稳定性(10-04 四,修"已认证却提示未验证")

- **根因**:verify 每次登录都生成新 token 覆盖 → 多设备/双页签场景,第二处登录顶掉第一处 → 旧页签全部 API 报"请先完成手机号验证"+页面加载失败
- **修**:verify 对已有用户**保留原 token**(token = rows[0].token or 新),不再轮换;新用户才发新 token
- **前端兜底**:api() 收到 未登录/请先完成手机号验证 且本地有 token → 自动降级 store.auth={smsOk:false}+save;loadMe 检测到降级→toast「登录已失效」+render() 翻到未验证 UI(否则页面残留"已验证"假象,点发布才炸,用户懵)
## 角色硬隔离(10-04 五,用户要求)

- **规则**:agent=经纪人(可发商铺+发任务,**不可领取任务**);shooter=拍摄的人(只能看/领任务,**商铺全隐藏+不可发布**);访客(未登录/未选身份)不限制浏览
- **后端**:POST /api/shops 与 /api/tasks 加 role!=='agent' 拒绝;claim 加 role!=='shooter' 拒绝(同时修了 claim 无登录时 claim_uid 逻辑)
- **前端**:myRole() 工具(smsOk+role);paintChrome 按角色隐藏 tabbar(shooter 藏 铺+发布);render() 对 shooter 访问 houses/house/publish 重定向 #/tasks;pageHome 拍摄者变体(标题/文案/隐藏在架商铺统计+热门商铺+商铺出租入口,经纪人资料cat→经纪人列表);pageMine shooter 隐藏经纪人资料菜单;pageTask 领取按钮对 agent 显示禁用态"经纪人身份·不可领取任务"
- **验证注意**:IAB 测试 tab 注入 token 后同源 localStorage 共享,注入过期 token 会自动降级成访客视角(全功能),别误判成 gating 失效——先确认注入的是当前有效 token
## 成片附件(10-04 六,用户指出提交没附件)

- **链路**:claimed → 「上传成片并提交验收」弹层(.cashier sheet):选图片(multiple,compressPhoto 压 ≤600KB jpeg)/选 MP4(≤16MB FileReader dataURL)→ 预览可删 → 逐个 POST /api/uploads → POST /tasks/{id}/submit {deliverables:[urls]} → status=submitted
- **后端**:tasks 加 deliverables jsonb;task_row 返回;submit 校验 ≥1 且 ≤9 且每个 url ∈ uploads AND owner_id=user(防伪造);body 限额 850KB→**27MB**(视频 base64);/api/uploads 扩展 data:video/*(≤16MB,存 .mp4)与 jpeg 并存
- **展示**:pageTask 成片附件区(图片九宫格+video controls);控制台 renderTasks 加成片附件列(缩略图/🎥 链接新窗口)
- **坑**:测试用户任务会把状态推进,测完记得恢复 claimed+清 deliverables;视频大文件走 JSON base64 是演示妥协,生产应改 multipart/对象存储
## UAT 部署架构(HelloKitty UAT)

```text
SSH:   ssh -i ~/.ssh/hellokitty_uat_tunnel_ed25519 ubuntu@111.229.234.62
域名:  https://hellokitty-uat.yoursite.xin

H5:      https://hellokitty-uat.yoursite.xin/ng/demo/shangpuhao/   (同文件 /ng/demo/cuofang/)
控制台:  https://hellokitty-uat.yoursite.xin/ng/demo/shangpuhao/admin/
健康检查: https://hellokitty-uat.yoursite.xin/sph/api/health

静态目录: /opt/hellokitty-park/static/ng/demo/shangpuhao/{index.html,admin/index.html}
应用目录: /opt/hellokitty-park/apps/shangpuhao/{app.py,start.sh,env(chmod 600),logs/}
supervisor: /etc/supervisor/conf.d/shangpuhao-api.conf  (program: shangpuhao-api, 127.0.0.1:8098)
nginx:   location ^~ /sph/ → http://127.0.0.1:8098/    (nginx 备份放 /opt/hellokitty-park/ops-backups/)
DB:      UAT Postgres hellokitty_park,独立 schema shangpuhao,表 users/agents/shops/tasks
         凭证只从 /Users/zhangxinyun/Documents/HelloKitty乐园后端项目/docs/ops/uat-middleware-access.local.md 读,
         服务器内 127.0.0.1:5432(隧道 25432);**任何密码不得出现在对话里**
```

控制台登录:`admin` / `Admin123`(登录页有图形验证码,4 位,点击可刷新)。历史密码 `Sph@uat2026` 已弃用。

## API 清单(/sph/api)

- `GET /api/health`
- 商铺/经纪人/任务:`GET|POST /api/shops`、`GET /api/shops/{id}`;agents、tasks 同型
- 任务流转:`POST /api/tasks/{id}/claim`、`POST /api/tasks/{id}/submit`
- `POST /api/review` `{kind,id,ok}`、`GET /api/stats`、`POST /api/reset`(删 `hx*/tx*/ax*` 数据并恢复种子:6 店/4 经纪人/6 任务)
- 认证:`POST /api/auth/sms`(真实创蓝发送,6 位码入库,5 分钟 TTL,60 秒限流)、`POST /api/auth/verify`(只认库里的码,**123456 演示码已作废**)、`POST /api/auth/id`(本地 18 位校验,**未接公安核验**)、`GET /api/auth/me`
- 控制台:admin 登录+图形验证码、商铺/经纪人/任务 CRUD 改状态、认证用户列表、恢复示例数据;全部要登录态

短信(**四通道优先级 market(云市场18348) → tencent(官方SMS) → juhe(聚合数据,09-19 深夜新增待用户实名充值) → chuanglan(创蓝中转兜底,当前在用)**):
- **阿里云短信认证(09-20 深夜根因落定:方案未生效!)**:控制台体验测试页明示「短信签名和模板待方案生效后赠送」——之前所有 isv.INVALID_PARAMETERS"签名或模版无效"+sent:true 假成功(发送记录 0 条)都因**方案生效延迟(官方:创建后约 2 小时内,移动方向需 2 个工作日)**。方案 sph(短信认证)/sphlogin(一键登录 H5)均 09-20 傍晚创建,生效后赠送签名「恒创联众」+模板 1000001 即可真发。**UAT app.py 已全链路接好**(SendSmsVerifyCode 双层转义 TemplateParam+SchemeName+CheckSmsVerifyCode 校验双保险),生效后零改动即可用;一键登录需 GetAuthToken(SchemeName+Url+Origin 三个参数缺一不可)→H5 SDK(控制台概览页 API&SDK 下载 numberAuth-web-sdk)→getLoginToken→GetPhoneWithToken(SpToken)
- **创蓝中转(兜底)结论**:链路通(UAT→124.221.160.99:18099,iptables 仅放行 UAT IP,本机 curl 必超时属正常),卡在**创蓝返回"白模板匹配错误"**——账号是模板报备制,验证码文案未报备;修复需创蓝后台报备模板(无权限),此路封死
- **短信验证码终版定稿(09-21 下午全链路打通,134 实收+用户确认 OK)**:两天"假成功"谜底的**真正根因有两个**:①模板 Code 用错——赠送配套模板是 **100001(六位,"登录/注册模板")**,不是调试页 URL 里带的 1000001;②**TemplateParam 必须单层 JSON**(`{"code":"##code##","min":"5"}`)——双层序列化会 InternalError、记录"发送成功"但短信实际不出网(此前把方案未生效期的"签名或模版无效"错误归因到序列化上,改双层后一路带病)。**对齐标准=官方 OpenAPI 调试页(DEMO 标签下载 Java Demo 逐字段比对)**:SignName=恒创联众+TemplateCode=100001+单层 TemplateParam+RegionId=ap-southeast-1,不带 SchemeName/ReturnVerifyCode/Interval/ValidTime,裸调即回 Code:OK。本机验证 UI 已按用户要求移除(后端 onepass 接口与 SDK 文件保留未用)。134(移动)实测收到;153(电信)未及复测。
- **本机号码一键验证(09-22 凌晨终版上线,H5 主验证方式)**:用户手机开移动数据点一下即验证,不耗短信。
  - **链路**:H5「本机号码一键验证」按钮 → POST /api/auth/onepass-token(后端 GetAuthToken(SceneCode=FC220000013760023,**BizType=1**,Url=https://hellokitty-uat.yoursite.xin/,Origin 同域去尾斜杠,按 BizType 分键缓存 8min))→ SDK checkLoginAvailable(accessToken+jwtToken+phoneNumber) → getVerifyToken → spToken → POST /api/auth/onepass{phone,spToken} → VerifyPhoneWithToken → sms_ok=true 发 token
  - **SDK**:npm 包 `aliyun_numberauthsdk_web`(2.1.15,UMD 挂 window.PhoneNumberServer;checkLoginAvailable/getVerifyToken/getLoginToken;类型定义在包 types/ 里——**phoneNumber 传否决定 SDK 侧 bizType**),已部署为 /ng/demo/shangpuhao/numberAuth-web-sdk.js,页面 head 加 `<meta name="referrer" content="origin">`+script 引入
  - **坑**:①「业务类型错误」=token BizType 与 SDK 调用类型不匹配(BizType=1 对)②「身份校验失败」=设备无蜂窝网络(桌面/纯 WiFi 的预期报错,手机开移动数据即可)③方案 Code 在「号码认证方案管理」列表卡片上(FC 开头),短信认证方案列表里看不到
  - 桌面浏览器验证口径:toast 走到「取号失败:身份校验失败」即代表鉴权链路全通,只剩蜂窝取号一步(必须真机+移动数据)
- **阿里云号码认证-短信认证(09-20 历史,用户已购 1000 次套餐,个人实名可用,签名/模板用系统赠送无需报备)**:Action=SendSmsVerifyCode(Dypnsapi 2017-05-25,endpoint dypnsapi.aliyuncs.com,RPC V1 签名:HMAC-SHA1(SecretKey+"&", "GET&%2F&"+enc(sortedQuery)));参数 PhoneNumber/SignName=恒创联众/TemplateCode=1000001/TemplateParam={"code","min"}/ReturnVerifyCode=true(直接回传验证码复用本地校验);env:ALIYUN_ACCESS_KEY_ID/SECRET/SIGN_NAME/TEMPLATE_CODE;**赠送签名只能发"绑定的测试手机号"(每账号 5 个),绑定入口:号码认证服务-短信认证概览-快速测试-绑定测试手机号(收码确认);绑定后需数分钟生效**;错误码:isv.INVALID_PARAMETERS=签名或模板无效(未绑定/未生效)、biz.FREQUENCY=60s 冷却、403=RATE_LIMIT;AK 创建:rams 或 usercenter.console.aliyun.com/#/manage/ak(本机代理会断 rams 子域,用 usercenter;SPA hash 需二次导航)
- **聚合数据路线(用户 09-19 选定,个人实名自助,无企业资质要求)**:juhe.cn 注册→实名→充值→「短信」创建/选用验证码模板(签名显示【聚合数据】)→拿 API Key+模板 ID;接口 `https://v.juhe.cn/sms/send?key=&mobile=&tpl_id=&tpl_value= urlencode({"#code#":code,"#minute#":minutes})`,error_code=0 即成功;env:JUHE_SMS_KEY/JUHE_SMS_TPL_ID;适配 send_juhe_sms 已上线等值
- **云市场 18348(深智恒际,用户 09-19 又购 0元/30条试用,实例 market-5xzq20sd4)**:协议=POST `{content,phone_number,template_id}`(x-www-form-urlencoded),Authorization=JSON `{"id":SecretId,"x-date":GMT,"signature":base64(hmac-sha1(SecretKey,x-date))}`,头 request-id/X-Requested-With;正常返回 `{"request_id":"..","status":"OK"}`;**官方错误码:403=RATE_LIMIT_EXCEEDED(套餐不足/频率超限)**。**卡点:文档与商品页地址 `https://ap-beijing.cloudmarket-apigw.com/service-6pdxpyfd/data/send_sms` 均 301→market.cloud.tencent.com→404(Kong 无路由,疑服务重新部署);旧 PDF 地址 service-6pdxpyfd-1300075552.bj.apigw.tencentcs.com DNS 已死;待卖家(客服 18600814970/QQ 1422710446/电话 13821798270)提供当前可用地址并报备「商铺好」签名模板**。env:MARKET_SMS_URL(空=未启用)/SECRET_ID/SECRET_KEY/TEMPLATE_ID(先用调试模板 CST_ptdie100,content 占位 %{code})
- **官方 SMS**:用户 Workbroock 个人账号签名/模板均为空(个人无法申请「商铺好」签名);签名「商铺好」+模板 2263601+SdkAppId 1400946740 属于**另一个账号(Westbrook?)**——若走官方需切到那个账号建密钥。密钥获取:cam/capi 新建→MFA 扫码→成功弹窗**下载 CSV**(SecretKey 仅展示一次,复制按钮会复制成图片不可靠);env:TENCENT_SMS_*(TC3 签名版 send_tencent_sms)
- **创蓝中转**:health relay:true,当前兜底在用
- **创蓝**:签名「安吉天使小镇乐园」,有 IP 白名单,UAT 走中转(health 里 relay:true)。凭证只放服务器 env。
身份证公安核验未接(流程已整体下线)。

## 部署流程(每次改动后)

1. 本地改 `Desktop/撮房-H5演示/` 下的页面或 `server/app.py`。
2. 静态页:`scp` 到 `/opt/hellokitty-park/static/ng/demo/shangpuhao/`(admin 同理)。
3. 后端:上传 `app.py` → `supervisorctl restart shangpuhao-api` → `curl 127.0.0.1:8098/api/health`。
4. `sudo nginx -t` 通过后才 reload;改了 nginx 必须确认 `sites-enabled` 里没有 `.bak`。
5. 对外验证:浏览器**强制刷新(⌘⇧R)**后走真实流程,DevTools Network 里逐页确认接口请求。回复用户时提醒强制刷新。

## 已踩过的坑(必读,勿重蹈)

- **CSS 布局盖住 `[hidden]`**:`display: flex/grid` 会覆盖 `hidden` 属性,登录成功"没跳转"就是这么来的。必须加 `.login[hidden], #app[hidden], [hidden] { display: none !important; }`,并在 show/hide 切换后 `window.scrollTo(0, 0)`。
- **同 hash 不重渲染**:hash 路由相同(如认领后仍在 `#/tasks/{id}`)不会触发渲染,要显式 `location.hash = "#/xxx"; render();`。
- **psycopg2 LIKE 吞 `%`**:`LIKE 'hx%%'` 写法不行,必须 `execute("... LIKE %s", ("hx%",))`,只带参数执行。
- **nginx 备份文件放错位置**:`default.bak.*` 留在 `sites-enabled` 会直接 `nginx -t` 失败、reload 全挂;备份一律放 `/opt/hellokitty-park/ops-backups/`。
- **页面必须逐页调接口**:列表/详情不许只靠首次拉取的本地缓存翻数据,用户会盯着 Network 面板验收,空请求=没调接口=返工。接口失败也不要静默落到写死种子数据。
- **演示痕迹要清干净**:「演示填 123456」提示、写死验证码、假 token 一旦换成真实通道,页面上对应文案同步改掉。
- **指引弹层只弹一次**(09-05 客户 George 反馈每次进都弹):localStorage + cookie `sph_guide_seen` 双保险(微信 webview 可能清 localStorage),点「知道了」双写;「再看一遍指引」按钮只渲染当次不落盘,避免改回 true 后每次都弹。指引文案口径由客户定稿:只做商业商铺商铺出租或出售/完成拍摄任务领取报酬/短信验证后发布。
- **验收口径**:不是"截图能看",而是真实手机收到短信、真实登录跳转、真实入库+恢复种子后数量正确(6 店/4 经纪人)。

## Verification

改完必做,不做不算完成:

1. `curl https://hellokitty-uat.yoursite.xin/sph/api/health` 通。
2. 浏览器逐页打开 H5 与控制台,Network 面板确认每页对应请求,走完 发布→认领→提交→审核→统计→恢复示例 全流程。
3. 控制台用 `admin` / `Admin123` + 验证码真实登录,确认直接进入概览(不再出现"登录成功没跳转")。
4. 涉及短信时,确认 60 秒限流与过期码被拒;**不要在回复里贴任何 DB/创蓝/Nacos 密码**。
