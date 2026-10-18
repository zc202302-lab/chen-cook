# 灶间书房 · Chen Cook 阅读端

部署域名：https://cook.ziboxiaozhushou.cn

本仓库只负责服务器书库、全文搜索、图文阅读、可点击目录、阅读进度和书签。原PDF的批量识别、修正与图片裁切在独立桌面端完成。桌面端上传转换包，服务器不接收或处理原PDF，不安装OCR模型，不运行PDF worker。

## 现有服务器升级

沿用 `/opt/chen-cook`、`chen-cook.service`、`172.19.0.1:8020` 和现有Caddy配置。CI通过的main由已经安装的timer自动部署。`/health`返回service、mode、version、revision，用于确认真正上线的提交。

新书库位于 `/var/lib/chen-cook/reader`。旧目录下的SQLite、预览及OSS配置不删除，也不自动导入到新阅读库。旧数据与桌面转换结果属于不同格式，请从桌面上传转换后的书籍。

旧部署器首次切换时仍会安装worker单元，因此提供一个不做任何处理的兼容占位；下一次timer检查完成迁移后停止并禁用该单元。仓库中已无旧OSS、登录、PDF识别与处理代码。部署不修改Caddy、其他站点、小助手或其他端口。

## 桌面上传

桌面端网站地址填写 `https://cook.ziboxiaozhushou.cn`。同步密钥在新站首次启动时自动生成，仅保存在服务器 `/var/lib/chen-cook/reader/sync-token`，权限0600，不会写进日志或网页。管理员可在服务器终端读取并填入桌面端，勿发到公开聊天或仓库。也可在 `/etc/chen-cook/reader.env` 设置 `COOK_SYNC_TOKEN` 后重启服务。

支持ZIP转换包（最大1GB）；不接受PDF、越界路径或重复书籍覆盖。网站暂不开发读者账号；上传有同步密钥保护，网页写入有同源检查。

## 本地验证

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt playwright
.venv/bin/python -m unittest discover -s tests -v
COOK_READER_DATA=./data .venv/bin/uvicorn server:app --host 127.0.0.1 --port 8765
```

浏览器验收：`python -m playwright install chromium webkit` 后运行 `python tests/browser_acceptance.py`。只用合成书籍，覆盖320/390/768/1440四种尺寸，不上传私人书刊。
