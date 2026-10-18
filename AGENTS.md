# Chen Cook 阅读端

本仓库仅部署 cook.ziboxiaozhushou.cn 的阅读网站。用户已明确要求替换旧站全部源码；旧登录、OSS、PDF处理和worker不再属于本产品。转换在独立桌面端进行，阅读端只接收转换包。

开始工作先读 docs/AI_HANDOFF.md。不要提交原PDF、真实书刊、密钥、数据库或生产目录。API写入保留同源检查；上传使用同步密钥；按用户要求暂不开发读者账号。

生产源码 /opt/chen-cook，服务 chen-cook，绑定172.19.0.1:8020，保留现有Caddy域名配置。新数据 /var/lib/chen-cook/reader；不删除旧 /var/lib/chen-cook 内容，不改其他站点、小助手或端口。deploy/chen-cook-worker.service只是旧部署器首次迁移的无操作占位，后续部署停止并禁用它，不执行PDF任务。

CI、代码提交、生产health分别验证并记录。CI通过后现有timer自动部署；不可将提交成功当作已经上线。页面修改需Chromium/WebKit手机及桌面验收，测试仅用合成内容。
