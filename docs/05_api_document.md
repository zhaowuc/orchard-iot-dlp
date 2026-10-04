# 05 API 文档

## POST /api/iot/data/

设备数据接入，无需用户 Session，但必须提供请求头：

```http
Content-Type: application/json
X-Device-Token: orchard-device-demo-token
```

请求示例：

```json
{
  "device_code": "ORCH-NORTH-DEVICE-0001",
  "temperature": 26.5,
  "humidity": 62.1,
  "soil_moisture": 45.8,
  "light": 35000,
  "pest_alarm": false,
  "device_status": "ONLINE",
  "collection_time": "2026-08-11T18:32:16+08:00"
}
```

成功返回 201，包含 `id`、`is_valid`、`is_abnormal` 和 `abnormal_reason`。异常范围数据也返回 201 并真实保存。未知设备 404、令牌错误 403、JSON/必填/时间错误 400。

## GET /data/api/readings/

需要登录。返回当前用户授权果园最近 100 条数据。普通用户的设备编号和采集时间经过动态脱敏，管理员按原文权限返回。

## GET /api/dashboard/summary/?days=7

需要登录。`days` 支持 1/7/30，返回当前用户数据范围的 8 个统计卡片及传感、设备、敏感、风险和告警图表数据。

## CSV 导出

Web 表单提交 `/dlp/exports/`。大规模或高敏导出进入 PENDING；安全管理员在 `/dlp/exports/<uuid>/decision/` 处理；授权用户通过 `/dlp/exports/<uuid>/download/` 下载。系统不公开媒体目录直链。

