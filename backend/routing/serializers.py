from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .domain.forecast import start_limit

INTERVALS = (10, 25, 50)
PAST_GRACE = timedelta(minutes=5)  # a form defaulting to "now" is a few seconds old on arrival


def validate_forecast_window(value, now):
    limit = start_limit(now)
    if value >= limit:
        raise serializers.ValidationError(
            f"Choose a time before {limit:%Y-%m-%d %H:%M} UTC so the full 48-hour forecast is available."
        )


class PlaceSearchSerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=100, trim_whitespace=True)


class PlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure = serializers.DateTimeField(help_text="ISO 8601; without an offset it is read as UTC")
    load_lbs = serializers.FloatField(
        min_value=1,
        max_value=150_000,
        error_messages={
            "min_value": "Load must be at least 1 lb.",
            "max_value": "Load can't be more than 150,000 lb.",
            "invalid": "Enter the load in pounds.",
        },
    )
    interval_miles = serializers.ChoiceField(choices=INTERVALS, default=25)

    def validate_departure(self, value):
        now = timezone.now()
        if value < now - PAST_GRACE:
            raise serializers.ValidationError("Departure can't be in the past.")
        validate_forecast_window(value, now)
        return value

    def validate(self, attrs):
        if " ".join(attrs["origin"].lower().split()) == " ".join(attrs["destination"].lower().split()):
            raise serializers.ValidationError({"destination": ["Destination must differ from origin."]})
        return attrs


class LngLatField(serializers.ListField):
    child = serializers.FloatField()

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if len(value) != 2 or not (-180 <= value[0] <= 180 and -90 <= value[1] <= 90):
            raise serializers.ValidationError("Expected [lng, lat].")
        return value


class HeatmapRequestSerializer(serializers.Serializer):
    routes = serializers.ListField(
        child=serializers.ListField(child=LngLatField(), min_length=1, max_length=500),
        min_length=1,
        max_length=3,
    )
    load_lbs = serializers.FloatField(min_value=1, max_value=150_000)
    start = serializers.DateTimeField()

    def validate_start(self, value):
        now = timezone.now()
        if value < now - timedelta(hours=1):
            raise serializers.ValidationError("Start can't be more than an hour in the past.")
        validate_forecast_window(value, now)
        return value
