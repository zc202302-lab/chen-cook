# Chen Cook 当前交接

- 最新要求（2026-10-17 16:11 Asia/Shanghai）：用户取消密码至少12位限制。安装账户只拒绝空密码，短密码可生成哈希并登录；安装提示同步修改，现有密码与哈希算法保持兼容。本地8项测试以短密码运行验证，提交后核对CI。用户16:09截图已克隆仓库并启动bootstrap，尚无密码设置/服务启动/HTTPS完成证据。若旧安装脚本正在运行，须终止旧进程后拉取新版再重试；不删除已有账户配置或数据。

- 日期：2026-10-17（Asia/Shanghai）。用户要求在新建zc202302-lab/chen-cook独立仓库重新完成部署，域名cook.ziboxiaozhushou.cn；小助手内资料库已通过旧仓库PR #161移除，但用户尚未反馈那次现网移除结果。
- 仓库起点为空，无历史AGENTS或活动PR。独立站首版代码与CI验证完成，等待青岛首次安装和真实业务验证。复用旧阅读器与独立SQLite结构，已重新实现独立密码登录、CSRF、OSS网页设置/列表/入库队列、目录网页编辑；原图阅读/缩放/翻页/本浏览器继续阅读保留。首次密码在服务器终端隐藏输入，不索要聊天密码。
- 后台worker单独systemd服务，阅读入库不做OCR，自动提取PDF书签；无书签时在网页编辑目录。纸面目录OCR、AI总结、细分类尚未实现。原PDF仍在青岛私有OSS。
- 初装/opt/chen-cook，数据/var/lib/chen-cook，独立账户chencook，172.19.0.1:8020，独立Web/worker/update timer；首次可只读复制旧/opt/chen-assistant/data/cooking-library，不改变旧库。Caddy仅向已知sms-relay-caddy-1的现有配置追加cook主机，备份/校验后reload；发现已有不同cook配置则停止，不覆盖。
- 自动部署采用青岛定时拉取公开GitHub上已通过ci.yml的push/main提交，不需要GitHub生产SSH私钥；首装仍需服务器执行一次。CI使用ubuntu-latest，不假定旧仓库专属runner可用。
- 环境无生产SSH入口；本地DNS查询网络暂失败，不能据此判定用户DNS未配置。新域名HTTPS、服务器安装、真实OSS连接、真实数据迁移均待实际验证，不能声称已上线。
- 早期测试有一次settings保存后自动跳转导致未mock的OSS列表请求，自动审批拦截了测试轮询；已将所有单元测试的OSS列表入口完全mock，下载也使用mock，不需要用户提供密钥或允许测试外连。
- 本地/workspace/scratch/3b63417353f2/chen-cook。原样书98页无PDF书签；47项目录JSON保留在用户文件，未提交公开仓库。
- 验证：初始功能提交11c5daf950dbcf987a28e6588873e267f1754893的GitHub CI39015800203/job117347534601全部success，含320/390/768/1440真实登录/阅读/目录网页编辑/继续阅读/退出验收。本地原7项测试通过；后补目录JSON网页导入及CSRF/原子失败保护测试后8项通过，最新功能head04bf866085d33c96400b7b0162fa25270d4c1fd6的CI39016038873/job117348301585全部success，8项单元/迁移测试、Python/JS/Shell检查和320/390/768/1440真实浏览器全部通过。真实服务器systemd/Caddy联调与失败回退尚未执行，不能用脚本语法检查冒充生产验收。
- 目录：网页编辑器现支持上传之前保存的47项目录JSON，无需服务器上传或终端粘贴目录；目录内容仍不进入公开仓库。
- 下一步：用户在青岛以root克隆本仓库至/opt/chen-cook并执行scripts/bootstrap.sh完成一次首装，核验cook域名HTTPS、独立登录和样书阅读。

- GitHub代码已完成，生产仍未上线：无直接SSH，未读取或索要用户密码/AccessKey；DNS的cook A记录应指向47.104.233.200，用户是否已设置未知。安装成功后必须同时核对公网HTTPS health的service=chen-cook、revision、登录和样书原页，才可更新部署完成状态。
