import random
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.iot.models import SensorReading
from apps.iot.services import IoTValidationService
from apps.orchards.models import Device


class Command(BaseCommand):
    help = "生成连续变化的果园 IoT 模拟数据"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1, help="生成记录数；配合 interval 可持续生成指定数量")
        parser.add_argument("--interval", type=float, default=0, help="每条数据的间隔秒数")
        parser.add_argument("--once", action="store_true", help="每台启用设备各生成一条")
        parser.add_argument("--abnormal", action="store_true", help="注入一条湿度 150 的异常数据")

    def handle(self, *args, **options):
        devices = list(Device.objects.exclude(status=Device.DeviceStatus.DISABLED).select_related("orchard", "plot"))
        if not devices:
            raise CommandError("没有可用设备，请先运行 python manage.py seed_demo")
        total = len(devices) if options["once"] else max(options["count"], 1)
        rng = random.Random()
        generated = 0
        for index in range(total):
            device = devices[index % len(devices)]
            last = SensorReading.objects.filter(device=device).order_by("-collection_time").first()
            temperature = float(last.temperature) if last and last.temperature is not None else 24 + rng.uniform(-2, 2)
            humidity = float(last.humidity) if last and last.humidity is not None else 62 + rng.uniform(-4, 4)
            soil = float(last.soil_moisture) if last and last.soil_moisture is not None else 48 + rng.uniform(-3, 3)
            light = float(last.light) if last and last.light is not None else 32000 + rng.uniform(-3000, 3000)
            payload = {
                "device_code": device.device_code,
                "temperature": round(max(-20, min(55, temperature + rng.uniform(-0.6, 0.6))), 2),
                "humidity": round(max(0, min(100, humidity + rng.uniform(-1.2, 1.2))), 2),
                "soil_moisture": round(max(0, min(100, soil + rng.uniform(-0.9, 0.9))), 2),
                "light": round(max(0, min(150000, light + rng.uniform(-900, 900))), 2),
                "pest_alarm": rng.random() < 0.015,
                "device_status": "ONLINE",
                "collection_time": timezone.now().isoformat(),
            }
            if options["abnormal"] and index == 0:
                payload["humidity"] = 150
            reading = IoTValidationService.ingest(payload, source_type=SensorReading.SourceTypes.SIMULATOR)
            generated += 1
            self.stdout.write(f"[{generated}/{total}] {device.device_code} -> reading={reading.pk} abnormal={reading.is_abnormal}")
            if options["interval"] > 0 and index < total - 1:
                time.sleep(options["interval"])
        self.stdout.write(self.style.SUCCESS(f"成功生成 {generated} 条 IoT 数据"))

