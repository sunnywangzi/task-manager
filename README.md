# task-manager

## 项目简介

这是一个基于 Web 的 Linux 定时任务管理工具，使用 Python Flask 框架开发。它提供了友好的界面来查看、添加、编辑和监控 cron 任务，特别适合管理服务器上的各种定时脚本。

## 主要功能

- 📝 查看所有 cron 任务
- ➕ 添加新定时任务
- ✏️ 编辑现有任务
- ❌ 删除不再需要的任务
- ▶️ 手动立即运行任务
- 📄 查看任务执行日志
- ⏱️ 查看任务执行历史记录
- ✅ 检查任务今日是否运行过
- 🔄 实时同步到系统 crontab

## 系统要求

- Linux 系统
- Python 3.x
- Flask 框架
- crontab 服务

## 安装步骤

1. 克隆仓库或下载代码：

```bash
git clone https://github.com/sunnywangzi/task-manager.git
cd task-manager
```

2. 安装依赖：

```bash
pip install flask
```

3. 创建日志目录（可选）：

```bash
sudo mkdir -p /var/log/
sudo chmod 666 /var/log/*.log
```

4. 启动服务：

```bash
python app.py
```

## 配置为系统服务

1. 创建 systemd 服务文件 `/etc/systemd/system/taskmanager.service`：

```ini
[Unit]
Description=Task Manager Web Interface
After=network.target

[Service]
User=root
WorkingDirectory=/path/to/task-manager
ExecStart=/usr/bin/python3 /path/to/task-manager/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

2. 启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable taskmanager
sudo systemctl start taskmanager
```

## 使用方法

1. 访问 `http://your-server-ip:5000`
2. 主界面显示所有任务及其状态
3. 使用顶部标签页切换任务列表和原始 cron 视图
4. 操作按钮说明：
   - **运行** - 立即执行任务
   - **日志** - 查看任务日志
   - **历史** - 查看执行历史记录
   - **编辑** - 修改任务配置
   - **删除** - 移除任务

## 项目结构

```
task-manager/
├── app.py                 # 主应用程序
├── task_db.json           # 任务数据库
├── task_history.json      # 执行历史记录
├── templates/
│   ├── index.html         # 主界面
│   └── edit_task.html     # 任务编辑表单
└── README.md              # 说明文档
```

## 安全注意事项

1. 默认情况下，该面板没有身份验证机制
2. 建议采取以下安全措施之一：
   - 使用防火墙限制访问IP
   - 添加基本的HTTP认证
   - 通过反向代理（如Nginx）添加安全层
   - 仅在内网使用

## 常见问题

**Q: 为什么我的任务日志显示为空？**
A: 请确保在任务配置中指定了正确的日志文件路径，并且该文件有写入权限。

**Q: 如何修改监听端口？**
A: 编辑 `app.py` 文件末尾的 `app.run(port=5000)`，将5000改为你想要的端口号。

**Q: 添加的任务没有出现在系统crontab中？**
A: 确保运行服务的用户有修改crontab的权限，通常需要使用root用户运行。

## 贡献指南

欢迎提交问题和拉取请求！对于重大更改，请先开issue讨论您想做的更改。

## 许可证

MIT License
