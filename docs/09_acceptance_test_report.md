# 独立验收测试报告

> 本报告基于代码逐层审查、独立攻击测试、真实 HTTP 请求、数据库副作用、文件内容与哈希检查以及全量回归生成，不引用原开发报告中的“已完成”作为验收证据。

## 1. 测试环境

- 项目：基于 Python 的果园物联网数据防泄漏与脱敏系统
- 测试日期：2026-08-11
- 操作系统：Windows 11 10.0.22621
- Python：3.12.10
- Django：5.2.15
- 数据库：SQLite 3
- 时区：Asia/Shanghai，`USE_TZ=True`
- Git：当前目录不是 Git 仓库，无法记录 commit；验收未删除现有数据库或用户文件。

## 2. 测试范围

覆盖功能、四角色认证、RBAC、果园级 ABAC、IDOR、IoT HTTP 接口、模拟器、敏感识别、四级分类、五类脱敏、防泄漏、限流、导出状态机、CSV 安全、审计、风险评分、告警、Dashboard、数据库一致性、XSS、SQL 注入、CSRF、路径遍历、错误页、性能、干净部署和答辩闭环。

不适用项：项目无上传功能；未提供 XLSX 导出；MQTT 不要求真实 Broker/设备；Linux 脚本在 Windows 环境仅静态审查。

## 3. 六大模块 / 24 子功能追踪矩阵

| 模块/子功能 | 页面或命令 | URL / View | Service | Model | 独立验证 |
|---|---|---|---|---|---|
| 数据采集：设备登记 | 设备管理 | `/assets/devices/` / `asset_edit` | `AccessControlService` | `Device` | 通过，含跨果园关联攻击 |
| 数据采集：MQTT/HTTP | API、MQTT 命令 | `/api/iot/data/` / `listen_mqtt` | `IoTValidationService` | `Device`、`SensorReading` | HTTP 实测通过，MQTT 静态/依赖通过 |
| 数据采集：数据校验 | API | `ingest_api` | `IoTValidationService` | `SensorReading` | 类型、时间、范围、体积、认证通过 |
| 数据采集：异常标记 | 数据列表 | `/data/readings/?status=abnormal` | `IoTValidationService` | `SensorReading` | 湿度 150 原值保留并标记 |
| 敏感识别：字段字典 | 字段字典 | `/sensitive/fields/` | 表单与审计服务 | `SensitiveFieldDefinition` | 修改后数据库和脱敏入口同步 |
| 敏感识别：规则识别 | 识别规则 | `/sensitive/rules/` | `SensitiveDetectionService` | `SensitiveRule` | 字段名、正则、标签运行通过 |
| 敏感识别：敏感级别 | 字段编辑 | `field_edit` | `MaskingService.level_for_field` | 四级枚举 | PUBLIC/INTERNAL/SENSITIVE/IMPORTANT 通过 |
| 敏感识别：识别记录 | 识别记录 | `/sensitive/detections/` | `scan_mapping` | `SensitiveDetectionRecord` | 真实 IoT 入库后记录存在 |
| 动态脱敏：策略配置 | 脱敏策略 | `/masking/rules/` | `MaskingService` | `MaskingRule` | 角色、场景、等级规则通过 |
| 动态脱敏：掩码/泛化 | 脱敏预览 | `/masking/preview/` | `transform` | `MaskingRule` | MASK、GENERALIZE 通过 |
| 动态脱敏：Token 替换 | 脱敏预览 | `/masking/preview/` | `transform` | `MaskingRule` | TOKEN、HASH、RANDOM 通过 |
| 动态脱敏：预览 | 预览页 | `preview` | `MaskingService` | `AuditLog` | 输入驱动，非写死示例 |
| 防泄漏：RBAC/ABAC | 访问策略 | `/dlp/policies/` | `AccessControlService` | `AccessPolicy` | GET/POST、范围、时间窗通过 |
| 防泄漏：查询频率 | 查询监控 | `/dlp/queries/` | `QueryLimitService` | `QueryMonitor` | N-1/N/N+1 与动态配置通过 |
| 防泄漏：导出审批/追踪 | 导出中心 | `/dlp/exports/` | `ExportSecurityService` | `ExportRequest`、`ExportRecord` | 状态、元数据、SHA-256 通过 |
| 防泄漏：异常行为拦截 | 数据查询 | `/data/readings/` | 限流、风险服务 | Audit/Risk/Alert | 第 11 次敏感查询被 403 |
| 安全审计：操作日志 | 审计页 | `/security/logs/` | `AuditService` | `AuditLog` | 登录、查询、导出、处置均有记录 |
| 安全审计：行为基线 | 业务服务 | 无独立页面 | `BehaviorBaselineService` | `AuditLog` | 异常时段、历史果园、规模因子通过 |
| 安全审计：风险评分 | 风险页 | `/security/risks/` | `RiskScoringService` | `RiskEvent` | 0-100、边界、解释、去重通过 |
| 安全审计：告警处置 | 告警页 | `/security/alerts/<id>/` | 风险与审计服务 | `SecurityAlert` | PROCESSING→RESOLVED 真实通过 |
| 统计运维：安全看板 | Dashboard | `/` | `_dashboard_payload` | 多模型聚合 | 数据库值与页面值对应 |
| 统计运维：趋势分析 | ECharts | `/api/dashboard/summary/` | Dashboard 聚合 | Reading/Risk/Alert | 1/7/30 天、未登录保护通过 |
| 统计运维：报表下载 | 导出中心 | 安全下载 URL | `ExportSecurityService` | `ExportRecord` | 601 行导出、鉴权、哈希通过 |
| 统计运维：参数维护 | 系统参数 | `/settings/` | `SystemConfig.get_value` | `SystemConfig` | 类型校验及实时阈值通过 |

## 4. 自动化测试结果

- 最终命令：`python manage.py test --verbosity 1`
- 总数：82
- 通过：82
- 失败：0
- 错误：0
- 跳过：0
- 原有测试：38
- 新增独立验收/攻击测试：44
- 运行时间：27.249 秒

测试中显示的 400、403、404、405、413、415 与模拟磁盘异常 Traceback 均为断言中的预期攻击/事务回滚场景，最终进程退出码为 0。

## 5. 权限测试结果

- 四个账户正确密码均可登录；错误密码、不存在账户、禁用账户均拒绝。
- 普通用户直接 GET/POST 用户、角色、敏感规则、脱敏规则、策略、审计、风险、告警、系统参数均为 403。
- 安全管理员可管理安全模块，但设备编辑 GET/POST 均为 403。
- 果园管理员只见授权果园；设备绑定其他果园地块被表单和后端同时阻止。
- 退出后原会话不能继续访问 Dashboard。
- 菜单隐藏与后端权限均已验证，未依赖“只隐藏按钮”。

## 6. IDOR 测试结果

- 修改设备、果园、Export ID、Alert ID、UUID、Query String 均未获得额外权限。
- 其他用户 Export ID 下载返回 403，并生成 `UNAUTHORIZED_EXPORT_DOWNLOAD`。
- 路径遍历形式与非法 UUID 返回 404。
- 未授权果园设备编辑返回 403，并生成 `UNAUTHORIZED_ORCHARD_ACCESS`、RiskEvent。
- 私有 `media/exports` 不再映射为公开 URL，未登录直链实测从 200 修复为 404。

## 7. IoT 接口测试结果

- 正常数据：201 并入库。
- 缺字段、格式错误、非对象 JSON、NaN：400，无 500。
- 无 Token/错误 Token：403；未知设备：404；错误 Content-Type：415；超过 64 KiB：413。
- 未来/过旧时间、湿度/土壤/光照越界：保存原值并设置 `is_abnormal` 和原因。
- 字符串 `false` 不再误存为虫情告警；非法设备状态被标记异常。
- 重放数据允许保留，但后续记录明确包含“重复数据”。
- 真实 HTTP 注入湿度 150 返回 201，生成记录 ID 1801，异常原因真实保存。

## 8. 敏感识别测试结果

- 手机号、设备编号、坐标、账号、采集时间、告警字段均通过字段字典/规则验证。
- IoT 业务行为真实生成 `SensitiveDetectionRecord`，包含字段、规则、等级、时间及原值指纹。
- 重复检测会更新现有记录的最新规则和等级，不复制原始敏感值。

## 9. 动态脱敏测试结果

- 数据库 `Orchard.contact_phone` 保持 `13812345678`。
- 真实 HTTP：普通用户页面包含 `138****5678`，不含原文；管理员页面包含原文。
- API、页面、CSV 均对普通用户隐藏完整设备编号和精确采集时间。
- MASK、GENERALIZE、HASH、TOKEN、RANDOM 对空值、短值、Unicode、超长字符串均不产生 500。
- 全局规则、配置化泛化结果、字段等级实时变更均已回归。

## 10. 防泄漏测试结果

- 查询阈值从 `SystemConfig` 实时读取；阈值 2 时前两次通过，第 3 次阻止。
- 主库真实测试中前 10 次敏感查询为 200，第 11、12 次为 403。
- 阻止动作生成 QueryMonitor、BLOCKED AuditLog、RiskEvent，并在达到阈值时生成 SecurityAlert。
- 同一评分因子只计一次；同类高风险告警 5 分钟内合并，避免告警风暴。

## 11. 导出测试结果

- 小规模导出自动完成；大规模普通用户导出进入 PENDING。
- PENDING、REJECTED、EXPIRED 不可生成或下载；只有 APPROVED 可生成，生成后为 COMPLETED。
- 重复提交 10 秒内幂等，不重复创建请求或文件。
- CSV 用户可控单元格以单引号转义 `= + - @`，防止公式注入。
- 下载前重新计算 SHA-256；篡改文件返回 403 并写 `EXPORT_INTEGRITY_FAILURE`。
- 主库真实审批导出 601 行；文件存在、哈希一致，完整设备号不存在，`ORCH-NORTH-****-0001` 存在。
- 审批生成失败模拟会回滚到 PENDING，审批审计也不会留下半成品。

## 12. Audit 测试结果

- 登录成功/失败、退出、数据查询、越权、IoT 接入、规则修改、导出申请/审批/生成/下载、告警处置均真实写入。
- 登录审计保存账号快照、IP、时间，不保存密码。
- 日志扫描未发现 Demo 密码、设备 Token、完整测试手机号、Session ID 或 SECRET_KEY。
- 普通用户与果园管理员没有审计日志修改/删除入口。

## 13. Risk 测试结果

- 0-29 LOW、30-59 MEDIUM、60-79 HIGH、80-100 CRITICAL。
- 最低不会小于 0，最高被钳制为 100。
- `details.breakdown` 与 `reason` 保存因子、名称和加分，得分可解释。
- 修复重复 `large_export` 因子后，不再重复加分。
- 连续登录失败可随次数增长达到告警阈值。

## 14. SecurityAlert 测试结果

- 告警由真实查询、导出、登录失败或越权行为经 RiskEvent 自动产生，不通过直接造告警证明功能。
- 5 分钟相同用户/事件类型告警使用冷却合并；RiskEvent 仍逐条保留。
- 普通用户、果园管理员不能处理告警。
- 主库真实告警 ID 4 已完成 PROCESSING→RESOLVED；处理人为 `security`，处理时间、意见和 2 条 AuditLog 均存在。

## 15. Dashboard 测试结果

- 设备总数、在线/离线、今日数据、脱敏、风险、告警均来自数据库查询。
- 普通用户风险/告警只统计本人，且不展示其他用户安全告警标题或无权限链接。
- `device_offline_timeout` 修改后在线/离线统计立即变化。
- 风险和告警操作后 Dashboard 聚合同步变化。
- 空数据库、非法 `days`、非法分页不会产生 500。

## 16. 安全测试结果

- 认证：通过。
- RBAC/ABAC/IDOR：通过。
- CSRF：管理 POST 无 Token 返回 403；IoT API 仅因设备接口豁免 CSRF，并使用哈希设备 Token。
- XSS：模板自动转义，`<script>` 以实体显示；无 `|safe`/`mark_safe`。
- SQL 注入：搜索特殊字符串无 500、无范围绕过；业务查询使用 ORM。
- 开放重定向：外部 `next` 已阻止。
- 文件下载：UUID、所属用户、状态、过期时间、私有路径、实际哈希六层检查。
- 生产错误页：DEBUG=False 下 404 自定义页面，无 Traceback/源码路径泄漏。

## 17. 性能基本测试结果

主库 1828 条 SensorReading、65 条 AuditLog、6 条 RiskEvent、4 条 SecurityAlert 下真实 HTTP 粗测：

- Dashboard：29 ms
- 数据列表：30 ms
- 设备关键词搜索：27 ms
- 主要列表使用 `select_related`/`prefetch_related`，分页每页 20/25 条。
- 模拟器新增 27 条数据，最近 27 条中有 26 个不同温度值，湿度、土壤、光照无越界值。

上述为本机功能级响应时间，不等同于生产压力测试。

## 18. 部署测试结果

- 新建独立虚拟环境，仅安装 `requirements.txt`：成功。
- 新环境 `pip check`：无冲突。
- 全新 SQLite：迁移成功、seed 成功，得到 4 用户、3 果园、12 地块、24 设备、1800 数据、3 风险、2 告警。
- `seed_demo` 连续执行两次，所有基础模型数量不变，无唯一键异常。
- 生产安全环境变量完整设置时 `manage.py check --deploy`：0 问题。
- DEBUG=False 真实服务：登录 200、静态资源 200、自定义 404、私有 media 404、无 Traceback。
- Windows 启动脚本不删除/重置数据库；Linux 脚本静态检查一致。

## 19. Bug 列表

共发现 23 个真实产品缺陷：P0 1、P1 6、P2 16、P3 0。

| Bug ID | 等级 | 问题与复现摘要 | 原因 | 修复与回归 |
|---|---:|---|---|---|
| ACC-P0-001 | P0 | 未登录 `/media/exports/<file>` 返回 200 | DEBUG 直接挂载 MEDIA_ROOT | 移除公开挂载；HTTP/URL 解析均为 404 |
| ACC-P1-001 | P1 | 果园管理员可把 A 果园设备关联 B 果园地块 | 关联字段未限域/未交叉校验 | QuerySet 限域 + Form clean，回归通过 |
| ACC-P1-002 | P1 | 普通用户 Dashboard 泄露其他用户告警标题 | 安全事件使用全局 QuerySet | 用户级聚合并隐藏无权入口，回归通过 |
| ACC-P1-003 | P1 | REJECTED/EXPIRED 导出可被服务生成或已生成文件继续下载 | 状态和过期检查缺失 | 生成/下载双重状态校验，回归通过 |
| ACC-P1-004 | P1 | 文件被篡改后仍可下载 | 只保存哈希、不在下载时验证 | 下载前重算哈希，篡改返回 403 |
| ACC-P1-005 | P1 | 连续登录失败风险分永远达不到告警阈值 | 分数上限过低且失败用户未关联 | 关联用户并阶梯计分，回归通过 |
| ACC-P1-006 | P1 | CSV 的 `= + - @` 可触发公式注入 | 用户字段直接写 CSV | 安全单元格转义，回归通过 |
| ACC-P2-001 | P2 | 外部 `next` 形成开放重定向 | 未验证目标 Host | 使用 Django 安全 URL 校验 |
| ACC-P2-002 | P2 | 非对象 JSON 触发 AttributeError/500 | 默认假定 dict | 顶层类型检查，返回 400 |
| ACC-P2-003 | P2 | NaN 触发 Decimal/SQLite JSON 错误 | 接受非标准 JSON 常量 | 严格 JSON 解析，返回 400 |
| ACC-P2-004 | P2 | 字符串 `false` 被当作 True | 直接 `bool(value)` | 严格布尔解析 |
| ACC-P2-005 | P2 | 任意 device_status 静默保存 | 无枚举验证 | 非法状态标记异常 |
| ACC-P2-006 | P2 | role=NULL 的全局脱敏规则不命中 | SQL `IN (..., NULL)` | 改用 `Q(role=...) OR isnull` |
| ACC-P2-007 | P2 | GENERALIZE 忽略 replacement | 字段特例先于算法配置 | 配置优先并保留默认泛化 |
| ACC-P2-008 | P2 | RAW_VIEW 不执行策略时间窗 | 仅普通果园访问检查时间 | 统一时间窗函数 |
| ACC-P2-009 | P2 | SystemConfig 可保存非法整数 | ModelForm 无类型校验 | 类型/范围校验 |
| ACC-P2-010 | P2 | 重复高风险请求造成告警风暴 | 每个 RiskEvent 都创建 Alert | 5 分钟冷却合并 |
| ACC-P2-011 | P2 | 重复导出 POST 创建多个文件 | 无幂等窗口 | 10 秒请求指纹幂等 |
| ACC-P2-012 | P2 | 字段等级/规则修改后识别记录和脱敏入口可能仍用旧值 | get_or_create 与硬编码等级 | update_or_create + 动态等级解析 |
| ACC-P2-013 | P2 | 重复告警提交可能重复审计，首次修复又受 ModelForm 内存变更影响 | 未保存表单前状态 | 保存原状态后比较，回归通过 |
| ACC-P2-014 | P2 | 相同风险因子被重复计分 | calculate 不去重 | 按 factor key 去重 |
| ACC-P2-015 | P2 | 导出允许 start_time > end_time | 无跨字段 clean | 日期及果园/地块/设备一致性校验 |
| ACC-P2-016 | P2 | HTTPS Cookie/HSTS 参数不可完整环境化 | 部署配置缺项 | 增加安全环境变量，deploy check 通过 |

## 20. Bug 修复与回归结果

- 23 个缺陷全部修复并有自动化或真实 HTTP 回归证据。
- 修复后独立验收测试：44/44 通过。
- 修复后完整测试：82/82 通过。
- 当前未关闭缺陷：0。

## 21. 剩余风险

- MQTT 命令与依赖已验证，但按软件项目约束未连接真实 Broker；HTTP 和模拟器是答辩主路径。
- MySQL 配置已提供但本轮未准备 MySQL 服务，实际验收数据库为 SQLite。
- Linux `start.sh` 在 Windows 上仅静态审查。
- Django `runserver` 仅用于本地答辩；正式部署仍应使用生产 WSGI/ASGI、反向代理与 HTTPS。
- 浏览器视觉验收已覆盖 1440×900 与 390×844、侧栏抽屉、表格内部滚动和控制台错误；不同投影仪缩放仍建议答辩前人工确认一次。

以上均为环境/部署边界，不构成当前本科软件项目的 P0/P1/P2 未修复缺陷。

## 22. 最终结论

**PASS**

- 当前 P0：0
- 当前 P1：0
- 当前 P2：0
- 当前 P3：0
- 核心闭环已通过真实 HTTP、数据库记录与导出文件三类证据验证。
