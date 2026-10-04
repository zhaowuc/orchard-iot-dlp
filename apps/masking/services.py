import hashlib
import random
import re
import string

from django.db.models import Q

from apps.dlp.services import AccessControlService
from apps.sensitive.models import SensitiveFieldDefinition, SensitivityLevel
from .models import MaskingRecord, MaskingRule


class MaskingService:
    LEVEL_RANK = {
        SensitivityLevel.PUBLIC: 0,
        SensitivityLevel.INTERNAL: 1,
        SensitivityLevel.SENSITIVE: 2,
        SensitivityLevel.IMPORTANT: 3,
    }

    @classmethod
    def level_for_field(cls, field_name, field_type, fallback="SENSITIVE"):
        definitions = SensitiveFieldDefinition.objects.filter(enabled=True)
        exact = definitions.filter(field_name=field_name).values_list("sensitivity_level", flat=True).first()
        if exact:
            return exact
        levels = list(definitions.filter(field_type=field_type).values_list("sensitivity_level", flat=True))
        return max(levels, key=lambda item: cls.LEVEL_RANK.get(item, 0)) if levels else fallback

    @classmethod
    def apply(cls, value, field_type, *, user=None, scene=MaskingRule.Scenes.WEB_VIEW, sensitivity_level="SENSITIVE", orchard=None, source_type="", source_object_id="", record=True, force_mask=False):
        if value is None or value == "":
            return value
        raw = str(value)
        if sensitivity_level == SensitivityLevel.PUBLIC and not force_mask:
            return raw
        if not force_mask and user is not None and AccessControlService.can_view_raw(user, orchard=orchard, sensitivity_level=sensitivity_level):
            return raw
        role = getattr(user, "role", None)
        rule = MaskingRule.objects.filter(enabled=True, field_type=field_type, sensitivity_level=sensitivity_level).filter(Q(role=role) | Q(role__isnull=True)).filter(scene__in=[scene, MaskingRule.Scenes.ALL]).order_by("priority", "id").first()
        masking_type = rule.masking_type if rule else MaskingRule.MaskingTypes.MASK
        config = rule.config if rule else {}
        result = cls.transform(raw, field_type, masking_type, config)
        if record:
            MaskingRecord.objects.create(
                user=user if getattr(user, "is_authenticated", False) else None,
                rule=rule,
                field_type=field_type,
                scene=scene,
                source_type=source_type,
                source_object_id=str(source_object_id or ""),
                original_fingerprint=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                result_preview=result[:255],
            )
        return result

    @classmethod
    def transform(cls, raw, field_type, masking_type, config=None):
        config = config or {}
        if masking_type == MaskingRule.MaskingTypes.HASH:
            return "HASH_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        if masking_type == MaskingRule.MaskingTypes.TOKEN:
            return "TOK_" + hashlib.sha256(("orchard-dlp:" + raw).encode("utf-8")).hexdigest()[:12].upper()
        if masking_type == MaskingRule.MaskingTypes.RANDOM:
            rng = random.Random(hashlib.sha256(raw.encode("utf-8")).digest())
            return "".join(rng.choice(string.ascii_uppercase + string.digits) if ch.isalnum() else ch for ch in raw)
        if masking_type == MaskingRule.MaskingTypes.GENERALIZE and "replacement" in config:
            return str(config["replacement"])
        if field_type == "phone":
            return re.sub(r"^(\d{3})\d+(\d{4})$", r"\1****\2", raw) if len(raw) >= 7 else "*" * len(raw)
        if field_type == "device_code":
            parts = raw.split("-")
            if len(parts) >= 3:
                parts[-2] = "****"
                return "-".join(parts)
            return raw[:3] + "****" + raw[-4:]
        if field_type in {"username", "account"}:
            return raw[:3] + "*" * max(len(raw) - 6, 4) + raw[-3:]
        if field_type in {"coordinate", "latitude", "longitude"}:
            return re.sub(r"(\d+\.\d{2})\d+", r"\1**", raw)
        if field_type in {"datetime", "collection_time"}:
            return re.sub(r"(\d{4}-\d{2}-\d{2})[ T]\d{2}:\d{2}:\d{2}.*", r"\1 **:**:**", raw)
        if field_type in {"location", "address"}:
            return raw[: max(2, len(raw) // 3)] + "***"
        if masking_type == MaskingRule.MaskingTypes.GENERALIZE:
            return "[已泛化]"
        prefix = int(config.get("prefix", 2))
        suffix = int(config.get("suffix", 2))
        if len(raw) <= prefix + suffix:
            return "*" * len(raw)
        return raw[:prefix] + "*" * max(4, len(raw) - prefix - suffix) + raw[-suffix:]
