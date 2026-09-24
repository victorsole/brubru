"""The calendar response schema must accept every value the model can store.

It keeps its own copies of the enums. They drifted twice: THIRD_PARTY
institutions, then tris_standstill (24 Sep 2026), and each time ONE unknown
row made CalendarEventResponse raise, which failed the whole range endpoint.
"""
from models.eu_calendar import EventTypeEnum as ModelEventType, InstitutionEnum as ModelInstitution
from schemas import eu_calendar_schemas as sch


def _values(enum_cls):
    return {m.value for m in enum_cls}


def test_every_model_event_type_is_accepted_by_the_schema():
    schema_enum = next(v for k, v in vars(sch).items() if k.lower().startswith("eventtype") and hasattr(v, "__members__"))
    assert _values(ModelEventType) <= _values(schema_enum)


def test_every_model_institution_is_accepted_by_the_schema():
    schema_enum = next(v for k, v in vars(sch).items() if k.lower().startswith("institution") and hasattr(v, "__members__"))
    assert _values(ModelInstitution) <= _values(schema_enum)
