# 灶间书房 · 烹饪原文资料库

部署域名：https://cook.ziboxiaozhushou.cn

首页提供原PDF资料库：批量上传、分类与年份筛选、封面书架、中文关键词搜索、目录与命中页跳转、手机和电脑原页阅读。界面参考东方美食的公开信息结构，独立实现；内容由用户提供。暂不生成AI总结。

已有转换结果保留在 `/legacy`，原接口及桌面更新发布包保持兼容。新PDF资料与旧转换结果分开保存。扫描件OCR、语义检索、无内嵌目录的自动文章划分尚未实现，详见 [实现范围](docs/ORIGINAL_LIBRARY.md)。

## 现有服务器升级

沿用 `/opt/chen-cook`、`chen-cook.service`、`172.19.0.1:8020` 和现有Caddy配置。CI通过的main由已经安装的timer自动部署。`/health`返回service、mode、version、revision，用于确认真正上线的提交。

新原文资料库位于 `/var/lib/chen-cook/reader/original-library`，保存原PDF及独立SQLite索引。旧目录和旧转换结果均不删除。原PDF不得提交GitHub。

旧worker保持禁用，文字索引在阅读服务内串行处理。部署不修改Caddy、其他站点、小助手或其他端口。

## 上传与管理

网站点击“管理书库”，填写现有同步密钥，即可批量选择PDF。同步密钥仅保存在服务器 `/var/lib/chen-cook/reader/sync-token`，权限0600，不写进日志或网页。管理员在自己的服务器终端读取，勿发到公开聊天或仓库。也可通过 `/etc/chen-cook/reader.env` 设置 `COOK_SYNC_TOKEN` 后重启服务。

新资料库单个PDF上限2GB，SHA256检测完全重复文件，删除进入可恢复的回收站。已有文字与内嵌目录自动提取；没有目录时按页检索，可编辑文章起止页。扫描件标记待OCR。旧版 `/api/import` 仍支持ZIP转换包（最大1GB）。网站暂不开发读者账号；写操作有同步密钥及同源检查。

## 本地验证

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt playwright
.venv/bin/python -m unittest discover -s tests -v
COOK_READER_DATA=./data .venv/bin/uvicorn server:app --host 127.0.0.1 --port 8765
```

浏览器验收：安装Chromium/WebKit后运行 `python tests/browser_acceptance.py` 和 `python tests/library_browser_acceptance.py`。只用合成书籍，不上传私人书刊。
