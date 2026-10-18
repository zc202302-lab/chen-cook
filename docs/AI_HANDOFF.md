# 阅读端替换交接

用户在2026-10-18明确授权清除chen-cook原有全部仓库内容，部署新阅读端。新的产品划分为独立桌面转换程序与服务器阅读网站；原PDF只留电脑，网站暂不做读者账号。本次以新tree替换旧tree并保留Git历史，不删除生产数据。

原main为90394a6895fccae3005d2b3237cd7e413ab176b9。现网此前启用按分钟读取ci.yml成功push/main的自动更新timer，源码/opt/chen-cook，服务chencook账户，绑定172.19.0.1:8020。域名cook.ziboxiaozhushou.cn不变。无SSH访问，不读取生产凭据。

新代码：app.py/storage.py/server.py及web；无OSS、PDF下载、OCR或旧登录模块。旧/var/lib/chen-cook数据保持原位，新转换包写入reader子目录。同步密钥由服务首次启动生成0600文件，不在聊天或提交中读取。

首次自动切换仍由内存中的旧deploy.sh完成：保留deploy/chen-cook.service和无操作worker占位文件作为协议入口；新unit运行server:app，health维持service=chen-cook与COOK_REVISION。新auto_update.py看到迁移marker缺失时会在同一HEAD再运行新deploy.sh，停止禁用旧worker并记录marker。旧代码中的SQLite备份也只发生在首次旧部署器执行阶段。新部署脚本只更新源码和独立服务，不删除数据，不修改Caddy。

验证要求：本地单元/编译/JS/Shell检查；CI保留Chromium/WebKit四尺寸真实页面验收，仅合成数据；最后单独核对公网health的mode=reader与revision。代码提交、CI成功、生产成功分别记录，不混淆。当前文件为提交前计划记录，CI和现网证据在发布后补充。
