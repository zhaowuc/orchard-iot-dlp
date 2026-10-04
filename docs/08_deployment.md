# 08 部署说明

## 本地答辩部署

Windows 运行 `init_demo.bat` 初始化，运行 `start.bat` 启动。Bootstrap 和 ECharts 已本地化，不依赖现场外网。SQLite 适合单机答辩，不需要额外数据库服务。

## 生产化建议

1. 使用环境变量设置 `SECRET_KEY`、`DEBUG=False`、`ALLOWED_HOSTS`。
2. 切换 MySQL/PostgreSQL，安装对应驱动并执行迁移。
3. 使用 Gunicorn/Uvicorn 等应用服务器并由 Nginx/Caddy 提供 HTTPS、静态资源和请求限制。
4. 导出文件使用私有对象存储或仅应用可读目录，配置清理周期。
5. 应用运行日志和 AuditLog 分别保留；配置数据库备份、告警通知和监控。
6. 修改 Demo 密码、设备令牌和所有默认阈值。

## 环境变量

参考 `.env.example`。当前项目直接读取进程环境变量，不会自动读取或提交 `.env`；可由 PowerShell、systemd、Docker 或 CI/CD 注入。

## 静态资源

开发环境由 Django 提供 `static/`。生产环境执行：

```bash
python manage.py collectstatic --noinput
```

再由反向代理提供 `staticfiles/`。

