# 04 安全设计

## 身份和权限

- 业务用户使用 Django Authentication、Session、密码哈希和 CSRF。
- 设备通过设备编号与 `X-Device-Token` 认证；数据库只保存令牌哈希。
- 后端按角色和 assigned_orchards 过滤查询集，并在修改、导出、告警等对象操作前再次检查。
- 普通用户直接访问安全管理 URL、其他果园对象或他人 Export ID 返回 403。

## 数据保护

- 数据库保存原始业务值，脱敏只发生在 WEB_VIEW、API 和 EXPORT 输出边界。
- MaskingRecord 保存原值 SHA-256 指纹，不保存额外原文副本。
- CSV 在生成时重新执行范围授权和动态脱敏，并写入 EXPORT_ID、USER、EXPORT_TIME 和文件哈希。
- 下载通过 UUID 查询记录并校验所有权；解析后的文件路径必须位于 MEDIA_ROOT 内。

## 风险与审计

- 查询频率、敏感访问、大规模导出、跨果园越权、连续登录失败、异常时段和重复异常均可形成风险因素。
- 风险分限制在 0-100：LOW 0-29、MEDIUM 30-59、HIGH 60-79、CRITICAL 80-100。
- RiskEvent 保存逐项分值；达到可配置阈值后自动创建 SecurityAlert。
- AuditService 是统一写入口；写失败会记录应用错误，但不直接破坏正常业务请求。

## 常见 Web 风险

- SQL 注入：使用 Django ORM 和表单校验。
- XSS：模板默认转义，项目未使用 `safe` 绕过。
- CSRF：业务表单使用 CSRF；设备 API 免 CSRF，但要求设备令牌。
- IDOR：对象级授权与 Export ID 所有权检查。
- 路径遍历：导出路径 resolve 后确认位于 MEDIA_ROOT。
- 敏感日志：普通 app.log 不写密码、令牌或完整敏感数据。

