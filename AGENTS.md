# Chen Cook

本仓库是独立书刊网站，域名cook.ziboxiaozhushou.cn，不得重新挂回chen-assistant。
开始工作先读docs/AI_HANDOFF.md，核对main、活动分支、CI和实际部署；代码、CI、生产分别记录。
原PDF、凭据、SQLite、预览、私人书刊目录不得提交公开仓库。所有修改操作保留登录与CSRF；PDF处理只运行在独立worker。
阶段完成主动更新交接；变更后运行相关契约，涉及页面运行真实手机/桌面浏览器验收。不要为通过CI删除/弱化测试。OSS网络在测试中必须完全模拟。
生产数据路径/var/lib/chen-cook，旧小助手书库只复制迁移、不删除。部署不得覆盖其他Caddy站点、抢占其他端口或更改小助手服务。
