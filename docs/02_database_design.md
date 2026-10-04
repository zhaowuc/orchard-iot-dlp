# 02 数据库设计

## 账户与范围

| 表/模型 | 用途 | 关键字段与关系 |
|---|---|---|
| Role | 四类业务角色 | code 唯一、name、description |
| User | 业务账号 | role → Role；assigned_orchards ↔ Orchard；is_active |
| LoginAttempt | 登录成功/失败记录 | username、user、IP、success、created_at |

## 果园与 IoT

| 表/模型 | 用途 | 关键字段与关系 |
|---|---|---|
| Orchard | 果园主体 | code 唯一、位置、联系人、电话、状态 |
| Plot | 地块 | orchard → Orchard；同一果园 code 唯一；坐标、面积 |
| Gateway | 边缘网关 | orchard → Orchard；gateway_code 唯一；协议、last_seen_at |
| Device | 传感设备 | orchard、plot、gateway；device_code 唯一；token_hash |
| DataSource | 数据源配置 | orchard、HTTP/MQTT/SIMULATOR、endpoint、config |
| SensorReading | 统一传感器读数 | orchard、plot、device；四类指标；采集时间；异常与原始载荷 |

## 敏感、脱敏和 DLP

| 表/模型 | 用途 | 关键字段与关系 |
|---|---|---|
| SensitiveFieldDefinition | 字段字典 | field_name 唯一、field_type、业务标签、敏感等级 |
| SensitiveRule | 组合识别规则 | 匹配方式、pattern、field_type、等级、优先级 |
| SensitiveDetectionRecord | 识别证据 | 来源、字段、值指纹、命中规则、等级、人工调整 |
| MaskingRule | 动态脱敏策略 | 字段、算法、等级、角色、场景、JSON 配置、优先级 |
| MaskingRecord | 脱敏命中 | 用户、规则、场景、原值 SHA-256、结果预览 |
| AccessPolicy | 属性访问策略 | 角色、果园、地块、设备、等级、操作、ALLOW/DENY |
| QueryMonitor | 查询窗口记录 | 用户、IP、路径、范围、记录数、敏感数、blocked |
| ExportRequest | 导出申请 | UUID、用户、筛选、规模、状态、审批人和意见 |
| ExportRecord | 导出追踪 | UUID、文件路径、记录数、敏感数、文件 SHA-256 |

## 审计、风险与运维

| 表/模型 | 用途 | 关键字段与关系 |
|---|---|---|
| AuditLog | 统一业务审计 | 用户快照、IP、路径、动作、对象、结果、风险分、详情 |
| RiskEvent | 可解释风险事件 | 用户、类型、0-100 分、等级、分项原因、关联审计 |
| SecurityAlert | 告警闭环 | event 一对一、状态、处理人、意见、处理时间 |
| SystemConfig | 集中安全阈值 | key 唯一、value、类型、说明、可编辑状态 |

所有核心表包含创建和更新时间；高频筛选字段建立了索引。ORM 查询未使用 SQLite 专有 SQL。

