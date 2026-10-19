# 阅读端替换交接

用户在2026-10-18明确授权清除chen-cook原有全部仓库内容，部署新阅读端。新的产品划分为独立桌面转换程序与服务器阅读网站；原PDF只留电脑，网站暂不做读者账号。本次以新tree替换旧tree并保留Git历史，不删除生产数据。

原main为90394a6895fccae3005d2b3237cd7e413ab176b9。现网此前启用按分钟读取ci.yml成功push/main的自动更新timer，源码/opt/chen-cook，服务chencook账户，绑定172.19.0.1:8020。域名cook.ziboxiaozhushou.cn不变。无SSH访问，不读取生产凭据。

新代码：app.py/storage.py/server.py及web；无OSS、PDF下载、OCR或旧登录模块。旧/var/lib/chen-cook数据保持原位，新转换包写入reader子目录。同步密钥由服务首次启动生成0600文件，不在聊天或提交中读取。

首次自动切换仍由内存中的旧deploy.sh完成：保留deploy/chen-cook.service和无操作worker占位文件作为协议入口；新unit运行server:app，health维持service=chen-cook与COOK_REVISION。新auto_update.py看到迁移marker缺失时会在同一HEAD再运行新deploy.sh，停止禁用旧worker并记录marker。旧代码中的SQLite备份也只发生在首次旧部署器执行阶段。新部署脚本只更新源码和独立服务，不删除数据，不修改Caddy。

验证要求：本地单元/编译/JS/Shell检查；CI保留Chromium/WebKit四尺寸真实页面验收，仅合成数据；最后单独核对公网health的mode=reader与revision。代码提交、CI成功、生产成功分别记录，不混淆。

## 已取得的发布证据

- 替换提交3caafb98e999e05d8cec1a63c96b0cf10791ef81进入main，旧cooklib、OSS、登录及PDF处理源码全部从当前tree移除，Git历史未重写。首轮CI39100326529因浏览器脚本导入路径错误失败，未部署该版本；随后修复根目录导入并将旧worker停止与禁用分开执行。
- 功能提交01602ada4c91f886c9ef7e364b0d81493e8cfe5c；本地8项测试、编译、JS/Shell语法检查通过。CI39100475194/job117595538391于2026-10-18 05:26 UTC成功，Chromium/WebKit在320/390/768/1440八个组合均通过阅读、自然换行、目录、字号、图片、书签和搜索验收。合成截图制品12125484564，不包含私人书刊。
- 公网HTTPS `/health`已经直接返回ok=true、service=chen-cook、mode=reader、version=0.2.0、revision=01602ada4c91f886c9ef7e364b0d81493e8cfe5c，确认新阅读服务自动上线。此后交接更新仅为文档，不改变上述功能代码。现网书库的真实内容转换/上传仍需桌面端完成，不能将合成验收称为用户全部书刊已入库。
- 没有服务器SSH访问，没有读取同步密钥或生产目录；worker最终禁用状态与磁盘上的旧数据未独立读取验证。同步密钥请用户在自己的服务器终端读取reader/sync-token并填入桌面，不发到公开聊天。不要将GitHub仓库内容清空误解为删除生产书刊数据。


## 2026-10-19 书籍观感与结构整理

用户指出目录粘成正文、页边书名混入步骤、逐块核对工具破坏阅读。阅读端已改为书页排版、清楚的标题层级、可跳转的目录条目、连续正文、章节导航；来源和核对工具仅在对照模式显示。结构叠加字段 role/catalog 经过校验并在导入/公开接口保留，原 text 与图片资产不改。打印页码仅作原页码展示，不猜测 PDF 页码；标题唯一匹配才跳转，重复或缺失条目标为待定位。

提交148ea6637b867d56cc35d95e0d93b87c37b14bdf：CI39252433284/job118059287640成功，9项服务测试及Chromium/WebKit在320/390/768/1440八个组合通过，新增目录保留、待定位、对照模式测试；截图制品12185154604已检查电脑和手机样式。公网/health确认version=0.3.0、revision=148ea6637b867d56cc35d95e0d93b87c37b14bdf、mode=reader。

桌面源码独立保存为用户下载补丁灶间书房_v0.3.0_书籍阅读重排补丁.zip（不在阅读端仓库内）。桌面增加识别后的结构整理、基于OCR坐标的目录同行恢复、边缘重复标签识别、保留OCR缓存的编辑写回、带revision检查的/organize端点和整理前备份；26项测试通过。现有书要在桌面点“重新整理结构”后才具备新目录叠加数据；网站的旧包不会被静默重建。重复导入同书仍被拒绝，未实现阅读包版本更新。Windows原生窗口没有实机验收。此阶段为保守规则整理，不能声称已解决所有OCR误识别、复杂图文归属或整书语义重建。


## 2026-10-19 程序内在线更新发布

用户要求后续点击程序“检查更新”完成更新，不能要求手动覆盖补丁。功能提交bfa55aa971ec39a6b14d712479ac7276809d792e发布releases/latest.json和cook-reader-0.3.1.zip（仅代码，无数据或PDF）；阅读服务的已有/api/releases接口增加部署源码目录回退。桌面0.3.1预设cook域名更新源，点击更新按钮立即检查、下载、校验、安装和重启；仍仅手动触发，没有定时自动检查。

CI39253326136/job118062273291成功：10项阅读服务测试含发布包SHA256与隐私边界，Chromium/WebKit八个尺寸组合通过。桌面27项测试通过；另用原0.2.0 updater实测新包暂存、安装、保留数据和回滚。使用原0.2.0 launcher/app的独立临时工作目录，以真实GitHub HTTPS更新源完成检查、下载、安装并由监督进程自动重启到0.3.1，数据哨兵保留；该完整测试在Linux无界面模式完成，不代表Windows原生窗口已实测。

旧版未内置更新地址，首次在程序内填写一次：https://raw.githubusercontent.com/zc202302-lab/chen-cook/main/releases/latest.json 。该GitHub发布源及归档SHA256已直接验证，实际升级测试也使用此地址；它会保存在用户本地配置，后续继续使用。cook域名/api/releases/latest在本次核对时仍404，生产health仍为0.3.0/revision73950285a2c47953911f7c88acfa79fa8be0a499，因此不能声称cook域名更新通道已经上线。不要让用户使用未验证的404入口；后续可调查服务器自动部署延迟，不需要阻止现已可用的GitHub更新通道。
