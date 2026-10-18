# Chen Cook 当前交接

## OSS V4签名修复（2026-10-18 08:44 +08:00 后）

- 用户真实服务器诊断明确返回AccessDenied/403、Message="V1 signature is forbidden."、EC=0002-00000080。本次根因是代码使用oss2.Auth旧签名，被OSS拒绝；不能继续让用户重复授权或更换密钥。此前根据灰色复选框推断未授权已纠正，用户已确认新增授权。
- 依据阿里云Python SDK官方初始化文档，将唯一共享bucket_client改为oss2.AuthV4并明确region='cn-qingdao'，已有OSS设置格式与凭据不变；列表、导入下载、原PDF HEAD/Range读取都会使用该客户端。依赖已固定oss2==2.19.1，无需更换SDK包。
- 新增真实SDK签名回归，HTTP发送方法完全拦截，无外部OSS访问；验证ListObjects、HeadObject、GetObject Range都产生OSS4-HMAC-SHA256和青岛地域scope，避免旧测试只mock业务入口而漏掉签名不兼容。
- 另建chen-cook-v4工作区，基于936c21784cfb41ea91274d4fb1252e36f9b7af2b；旧工作区改动保留。提交前执行本地测试，提交后核对CI与公网revision。用户密钥从未发送到聊天，也不获取生产密钥；真实OSS连通需用户网页刷新验证。

## 直接阅读源PDF（2026-10-17 23:01 +08:00 后）

- 用户放弃重排阅读，明确要求直接读源文件。默认“开始阅读”、目录条目和搜索结果改为登录保护的/books/{id}/source.pdf；浏览器接收OSS原PDF字节，排版/文字/图片全部不变，不再以低分辨率JPEG或OCR重排作为主阅读入口。旧两种网页阅读路线仍保留兼容链接，但不在详情页推荐文字重排。
- 新增source_pdf.py：只读OSS head/get，按256KiB块转发，不存原PDF到服务器磁盘，不跑PDF渲染/OCR，不暴露AccessKey或签名地址。支持HEAD、完整GET、单段Range、206/416、ETag/Last-Modified与If-Range；默认Content-Type application/pdf和Content-Disposition inline，所有请求继续走登录保护。OSS未配置时进入网页设置；读取错误不回显SDK敏感信息。使用现有bucket_client与现有配置，不擅自迁移凭据或改代理/域名/worker。
- #page=N只作为浏览器定位提示，不能保证所有iPhone内置PDF查看器支持；原PDF阅读进度由浏览器/阅读软件管理。旧网页进度按钮改为“从上次页码打开”，明确仅是此前记录，不虚称可以读取浏览器原生PDF阅读进度。
- 测试OSS完全模拟，验证原PDF全部字节相等、HEAD无下载、Range区间和后缀范围、无效范围、If-Range、鉴权、错误脱敏、无OSS配置与入口。浏览器验收验证主阅读入口/目录的源PDF地址和实际PDF响应，保留旧网页阅读器作为兼容回归；不把headless中的HTTP验证声称为真实iPhone原生PDF查看器验收。
- 基于83568b78c0c1d1ac4f778ed83a6ebb5c58b7ad6e；用户22:33问自动更新延迟时公网已直接返回83568b7且CI成功，上一节“部署阻塞”已解除，原延迟原因未取得服务器日志，不作推测。此次另建chen-cook-source worktree，旧工作区修改不动。源PDF版本提交后须核对CI和公网revision，再记录上线。
- 已提交源PDF功能9f2abc1d2fd46c80462ace8b756192fe9282e3c8，GitHub CI39043581167/job117427760865于23:08:07 +08:00成功，本地/CI均16项测试通过；Chromium/WebKit四尺寸源PDF入口、完整原文件字节、HEAD/206范围响应与旧阅读器回归通过，截图制品12105216187。未验证生产真实OSS凭据、真实原PDF读取或iPhone原生查看器，不能混淆验收范围。
- 公网在23:10–23:11 +08:00多次核对仍是83568b7，旧服务正常，本次源PDF版本尚未确认上线。无SSH可读取更新器状态；不猜测具体延迟原因。用户可立即部署已通过CI的明确版本：git -C /opt/chen-cook fetch origin main && bash /opt/chen-cook/scripts/deploy.sh 9f2abc1d2fd46c80462ace8b756192fe9282e3c8。原deploy脚本会检查本地修改、备份书库、只快进源码、重启独立服务并健康检查；不重装、不删数据。若自动更新已先完成则无需再执行。更新后在书刊详情点“开始阅读”，首次未配置OSS会转网页设置，凭据只在用户网站填写。

## 舒适阅读版（2026-10-17 22:13 +08:00 后）

- 用户新版截图确认布局已更新，但整页双栏图片字体小、放大模糊；用户要求实现电子书式阅读，并同意继续。独立站新增mode=comfort，原版默认与原图片保留，不重新挂回小助手。
- 基于已有文字重排，不在Web请求中跑OCR/PDF处理，不重新下载OSS；样书已有98页OCR及坐标审计。reflow.py只读保留的reading_order，过滤明显竖排边栏与孤立底部页码，合并断行，按几何字号分标题/正文与步骤开段；不修改或猜测任何配方/数字，低置信度点线提示。无审计时保守使用已有文字；无文字明确提示原页，不虚构。
- 文字版默认20px，支持16–30px、行距、黑体/宋体、纸色/纯白/夜间；设置与模式/页码只保存当前浏览器。保留页码跳转、目录、专注模式和原页对照链接。连续向下滚动按需获取私有flow JSON，更新当前PDF页码与继续阅读；失败/登录过期可见提示，空白页避免无止境自动加载。
- 本次是OCR重排试读，不是人工校对EPUB：原有OCR错字不会自动修正；配图、表格、复杂版式仍在原页，未自动抽图；PDF跨页可连续阅读但保留页界标识，尚未做可靠章节语义合并。扫描新书无文字时仍需后续独立worker识别流程。不得声称全库已转换或高精度识别已完成。
- 本地13项单元测试、语法检查通过；在私有样本副本对98页全部走geometry重排，分离177项边栏/页码，第9页左末到右首断词接续及示例数量检查通过，数据库SHA前后相同。没有向公开仓库提交任何真实书刊内容、目录、PDF、数据库或凭据。
- 基于18dd7c32a2d043d1e3574a2245dffc49f4f22021（CI39039176725成功）；新增worktree chen-cook-comfort，不触碰旧两个工作区的未提交修改。提交后继续核对Chromium/WebKit手机桌面原版+文字版真实验收与公网revision；当前段未宣称此版已上线。
- 已提交a948b430c0347062554b728b1cc1b0db419c5495，CI39040316379/job117418264426于22:21:48 +08:00成功：13项单元测试及两引擎四尺寸原版/文字版交互、字体/行距/背景持久化、连续加载、页码/模式继续阅读全部通过，16张合成样本截图制品12103802270。自动更新器所用公开GitHub过滤接口已直接核对能返回该成功push/main提交。
- 部署阻塞：22:24:48 +08:00多次公网HTTPS /health（含不同query排除缓存）仍为18dd7c32a2d043d1e3574a2245dffc49f4f22021，旧站正常；不能声称文字版已上线。没有服务器SSH，无法读取systemd日志确认自动更新是等待、网络、限流还是其他原因，不作猜测性生产改动。下一步请用户执行journalctl -u chen-cook-update.service -n 60 --no-pager提供只读日志，再有针对性处理；不重装，不清数据，不改Caddy或其他模块。

## 当前状态（2026-10-17 21:53 +08:00 后）

- 用户浏览器截图已确认 cook 域名可登录并打开迁移样书第2页；不能再按“未安装/未上线”处理。用户反馈阅读体验极差：旧版导航、标题、表单占满首屏，原页在屏幕底部，目录显示0。
- 本次仅调整独立阅读器：移除阅读页管理导航，52px手机顶部栏、全宽原页、固定底部翻页；目录/跳页/缩放/文字收进原生dialog；支持专注模式、左右滑动翻页、桌面方向键，保留双指缩放且放大/多指/斜向滚动不触发翻页。图片失败显示重试。独立reader.css只用于阅读页，不改变管理页、数据、OSS、worker或部署服务。
- 目录0是未录入，不是前端丢失：该扫描样书无PDF书签，之前47项目录JSON尚无生产导入证据。新目录弹层明确解释并链接现有网页录入/JSON上传；不得把私人目录提交公开仓库，也未擅自修改生产数据。
- 验证新增正文起点<=56px、手机全宽/桌面960px、底栏高度、缩放内部横向滚动不撑破页面、原生弹层、专注恢复、手势保护、页码边界、继续阅读。CI保留原320/390/768/1440全流程，增加WebKit相同尺寸与测试截图制品；测试PDF为合成样本，不含私人书刊。提交前本地单元、语法检查，提交后须核对真实CI结果。
- 服务器已启用按分钟拉取通过CI的main的update.timer。本次没有生产SSH权限；自动更新后的实际revision与用户手机复验仍需独立确认，不以GitHub提交代替上线证据。
- 工作基于main c70c9dea1bdfc87fad8808f906453ba79a949097（CI39034294581成功），新worktree chen-cook-reader；旧chen-cook目录的未提交改动保留不动。
- 已验证结果：阅读器功能提交442d9ed28a9ff9f3b479e24efea7e28d19e1e8b9；本地9项测试及Python/JS/Shell检查通过。GitHub CI39038977708/job117414406417全部success，Chromium与WebKit均完成320/390/768/1440全流程，8张合成样本截图已保存为reader-browser-screenshots制品（12102534011）。公网HTTPS /health已直接返回ok=true/service=chen-cook/revision=442d9ed28a9ff9f3b479e24efea7e28d19e1e8b9，确认自动更新已部署本次功能；无需用户重新安装。尚未取得用户真机对新版手势/浏览器工具栏的复验，WebKit自动化不等同于真实iPhone系统验收。

## 历史过程（以下“待安装”等为当时状态，以当前状态为准）

- 最新证书证据（2026-10-17 20:52 +08:00）：用户截图的本地health为ok=true/version0.1.0/service=chen-cook/revision=a45f7a75074fc13b516fa9f99deda807b41344bb。Caddy对cook.ziboxiaozhushou.cn的HTTP-01验证成功，authz_status=valid，日志明确certificate obtained successfully（Let’s Encrypt），证书已取得；先前TLS失败出现在初始申请阶段，不再按证书未签发排查。尚未收到公网HTTPS health重试或浏览器登录/书刊体验证据；本会话网页查询工具无法访问health，不能将工具失败等同网站失败。下一步用户直接打开https://cook.ziboxiaozhushou.cn并用已在服务器设置的密码登录，核对样书封面、原页与目录。未读取密码或真实OSS凭据。


- 最新生产证据（2026-10-17 20:50 +08:00）：用户20:48首次安装截图显示独立账户已保存、旧样书数据库与预览复制成功且原库未改变，本地独立站健康检查成功并输出revision911a9731c4054791db3573d495d568fa67443332。Caddy validate成功，已将cook主机追加到/opt/sms-relay/Caddyfile并reload，备份/opt/sms-relay/Caddyfile.chen-cook-backup-20261017-204805；Web/worker/update.timer已enable。公网HTTPS curl失败(35) tlsv1 alert internal error，不能确认已上线。下一步只读核对cook域名A解析、Caddy的ACME/证书日志；不盲目改上游或现有主站配置，不以格式警告为故障。尚未验证浏览器登录或真实OSS设置。


- 安装阻塞证据（2026-10-17 17:33 +08:00）：用户截图显示新版configure.py已使用“密码不能为空”规则，但hash_password收到空字符串并退出；之后用户在root shell提示符输入文本，被当作命令并提示command not found。未保存账户配置，也无服务/HTTPS完成证据。下一步重新运行bootstrap，等待隐藏输入密码提示后输入非空密码并回车，再确认一次；不要在shell提示符下直接输入密码。不记录或复述截图中出现的敏感输入。


- 最新要求（2026-10-17 16:11 Asia/Shanghai）：用户取消密码至少12位限制。安装账户只拒绝空密码，短密码可生成哈希并登录；安装提示同步修改，现有密码与哈希算法保持兼容。本地8项测试以短密码运行验证，提交后核对CI。用户16:09截图已克隆仓库并启动bootstrap，尚无密码设置/服务启动/HTTPS完成证据。若旧安装脚本正在运行，须终止旧进程后拉取新版再重试；不删除已有账户配置或数据。

- 日期：2026-10-17（Asia/Shanghai）。用户要求在新建zc202302-lab/chen-cook独立仓库重新完成部署，域名cook.ziboxiaozhushou.cn；小助手内资料库已通过旧仓库PR #161移除，但用户尚未反馈那次现网移除结果。
- 仓库起点为空，无历史AGENTS或活动PR。独立站首版代码与CI验证完成，等待青岛首次安装和真实业务验证。复用旧阅读器与独立SQLite结构，已重新实现独立密码登录、CSRF、OSS网页设置/列表/入库队列、目录网页编辑；原图阅读/缩放/翻页/本浏览器继续阅读保留。首次密码在服务器终端隐藏输入，不索要聊天密码。
- 后台worker单独systemd服务，阅读入库不做OCR，自动提取PDF书签；无书签时在网页编辑目录。纸面目录OCR、AI总结、细分类尚未实现。原PDF仍在青岛私有OSS。
- 初装/opt/chen-cook，数据/var/lib/chen-cook，独立账户chencook，172.19.0.1:8020，独立Web/worker/update timer；首次可只读复制旧/opt/chen-assistant/data/cooking-library，不改变旧库。Caddy仅向已知sms-relay-caddy-1的现有配置追加cook主机，备份/校验后reload；发现已有不同cook配置则停止，不覆盖。
- 自动部署采用青岛定时拉取公开GitHub上已通过ci.yml的push/main提交，不需要GitHub生产SSH私钥；首装仍需服务器执行一次。CI使用ubuntu-latest，不假定旧仓库专属runner可用。
- 环境无生产SSH入口；本地DNS查询网络暂失败，不能据此判定用户DNS未配置。新域名HTTPS、服务器安装、真实OSS连接、真实数据迁移均待实际验证，不能声称已上线。
- 早期测试有一次settings保存后自动跳转导致未mock的OSS列表请求，自动审批拦截了测试轮询；已将所有单元测试的OSS列表入口完全mock，下载也使用mock，不需要用户提供密钥或允许测试外连。
- 本地/workspace/scratch/3b63417353f2/chen-cook。原样书98页无PDF书签；47项目录JSON保留在用户文件，未提交公开仓库。
- 验证：初始功能提交11c5daf950dbcf987a28e6588873e267f1754893的GitHub CI39015800203/job117347534601全部success，含320/390/768/1440真实登录/阅读/目录网页编辑/继续阅读/退出验收。本地原7项测试通过；后补目录JSON网页导入及CSRF/原子失败保护测试后8项通过，最新功能head04bf866085d33c96400b7b0162fa25270d4c1fd6的CI39016038873/job117348301585全部success，8项单元/迁移测试、Python/JS/Shell检查和320/390/768/1440真实浏览器全部通过。真实服务器systemd/Caddy联调与失败回退尚未执行，不能用脚本语法检查冒充生产验收。
- 目录：网页编辑器现支持上传之前保存的47项目录JSON，无需服务器上传或终端粘贴目录；目录内容仍不进入公开仓库。
- 下一步：用户在青岛以root克隆本仓库至/opt/chen-cook并执行scripts/bootstrap.sh完成一次首装，核验cook域名HTTPS、独立登录和样书阅读。

- GitHub代码已完成，生产仍未上线：无直接SSH，未读取或索要用户密码/AccessKey；DNS的cook A记录应指向47.104.233.200，用户是否已设置未知。安装成功后必须同时核对公网HTTPS health的service=chen-cook、revision、登录和样书原页，才可更新部署完成状态。
