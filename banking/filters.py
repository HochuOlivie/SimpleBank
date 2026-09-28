from datetime import UTC, date, datetime, time
from typing import Any

import django_filters
from django import forms
from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.utils import extend_schema_field

from banking.models import Transaction


class DateOrDateTimeField(forms.Field):
    """Accepts an ISO 8601 date or date-time and returns an aware UTC datetime.

    A bare date stands for the whole UTC day: its start, or with ``end_of_day`` its last
    microsecond, so ``from=2026-03-01&to=2026-03-01`` covers all of 1 March.
    Naive date-times are read as UTC.
    """

    default_error_messages = {"invalid": "Enter an ISO 8601 date or date-time."}  # noqa: RUF012

    def __init__(self, *, end_of_day: bool = False, **kwargs: Any) -> None:
        self.end_of_day = end_of_day
        super().__init__(**kwargs)

    def to_python(self, value: Any) -> datetime | None:
        if value in self.empty_values:
            return None
        try:
            parsed: date | datetime | None = parse_date(value) or parse_datetime(value)
        except ValueError:
            parsed = None
        if parsed is None:
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")
        if not isinstance(parsed, datetime):
            return datetime.combine(parsed, time.max if self.end_of_day else time.min, UTC)
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


class DateOrDateTimeFilter(django_filters.Filter):
    field_class = DateOrDateTimeField

    def __init__(self, *, help_text: str, **kwargs: Any) -> None:
        super().__init__(help_text=help_text, **kwargs)
        # Document both accepted forms; the model field alone would say date-time only.
        date_or_datetime = [
            {"type": "string", "format": "date"},
            {"type": "string", "format": "date-time"},
        ]
        extend_schema_field({"oneOf": date_or_datetime, "description": help_text})(self)


class TransactionFilterForm(forms.Form):
    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        start, end = cleaned.get("from"), cleaned.get("to")
        if start and end and start > end:
            self.add_error("to", "Must not be earlier than 'from'.")
        return cleaned


class TransactionFilter(django_filters.FilterSet):
    # "from" is a Python keyword, so it cannot be declared as a plain class attribute.
    locals()["from"] = DateOrDateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
        help_text="Earliest timestamp, inclusive: an ISO 8601 date-time, or a date for 00:00 UTC.",
    )
    to = DateOrDateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
        end_of_day=True,
        help_text="Latest timestamp, inclusive: an ISO 8601 date-time, or a date for all of it.",
    )

    class Meta:
        model = Transaction
        fields: tuple[str, ...] = ()
        form = TransactionFilterForm
