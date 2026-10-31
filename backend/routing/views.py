import logging
import time

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import HeatmapRequestSerializer, PlanRequestSerializer
from .services.errors import InvalidTrip, NoRouteFound, PlaceNotFound, ProviderError, ProviderTimeout
from .services.heatmap import build_heatmap
from .services.planner import PlanRequest, plan_trip
from .services.tomtom import TomTomClient
from .services.weather import OpenMeteoClient

logger = logging.getLogger(__name__)

# Heroku's router drops any request that takes longer than 30 s. All the calls
# a request makes to TomTom and Open-Meteo share this budget, so a slow
# provider gets a clear "try again" message instead of the router's error page.
REQUEST_BUDGET_S = 25.0

TOO_SLOW = "The routing or weather service is responding slowly right now. Please try again in a moment."


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan(request):
    serializer = PlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    deadline = time.monotonic() + REQUEST_BUDGET_S
    try:
        result = plan_trip(
            PlanRequest(**serializer.validated_data),
            tomtom=TomTomClient(settings.TOMTOM_API_KEY, deadline=deadline),
            weather=OpenMeteoClient(deadline=deadline),
        )
    except PlaceNotFound as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Couldn't find a place called '{exc}'.")
    except NoRouteFound:
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "No truck route was found between these places.")
    except InvalidTrip as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except ProviderTimeout:
        logger.warning("Plan request ran out of time")
        return _error(status.HTTP_504_GATEWAY_TIMEOUT, TOO_SLOW)
    except ProviderError:
        logger.exception("External provider failed")
        return _error(
            status.HTTP_502_BAD_GATEWAY,
            "A routing or weather service didn't respond properly. Please try again.",
        )
    return Response(result)


@api_view(["POST"])
def heatmap(request):
    serializer = HeatmapRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    routes = [[(lat, lng) for lng, lat in route] for route in data["routes"]]
    weather = OpenMeteoClient(deadline=time.monotonic() + REQUEST_BUDGET_S)
    try:
        result = build_heatmap(routes, load_lbs=data["load_lbs"], start=data["start"], weather=weather)
    except ProviderTimeout:
        logger.warning("Heatmap request ran out of time")
        return _error(status.HTTP_504_GATEWAY_TIMEOUT, TOO_SLOW)
    except ProviderError:
        logger.exception("Weather provider failed")
        return _error(status.HTTP_502_BAD_GATEWAY, "The weather service didn't respond properly. Please try again.")
    return Response(result)


def _error(code: int, detail: str) -> Response:
    return Response({"detail": detail}, status=code)
