import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.iot.models import SensorReading
from apps.iot.services import IoTValidationService


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "连接 MQTT Broker 并接收果园传感器 JSON 数据；没有 Broker 时不影响 HTTP 与模拟器"

    def add_arguments(self, parser):
        parser.add_argument("--host", default=settings.MQTT_HOST)
        parser.add_argument("--port", type=int, default=settings.MQTT_PORT)
        parser.add_argument("--topic", default="orchard/+/sensor")
        parser.add_argument("--username", default="")
        parser.add_argument("--password", default="")

    def handle(self, *args, **options):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise CommandError("缺少 paho-mqtt，请执行 pip install -r requirements.txt") from exc

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="orchard-dlp-django")
        if options["username"]:
            client.username_pw_set(options["username"], options["password"])

        def on_connect(mqtt_client, userdata, flags, reason_code, properties):
            if reason_code != 0:
                self.stderr.write(self.style.ERROR(f"MQTT 连接失败：{reason_code}"))
                return
            self.stdout.write(self.style.SUCCESS(f"已连接 MQTT {options['host']}:{options['port']}，订阅 {options['topic']}"))
            mqtt_client.subscribe(options["topic"], qos=1)

        def on_message(mqtt_client, userdata, message):
            try:
                payload = json.loads(message.payload.decode("utf-8"))
                reading = IoTValidationService.ingest(payload, source_type=SensorReading.SourceTypes.MQTT)
                self.stdout.write(f"MQTT reading={reading.pk} device={reading.device.device_code} abnormal={reading.is_abnormal}")
            except Exception as exc:
                logger.warning("MQTT payload rejected on topic %s: %s", message.topic, exc)
                self.stderr.write(f"拒绝消息 topic={message.topic}：{exc}")

        client.on_connect = on_connect
        client.on_message = on_message
        try:
            client.connect(options["host"], options["port"], keepalive=60)
            client.loop_forever()
        except OSError as exc:
            raise CommandError(f"无法连接 MQTT Broker：{exc}。HTTP API 与 simulate_iot 仍可独立使用。") from exc
