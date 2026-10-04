import hashlib
import re

from .models import SensitiveDetectionRecord, SensitiveFieldDefinition, SensitiveRule, SensitivityLevel


class SensitiveDetectionService:
    @classmethod
    def detect(cls, field_name, value, *, business_tag="", source_type="", source_object_id="", create_record=True):
        normalized = field_name.lower()
        matched = None
        for rule in SensitiveRule.objects.filter(enabled=True).order_by("priority", "id"):
            if rule.match_type == SensitiveRule.MatchTypes.FIELD_NAME and rule.pattern.lower() in normalized:
                matched = rule
                break
            if rule.match_type == SensitiveRule.MatchTypes.BUSINESS_TAG and business_tag and rule.pattern.lower() in business_tag.lower():
                matched = rule
                break
            if rule.match_type == SensitiveRule.MatchTypes.REGEX and value is not None:
                try:
                    if re.search(rule.pattern, str(value)):
                        matched = rule
                        break
                except re.error:
                    continue
        definition = SensitiveFieldDefinition.objects.filter(enabled=True, field_name=field_name).first()
        level = matched.sensitivity_level if matched else (definition.sensitivity_level if definition else SensitivityLevel.PUBLIC)
        field_type = matched.field_type if matched else (definition.field_type if definition else "generic")
        is_sensitive = level != SensitivityLevel.PUBLIC
        record = None
        if create_record and is_sensitive:
            fingerprint = hashlib.sha256(str(value).encode("utf-8")).hexdigest() if value is not None else ""
            record, _ = SensitiveDetectionRecord.objects.update_or_create(
                source_type=source_type or "runtime",
                source_object_id=str(source_object_id or ""),
                field_name=field_name,
                value_fingerprint=fingerprint,
                defaults={
                    "field_type": field_type,
                    "is_sensitive": True,
                    "sensitivity_level": level,
                    "matched_rule": matched,
                    "business_tag": business_tag,
                },
            )
        return {"is_sensitive": is_sensitive, "sensitivity_level": level, "field_type": field_type, "matched_rule": matched, "record": record}

    @classmethod
    def scan_mapping(cls, mapping, *, source_type, source_object_id="", tags=None):
        tags = tags or {}
        return {key: cls.detect(key, value, business_tag=tags.get(key, ""), source_type=source_type, source_object_id=source_object_id) for key, value in mapping.items()}
