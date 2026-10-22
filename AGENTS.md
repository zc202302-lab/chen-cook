# Chen Cook 原文资料库

本仓库部署 cook.ziboxiaozhushou.cn。2026-10-22 用户将方向改为原PDF烹饪资料库，并授权参考东方美食网站重建，随后明确要求删除原来的全部程序。当前只保留新资料库，旧转换器、阅读器、接口、发布包和/legacy均删除。原PDF允许上传至用户服务器，但绝不提交仓库。新内容位于 COOK_READER_DATA/original-library；暂不实现AI总结及读者账号。删除源码不等于删除生产书刊数据。

开始工作先读 docs/AI_HANDOFF.md。不要提交原PDF、真实书刊、密钥、数据库或生产目录。API写入保留同源检查；上传使用同步密钥；按用户要求暂不开发读者账号。

生产源码 /opt/chen-cook，服务 chen-cook，绑定172.19.0.1:8020，保留现有Caddy域名配置。数据 /var/lib/chen-cook/reader；不删除旧 /var/lib/chen-cook 内容，不改其他站点、小助手或端口。旧worker保持禁用。新资料库文字索引在服务内串行执行，未集成扫描件OCR；必须明确标示覆盖不足，不能声称所有文件可检索或自动目录已准确重建。

CI、代码提交、生产health分别验证并记录。CI通过后现有timer自动部署；不可将提交成功当作已经上线。页面修改需Chromium/WebKit手机及桌面验收，测试仅用合成内容。
