# 01 系统架构

系统采用 Django 单体分层架构，目标是降低部署和答辩演示复杂度，同时保持服务边界清晰。

## 分层

1. 表现层：Django Template、Bootstrap、Vanilla JavaScript、ECharts、JSON API、CSV。
2. 认证与授权：Django Session、角色权限、果园对象范围、访问策略和设备令牌。
3. 业务服务：IoTValidationService、SensitiveDetectionService、MaskingService、AccessControlService、QueryLimitService、ExportSecurityService、AuditService、RiskScoringService。
4. 数据层：Django ORM、SQLite；关键审批和告警处置使用 `transaction.atomic`。
5. 运维层：环境变量、应用日志、迁移、Demo 初始化、启动脚本和自动化测试。

## 请求路径

- 业务用户：Browser → Django Auth → View → AccessControl/Service → ORM → Template/JSON。
- IoT 设备：HTTP JSON + Device Token → 校验 → SensorReading → 敏感识别 → 审计。
- 导出：筛选 → 对象权限 → 规模判断 → 审批 → 动态脱敏 → CSV 追踪元数据 → 授权下载。
- 安全事件：审计事实 → 风险因素 → 0-100 分 → 风险等级 → 告警 → 安全管理员处置。

完整 Mermaid 图见 `system_architecture.md`。

