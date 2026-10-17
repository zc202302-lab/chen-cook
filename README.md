# 晨的书刊库 · Chen Cook

独立私人电子书与杂志网站：**https://cook.ziboxiaozhushou.cn**。支持封面书库、内部章节目录、原页翻阅/缩放、页码跳转、本浏览器继续阅读；网页设置青岛OSS、选PDF入库、查看后台进度、编辑目录。

原件保留在私有OSS，新站使用独立数据库、JPEG预览和服务。已有小助手样书库可复制迁移，不改变原库。不依赖小助手代码或登录状态。

## 首次安装

本仓库CI通过后，在青岛服务器以root执行：

```bash
git clone https://github.com/zc202302-lab/chen-cook.git /opt/chen-cook
bash /opt/chen-cook/scripts/bootstrap.sh
```

终端会隐藏输入独立登录密码，无需把密码发给任何人。要求Python3 venv、Git、Docker及Caddy容器`sms-relay-caddy-1`，配置bind mount到`/etc/caddy/Caddyfile`，网桥172.19.0.1；不符合时停止。新站8020端口，原小助手8010端口不变。

DNS：`cook` A记录指向青岛47.104.233.200。Caddy自动申请HTTPS证书；DNS/防火墙未就绪时不能宣称公网部署完成。不开放OSS权限，不将书刊上传GitHub。

## 日常使用

登录 → 设置青岛OSS的Bucket及仅列出/读取权限凭据 → 添加书刊 → 选择电子书/杂志目录中的PDF → 加入书库 → 入库完成后阅读。凭据保存为服务器0600文件，不在网页回显。

入库逐页生成110dpi JPEG预览并提取PDF书签，**不要求全文OCR**。没有书签可在网页“编辑目录”填写章节与实际PDF页码。纸面目录自动OCR、AI总结和更细分类尚未实现。进度仅本浏览器；缩放不恢复原PDF全部细节。

当前限单PDF1GiB/5000页、列表200本、搜索100条；后续需增加书库分页。原OCR文字可关键词搜索，纯图片新书无正文检索。

## 自动部署

main push → GitHub CI单元与手机/桌面浏览器验收 → 青岛`chen-cook-update.timer`每分钟选择成功的push/main提交 → 独立数据库备份、源码快进更新、仅重启新站、核对健康和revision。新版本健康失败尝试恢复上一源码/依赖，保留书刊数据。

首装后无需每次手工部署，也无需配置GitHub生产SSH secrets。API限流或网络失败时保留当前服务，下一轮重试。不更新小助手或其他仓库。

## 验证

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt httpx==0.28.1 playwright
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m playwright install chromium
.venv/bin/python tests/browser_acceptance.py
```

交接入口：[docs/AI_HANDOFF.md](docs/AI_HANDOFF.md)。GitHub提交、CI与真实生产状态分别核对。
