# 灶间书房 · 烹饪原文资料库

部署域名：https://cook.ziboxiaozhushou.cn

使用用户提供的原PDF建立个人烹饪资料库。支持批量上传、分类和年份筛选、封面书架、中文关键词搜索、目录和命中页跳转、手机与电脑原页阅读。参考东方美食的公开信息结构，独立实现；暂不生成AI总结。

旧转换器、旧阅读网站、旧接口、桌面更新代码与发布包已从当前仓库删除。服务器已有书刊数据保留。

## 上传与管理

点击“管理书库”，填写现有管理密钥，批量选择PDF。单个文件上限2GB，SHA256检测相同文件，删除可从回收站恢复。已有文字与内嵌目录自动提取；无目录时按页检索，可编辑文章起止页。扫描件标记待OCR。

扫描件OCR、语义检索、无内嵌目录的自动文章划分尚未实现，详见[实现范围](docs/ORIGINAL_LIBRARY.md)。

## 部署

沿用/opt/chen-cook、chen-cook.service、172.19.0.1:8020及现有Caddy配置。CI成功的main由既有timer自动部署。/health返回version、revision及library标记。

新资料保存在/var/lib/chen-cook/reader/original-library；管理密钥沿用/var/lib/chen-cook/reader/sync-token（0600权限），或COOK_SYNC_TOKEN环境变量。不要将密钥发到聊天或提交GitHub。没有读者账号，写操作使用管理密钥与同源检查。部署不删除现有数据，不修改其他站点和端口。

## 验证

安装requirements.txt后运行：

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
node --check web/library/library.js
```

浏览器验收安装Playwright和Chromium/WebKit，运行python tests/library_browser_acceptance.py。测试仅用合成PDF。
