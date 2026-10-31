from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

INTERVALS = (10, 25, 50)
MAX_DAYS_AHEAD = 14  # trip + 48 h heatmap must fit Open-Meteo's 16-day forecast
PAST_GRACE = timedelta(minutes=5)  # a form defaulting to "now" is a few seconds old on arrival


class PlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure = serializers.DateTimeField(help_text="ISO 8601; without an offset it is read as UTC")
    load_lbs = serializers.FloatField(min_value=1, max_value=150_000)
    interval_miles = serializers.ChoiceField(choices=INTERVALS, default=25)

    def validate_departure(self, value):
        now = timezone.now()
        if value < now - PAST_GRACE:
            raise serializers.ValidationError("Departure can't be in the past.")
        if value > now + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(
                f"Departure must be within {MAX_DAYS_AHEAD} days; forecasts don't reach further."
            )
        return value

    def validate(self, attrs):
        if " ".join(attrs["origin"].lower().split()) == " ".join(attrs["destination"].lower().split()):
            raise serializers.ValidationError({"destination": ["Destination must differ from origin."]})
        return attrs
