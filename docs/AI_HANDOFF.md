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
