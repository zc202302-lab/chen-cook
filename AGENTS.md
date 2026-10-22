# Chen Cook 阅读端

本仓库部署 cook.ziboxiaozhushou.cn。2026-10-22 用户将方向改为原PDF烹饪资料库，并授权参考东方美食网站重建。首页为新资料库；/legacy 保留旧转换书库。原PDF允许上传至用户服务器，但绝不提交仓库。新内容位于 COOK_READER_DATA/original-library，与旧书籍数据隔离；暂不实现AI总结及读者账号。

开始工作先读 docs/AI_HANDOFF.md。不要提交原PDF、真实书刊、密钥、数据库或生产目录。API写入保留同源检查；上传使用同步密钥；按用户要求暂不开发读者账号。

生产源码 /opt/chen-cook，服务 chen-cook，绑定172.19.0.1:8020，保留现有Caddy域名配置。数据 /var/lib/chen-cook/reader；不删除旧 /var/lib/chen-cook 内容，不改其他站点、小助手或端口。旧worker保持禁用。新资料库文字索引在服务内串行执行，未集成扫描件OCR；必须明确标示覆盖不足，不能声称所有文件可检索或自动目录已准确重建。

CI、代码提交、生产health分别验证并记录。CI通过后现有timer自动部署；不可将提交成功当作已经上线。页面修改需Chromium/WebKit手机及桌面验收，测试仅用合成内容。
