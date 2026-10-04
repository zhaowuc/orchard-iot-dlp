# 基于 Python 的果园物联网数据防泄漏与脱敏系统

面向本科毕业设计答辩的可运行 Django Web 工程。系统不是普通果园 CRUD 平台，而是把 IoT 数据接入、校验、敏感识别、分类分级、动态脱敏、对象级授权、查询限频、安全导出、风险评分、告警和审计串成真实数据库闭环。

## 使用说明导航

- 第一次拿到项目：阅读“接收项目后的快速开始”。
- 日常启动和停止：阅读“Windows 安装与启动”和“停止、重启与端口”。
- 了解各角色如何操作：阅读“角色与推荐操作顺序”。
- 演示数据接入：阅读“IoT 模拟器”和“HTTP 数据接入”。
- 完成导出审批：阅读“安全导出完整流程”。
- 把项目发给其他人：阅读“项目打包与转交”。
- 遇到无法启动、403 或没有数据：阅读“常见问题”。

## 研究背景

智慧果园持续产生温度、湿度、土壤墒情、光照、虫情、设备状态、地块位置和人员信息。单纯依赖账号密码无法防止越权查询、敏感字段明文展示、异常批量导出或通过 URL 修改对象 ID 获取其他果园数据。本项目以规则型安全机制完成可解释、可演示的数据防泄漏控制。

## 核心功能

- 果园、地块、网关、设备、数据源的搜索、筛选、分页和维护。
- 带设备令牌的 `POST /api/iot/data/`，支持数据类型、时间、重复性和合理范围校验；异常数据保留并标记。
- `simulate_iot` 连续趋势模拟器，无需真实硬件或 MQTT Broker。
- 字段名、正则表达式和业务语义标签组合识别，支持 PUBLIC/INTERNAL/SENSITIVE/IMPORTANT 四级分类。
- MASK、GENERALIZE、HASH、TOKEN、RANDOM 五类脱敏；数据库保存原文，列表、API 和导出按角色实时处理。
- 角色 + 果园/地块/设备/敏感等级/操作的后端访问策略；IDOR 和纵向越权返回 403 并审计。
- 查询限频、CSV 导出审批、导出追踪元数据、SHA-256 文件哈希和 Export ID 下载隔离。
- 统一 AuditService、规则型行为基线、0-100 可解释风险评分和自动安全告警。
- 8 个真实统计卡片、传感趋势、设备状态、敏感等级及风险/告警趋势图。

## 系统架构

浏览器通过 Django Template/Vanilla JavaScript/ECharts 访问控制台；请求进入认证、对象级权限和业务服务，通过 Django ORM 访问 SQLite。IoT HTTP API 使用设备令牌，MQTT 适配使用 `paho-mqtt` 并允许在没有 Broker 时独立运行。详细图见 [docs/system_architecture.md](docs/system_architecture.md)。

## 技术栈

- Python 3.12、Django 5.2.15 LTS
- SQLite（开发/演示），ORM 代码可切换 MySQL
- Django Template、Bootstrap 5.3.8、Vanilla JavaScript、ECharts 5.6.0
- paho-mqtt 2.1.0
- Django TestCase、Test Client、RequestFactory

## 目录结构

```text
apps/                 八个业务 App
  accounts/           用户、角色、登录审计
  orchards/           果园资产
  iot/                传感数据、HTTP 接入、模拟器
  sensitive/          敏感识别与分类分级
  masking/            动态脱敏
  dlp/                访问控制、查询监控、安全导出
  audit/              审计、风险事件、安全告警
  dashboard/          Dashboard 与系统参数
config/               配置、URL、错误页、通用视图工具
templates/            服务端页面模板
static/               本地 Bootstrap、ECharts、CSS、JS
docs/                 架构、数据库、安全、API、测试和答辩文档
media/exports/         运行时安全导出文件
tests/                 自动化测试公共夹具
```

## 接收项目后的快速开始

本项目不需要真实传感器、MQTT Broker 或云服务器。软件内置模拟数据和 IoT 模拟命令，适合在单台电脑上完成开发、测试和答辩演示。

### 1. 环境要求

- Windows 10/11，推荐 64 位系统。
- Python 3.12；安装时勾选“Add Python to PATH”。
- 第一次安装依赖时需要网络；安装完成后，页面静态资源和 Demo 数据可以离线运行。
- 浏览器推荐 Edge 或 Chrome。
- 默认使用 SQLite，不需要安装 MySQL。

检查 Python：

```powershell
python --version
py -3 --version
```

### 2. 解压与初始化

将压缩包完整解压到本地目录，不要直接在 ZIP 压缩包内运行。推荐使用短路径，例如：

```text
D:\orchard_dlp
```

第一次使用时，双击 `init_demo.bat`。该脚本会：

1. 创建 `.venv` Python 虚拟环境。
2. 安装 `requirements.txt` 中的依赖。
3. 执行数据库迁移。
4. 创建四类 Demo 账号、果园、地块、设备、安全规则和演示数据。

`seed_demo` 是幂等命令，重复执行不会无限重复基础数据，也不会清空已有业务数据。

### 3. 启动系统

双击 `start.bat`，看到以下信息说明服务启动成功：

```text
Starting development server at http://127.0.0.1:8000/
```

浏览器打开 <http://127.0.0.1:8000/>，使用下方 Demo 账号登录。运行期间不要关闭启动命令窗口。

### 4. 再次使用

以后通常只需要双击 `start.bat`。只有首次安装、数据库结构更新或需要补充 Demo 基础数据时，才需要再次执行 `init_demo.bat`。

## 无环境离线运行包

项目另提供 ZIP 格式的 Windows 离线运行包，内置 Python 解释器、Django、paho-mqtt、SQLite、静态资源和干净 Demo 数据。接收方不需要安装 Python，也不需要联网。

使用方法：

1. 完整解压 ZIP，不要直接在压缩包内双击文件。
2. 双击 `启动系统.bat`。
3. 等待数秒，默认浏览器会自动打开 `http://127.0.0.1:8000/`。
4. 使用 `admin / Demo@123456` 等 Demo 账号登录。
5. 使用结束后双击 `停止系统.bat`。

离线包首次启动会自动执行数据库迁移和幂等 Demo 初始化。运行日志写入 `logs/offline_launcher.log`，服务进程号写入 `work/offline_server.pid`。如果 8000 端口被占用，启动器会提示先关闭占用程序。

离线包面向 64 位 Windows 10/11。它是可携带的答辩与演示版本，不等同于公网生产部署包。

## Windows 安装与启动

```powershell
cd D:\danzi\ruanjian
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

也可以双击 `init_demo.bat` 初始化，再双击 `start.bat` 启动。启动脚本不会自动重置 Demo 数据。

Linux/macOS 使用 `sh init_demo.sh` 和 `sh start.sh`。

访问地址：<http://127.0.0.1:8000/>

## 停止、重启与端口

- 停止服务：在运行 `start.bat` 的命令窗口按 `Ctrl+C`，确认后关闭窗口。
- 重启服务：先停止原服务，再重新双击 `start.bat`。
- 页面打不开：确认启动窗口没有报错，并确认访问的是 `http://127.0.0.1:8000/`，不是 HTTPS 地址。
- 8000 端口被占用时，可临时改用其他端口：

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

随后访问 <http://127.0.0.1:8001/>。

## 演示账号

以下密码只用于本地 Demo，命令会通过 Django 密码哈希保存，不应在生产环境使用。

| 账号 | 密码 | 角色 | 主要差异 |
|---|---|---|---|
| `admin` | `Demo@123456` | 超级管理员 | 全局数据、原文、用户、角色和系统参数 |
| `security` | `Demo@123456` | 安全管理员 | 规则、审计、风险、告警和导出审批 |
| `orchard_admin` | `Demo@123456` | 果园管理员 | 仅维护授权果园资产 |
| `user` | `Demo@123456` | 普通用户 | 授权范围只读，敏感字段动态脱敏 |

Demo 设备令牌：`orchard-device-demo-token`，通过请求头 `X-Device-Token` 发送。

## 角色与推荐操作顺序

### 超级管理员 `admin`

1. 登录后查看 Dashboard 安全态势。
2. 在“资产与数据”中管理果园、地块、网关、设备和数据源。
3. 查看实时与历史传感数据；管理员可以查看授权范围内的原始字段。
4. 管理用户、角色和系统参数。
5. 必要时进入安全中心查看风险、告警和审计日志。

### 安全管理员 `security`

1. 维护敏感字段、识别规则、脱敏策略和访问策略。
2. 在“查询行为监控”查看高频查询与拦截记录。
3. 在“风险事件”和“安全告警”查看评分、原因和处置状态。
4. 在“安全导出中心”审批普通用户提交的大规模或高敏导出。
5. 填写告警处置意见并将状态更新为处理中、已解决或已忽略。

### 果园管理员 `orchard_admin`

1. 只查看分配给自己的果园及相关地块、网关和设备。
2. 维护授权果园范围内的资产。
3. 无法通过修改 URL 或对象 ID 操作其他果园数据。

### 普通用户 `user`

1. 查看授权范围内的果园、设备和传感数据。
2. 手机号、设备编号等敏感字段按照策略动态脱敏。
3. 提交安全导出申请，并在审批完成后下载脱敏 CSV。
4. 短时间连续查询敏感数据超过阈值时会被阻止并产生风险事件。

## 主要页面入口

| 功能 | 页面地址 | 主要角色 |
|---|---|---|
| 安全总览 | `/` | 所有已登录用户 |
| 果园管理 | `/assets/orchards/` | 管理员、果园管理员、普通用户只读 |
| 地块管理 | `/assets/plots/` | 管理员、果园管理员 |
| 网关管理 | `/assets/gateways/` | 管理员、果园管理员 |
| 设备管理 | `/assets/devices/` | 管理员、果园管理员、普通用户只读 |
| 实时与历史数据 | `/data/readings/` | 所有已登录用户，按角色控制范围和原文 |
| 敏感字段字典 | `/sensitive/fields/` | 管理员、安全管理员 |
| 识别规则与记录 | `/sensitive/rules/`、`/sensitive/detections/` | 管理员、安全管理员 |
| 脱敏策略与预览 | `/masking/rules/`、`/masking/preview/` | 管理员、安全管理员 |
| 查询监控 | `/dlp/queries/` | 管理员、安全管理员 |
| 安全导出中心 | `/dlp/exports/` | 所有已登录用户，审批仅限安全角色 |
| 风险与告警 | `/security/risks/`、`/security/alerts/` | 管理员、安全管理员 |
| 操作日志 | `/security/logs/` | 管理员、安全管理员 |
| 用户、角色、系统参数 | `/accounts/users/`、`/accounts/roles/`、`/settings/` | 超级管理员 |

菜单显示只是操作提示，所有敏感页面和数据对象同时执行后端权限验证。无权限访问会返回 403，并在适用场景下写入审计和风险记录。

## IoT 模拟器

```powershell
# 生成 100 条连续趋势数据
.\.venv\Scripts\python.exe manage.py simulate_iot --count 100

# 每台设备生成一条
.\.venv\Scripts\python.exe manage.py simulate_iot --once

# 每 2 秒生成一条，共 30 条
.\.venv\Scripts\python.exe manage.py simulate_iot --count 30 --interval 2

# 注入湿度 150 的异常记录
.\.venv\Scripts\python.exe manage.py simulate_iot --count 1 --abnormal

# 可选：连接 MQTT Broker
.\.venv\Scripts\python.exe manage.py listen_mqtt --host 127.0.0.1 --port 1883 --topic "orchard/+/sensor"
```

## HTTP 数据接入

```powershell
$body = @{
  device_code = "ORCH-NORTH-DEVICE-0001"
  temperature = 26.5
  humidity = 62.1
  soil_moisture = 45.8
  light = 35000
  pest_alarm = $false
  device_status = "ONLINE"
  collection_time = (Get-Date).ToString("o")
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/iot/data/" -ContentType "application/json" -Headers @{"X-Device-Token"="orchard-device-demo-token"} -Body $body
```

接口成功返回 HTTP 201。温度、湿度、土壤墒情或光照超出合理范围时，系统仍保留原始数据，但会设置异常状态并记录原因。未知设备、错误令牌、非法 JSON、NaN、错误时间格式或超大请求体会被拒绝。

## 安全导出完整流程

1. 使用 `user` 登录并进入“安全导出中心”。
2. 可选择果园、地块、设备、时间范围和敏感等级；不选择表示导出全部授权范围。
3. 点击“提交安全导出”。小规模低风险数据可以自动生成；大规模或高敏数据进入 `PENDING`。
4. 退出后使用 `security` 登录，进入“安全导出中心”。
5. 点击待审批申请后的“审批”，选择“批准”或“拒绝”并填写处理意见。
6. 批准后系统执行范围复核、动态脱敏、CSV 公式注入防护、文件生成和 SHA-256 哈希计算。
7. 再次使用原申请人登录，在“可下载记录”中点击“安全下载”。
8. 下载时系统再次验证申请人、审批状态、有效期和文件完整性，并写入审计日志。

`media/exports/` 是私有运行目录，不能通过 `/media/...` 直链公开访问。请始终通过“安全下载”按钮获取文件。

## 测试与检查

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check
.\.venv\Scripts\python.exe manage.py test
```

当前独立验收基线：82 项测试全部通过（原有 38 项 + 独立攻击/回归 44 项）。覆盖登录成功/失败、角色权限、IDOR、IoT 恶意输入、重复数据、敏感识别、动态脱敏、API/导出防泄漏、CSV 公式注入、文件哈希、限频边界、审批事务、告警去重、生产错误页和 Dashboard。

## 数据文件、备份与恢复

- SQLite 业务数据库：`db.sqlite3`。
- 安全导出文件：`media/exports/`。
- 运行日志：`logs/app.log`，自动轮转保留有限历史文件。
- 静态前端资源：`static/`，演示页面不依赖外网 CDN。

备份前先停止服务，然后复制数据库和需要保留的导出文件：

```powershell
Copy-Item .\db.sqlite3 .\db.sqlite3.backup
Copy-Item .\media\exports .\exports_backup -Recurse
```

恢复时必须先停止服务，再用备份文件覆盖对应数据库。不要在服务运行时直接替换 `db.sqlite3`。

若只需要补充标准 Demo 基础数据，执行以下命令即可，不需要删除数据库：

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo
```

## 项目打包与转交

将项目发送给其他人前，先停止 Django 服务，再把项目根目录压缩为 ZIP。推荐保留：

- `apps/`、`config/`、`templates/`、`static/`、`docs/`、`scripts/` 和 `tests/`。
- `manage.py`、`requirements.txt`、`start.bat`、`init_demo.bat`、Linux/macOS 脚本和本 README。
- 需要保留当前演示数据时包含 `db.sqlite3`；只需要空白代码结构时可不包含，但接收方必须重新迁移和初始化。
- 需要转交已生成安全导出时包含 `media/exports/`，否则可以排除该目录中的文件。

推荐排除以下内容以减小体积并避免携带本机路径或临时信息：

```text
.venv/
__pycache__/
*.pyc
.pytest_cache/
work/
logs/*.log*
```

不要把本机 `.venv` 直接交给其他电脑使用；虚拟环境可能记录原电脑的绝对路径。接收方应运行 `init_demo.bat` 重新创建环境。如果接收方电脑没有 Python 或无法联网，需要额外制作离线依赖包或独立发行包。

转交前还应确认没有打包真实生产密码、数据库凭据、用户隐私数据或生产设备令牌。Demo 账号和 Demo Token 只能用于本地演示。

## 配置环境变量

`.env.example` 记录了可用配置项，但当前工程直接读取操作系统环境变量，不会自动加载 `.env` 文件。仅复制或改名 `.env.example` 不会自动生效。

PowerShell 临时配置示例，仅对当前命令窗口有效：

```powershell
$env:SECRET_KEY = "替换为足够长的随机密钥"
$env:DEBUG = "False"
$env:ALLOWED_HOSTS = "127.0.0.1,localhost"
$env:SESSION_COOKIE_SECURE = "False"
$env:CSRF_COOKIE_SECURE = "False"
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

本地 HTTP 演示不要启用 Secure Cookie 或 HTTPS 重定向，否则浏览器可能无法在 `http://127.0.0.1` 下正常保持会话。公网部署时必须改用 HTTPS，并按照“生产部署注意事项”开启相应安全配置。

## MySQL 切换

安装兼容的 MySQL Python 驱动后，将 `.env.example` 中 `DB_ENGINE` 改为 `mysql` 并填写连接信息。项目未使用 SQLite 专有 SQL。当前代码从操作系统环境变量读取配置；生产部署应由服务管理器注入真实值。

## 生产部署注意事项

- 必须设置随机 `SECRET_KEY`、`DEBUG=False` 和准确的 `ALLOWED_HOSTS`。
- 使用反向代理提供 HTTPS，并把 `SESSION_COOKIE_SECURE`、`CSRF_COOKIE_SECURE`、`SECURE_SSL_REDIRECT` 设为 `true`；确认全站 HTTPS 后设置 HSTS 秒数及子域策略。
- 导出目录应使用私有存储，不允许 Web 服务器直接列目录。
- 定期轮转 `logs/app.log`，AuditLog 使用数据库独立保存。
- 修改 Demo 密码和设备令牌，接入生产数据库及备份策略。

## 核心演示流程

登录 Dashboard → 查看资产 → 运行 IoT 模拟器 → 注入异常湿度 → 查看敏感识别 → 对比管理员/普通用户的原文与脱敏 → 触发查询限频或大规模导出 → `security` 审批/处置告警 → 返回 Dashboard 观察真实统计变化。完整 3-5 分钟脚本见 [docs/07_demo_guide.md](docs/07_demo_guide.md)。

## 常见问题

- 双击脚本后一闪而过：在 PowerShell 中进入项目目录手动执行 `.\init_demo.bat` 或 `.\start.bat`，根据终端中的具体错误排查。
- 提示找不到 `py` 或 `python`：安装 Python 3.12 并勾选 PATH，重新打开命令窗口。
- 依赖安装失败：确认网络和 pip 可用，执行 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`。
- 提示端口已占用：关闭旧的 Django 运行窗口，或临时使用 8001 端口。
- 页面没有数据：执行 `manage.py seed_demo`；命令幂等，不会无限重复基础数据。
- API 返回 403：确认设备编号和 `X-Device-Token`。
- 登录后返回 403：当前账号没有该模块或该果园的权限，请切换到对应角色，不要仅修改 URL。
- 普通用户看到星号：这是动态脱敏结果，数据库原值未被替换。
- 导出停留在 PENDING：使用 `security` 或 `admin` 在安全导出中心审批。
- 下载导出文件返回 403：确认使用原申请人或安全管理员登录，并检查申请是否已批准、是否过期以及文件是否被修改。
- 连续访问数据页返回 403：触发了 60 秒查询限频，等待窗口结束，或使用安全管理员查看查询监控和风险记录。
- ECharts/Bootstrap 加载失败：资源已放在 `static/`，不依赖答辩现场外网。
- 修改代码后没有生效：停止并重新启动服务；答辩现场不要同时启动多个占用不同端口的旧服务。

## 相关文档

- [系统架构](docs/system_architecture.md)
- [API 使用说明](docs/05_api_document.md)
- [测试报告](docs/06_test_report.md)
- [答辩演示指南](docs/07_demo_guide.md)
- [独立验收测试报告](docs/09_acceptance_test_report.md)
- [答辩前快速验收清单](docs/10_defense_checklist.md)
- [四分钟静音字幕演示视频](docs/demo_video/果安哨兵-四分钟答辩演示.mp4)
