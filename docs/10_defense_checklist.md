# 答辩前快速验收清单

最后验收：2026-08-11。自动化测试 82/82 通过。

- [x] 网站能启动（`http://127.0.0.1:8000/`）
- [x] `admin` 能登录
- [x] `security` 能登录
- [x] `orchard_admin` 能登录
- [x] `user` 能登录
- [x] Dashboard 正常
- [x] IoT 模拟器正常
- [x] 实时数据正常
- [x] 异常数据正常
- [x] 敏感识别正常
- [x] 动态脱敏正常
- [x] 普通用户无法获得原文
- [x] 越权访问被阻止
- [x] 高频查询触发风险
- [x] 大规模导出受限
- [x] Export 审批正常
- [x] AuditLog 正常
- [x] RiskEvent 正常
- [x] SecurityAlert 正常
- [x] 告警可以处理
- [x] Dashboard 数据真实变化
- [x] 图表正常
- [x] 没有菜单死链接
- [x] 主要非法输入没有 500
- [x] 静态资源正常
- [x] 私有导出直链返回 404
- [x] 导出 SHA-256 下载前复核
- [x] DEBUG=False 自定义错误页无 Traceback

## 现场开始前 30 秒

1. 双击 `start.bat`，确认终端显示 `Starting development server at http://127.0.0.1:8000/`。
2. 刷新浏览器并用 `admin / Demo@123456` 登录。
3. 确认 Dashboard 图表出现；若普通用户刚触发过限流，等待 60 秒再访问数据列表。
4. 需要恢复标准 Demo 密码和基础数据时执行 `init_demo.bat`；该命令幂等，不会清空数据库。
