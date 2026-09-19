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
