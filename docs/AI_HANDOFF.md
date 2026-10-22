# 原文资料库交接

用户于2026-10-22授权参考东方美食公开页面重建个人原PDF烹饪资料库，暂不AI总结，随后明确要求“chen-cook原来的程序全部删除”。

当前app.py仅包含新服务初始化、管理密钥、同源保护、health和静态页面，catalogue.py负责原PDF上传、索引、目录、搜索、原文页与可恢复删除。web/library为唯一页面源码。

旧storage.py、旧web/index.html/app.js/style.css、旧转换包导入与书库/书签/回收站接口、/legacy、桌面更新接口、releases全部ZIP与latest.json、旧测试和worker占位源码全部移除。只保留新资料库和现有服务器部署基础设施。生产PDF、数据库、书刊、密钥均不删除。

部署路径/opt/chen-cook，服务chen-cook，绑定172.19.0.1:8020，域名cook.ziboxiaozhushou.cn。CI成功后现有timer自动更新；不改Caddy、其他站点或端口。health中service=chen-cook及mode=reader是已安装部署器协议，library=true表示新资料库，不代表保留旧程序。部署仍停止禁用服务器残留worker，不能重新启用。

数据目录默认/var/lib/chen-cook/reader，新PDF与索引位于original-library。管理沿用sync-token或COOK_SYNC_TOKEN，不读取生产凭据，不将原PDF、真实书刊或数据库提交GitHub。没有SSH访问，不能声称独立核实服务器残留文件或systemd最终状态。

已有文字层与内嵌目录可提取。扫描件OCR、语义检索、无书签目录自动文章划分、AI总结尚未实现。仅用合成PDF测试。tests/test_catalogue.py验证新功能和旧入口移除及数据保留；tests/library_browser_acceptance.py验收Chromium/WebKit手机和电脑。分别记录提交、CI与生产health，不把提交当作上线。REA未实际运行。
