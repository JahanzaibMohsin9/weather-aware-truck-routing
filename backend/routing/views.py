import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import HeatmapRequestSerializer, PlanRequestSerializer
from .services.errors import InvalidTrip, NoRouteFound, PlaceNotFound, ProviderError
from .services.heatmap import build_heatmap
from .services.planner import PlanRequest, plan_trip
from .services.tomtom import TomTomClient
from .services.weather import OpenMeteoClient

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan(request):
    serializer = PlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = plan_trip(
            PlanRequest(**serializer.validated_data),
            tomtom=TomTomClient(settings.TOMTOM_API_KEY),
            weather=OpenMeteoClient(),
        )
    except PlaceNotFound as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Couldn't find a place called '{exc}'.")
    except NoRouteFound:
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "No truck route was found between these places.")
    except InvalidTrip as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
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
    try:
        result = build_heatmap(routes, load_lbs=data["load_lbs"], start=data["start"], weather=OpenMeteoClient())
    except ProviderError:
        logger.exception("Weather provider failed")
        return _error(status.HTTP_502_BAD_GATEWAY, "The weather service didn't respond properly. Please try again.")
    return Response(result)


def _error(code: int, detail: str) -> Response:
    return Response({"detail": detail}, status=code)
