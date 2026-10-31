import json
import logging
import queue
import threading
import time

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import HeatmapRequestSerializer, PlaceSearchSerializer, PlanRequestSerializer
from .services.errors import InvalidTrip, NoRouteFound, PlaceNotFound, ProviderError, ProviderTimeout
from .services.heatmap import build_heatmap
from .services.planner import PlanRequest, Progress, plan_trip
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


PLACES_BUDGET_S = 5.0


@api_view(["GET"])
def places(request):
    """Autocomplete: up to five places matching ?q=, e.g. "Dall" -> Dallas, TX."""
    serializer = PlaceSearchSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    client = TomTomClient(settings.TOMTOM_API_KEY, deadline=time.monotonic() + PLACES_BUDGET_S)
    try:
        found = client.suggest(serializer.validated_data["q"])
    except ProviderError:
        logger.warning("Place suggestions failed", exc_info=True)
        return _error(status.HTTP_502_BAD_GATEWAY, "Place suggestions are unavailable right now.")
    return Response({"places": [{"label": p.label, "lat": p.lat, "lng": p.lng} for p in found]})


def _run_plan(validated: dict, progress: Progress | None = None) -> dict:
    deadline = time.monotonic() + REQUEST_BUDGET_S
    options = {"progress": progress} if progress else {}
    return plan_trip(
        PlanRequest(**validated),
        tomtom=TomTomClient(settings.TOMTOM_API_KEY, deadline=deadline),
        weather=OpenMeteoClient(deadline=deadline),
        **options,
    )


def _plan_failure(exc: Exception) -> tuple[int, str]:
    """HTTP status and user-facing message for a planning error."""
    if isinstance(exc, PlaceNotFound):
        return status.HTTP_422_UNPROCESSABLE_ENTITY, f"Couldn't find a place called '{exc}'."
    if isinstance(exc, NoRouteFound):
        return status.HTTP_422_UNPROCESSABLE_ENTITY, "No truck route was found between these places."
    if isinstance(exc, InvalidTrip):
        return status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)
    if isinstance(exc, ProviderTimeout):
        logger.warning("Plan request ran out of time")
        return status.HTTP_504_GATEWAY_TIMEOUT, TOO_SLOW
    logger.exception("External provider failed", exc_info=exc)
    return status.HTTP_502_BAD_GATEWAY, "A routing or weather service didn't respond properly. Please try again."


PLAN_ERRORS = (PlaceNotFound, NoRouteFound, InvalidTrip, ProviderError)


@api_view(["POST"])
def plan(request):
    serializer = PlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = _run_plan(serializer.validated_data)
    except PLAN_ERRORS as exc:
        return _error(*_plan_failure(exc))
    return Response(result)


@api_view(["POST"])
def plan_stream(request):
    """The same plan as POST /api/plan, streamed as newline-delimited JSON:
    {"type": "progress", "step", "message"} lines while it works, then one
    {"type": "result", "plan"} or {"type": "error", "status", "detail"}.
    Invalid input still gets an ordinary 400 before anything is streamed."""
    serializer = PlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    events: queue.Queue = queue.Queue()

    def work():
        try:
            plan = _run_plan(
                serializer.validated_data,
                progress=lambda step, message: events.put({"type": "progress", "step": step, "message": message}),
            )
            events.put({"type": "result", "plan": plan})
        except PLAN_ERRORS as exc:
            code, detail = _plan_failure(exc)
            events.put({"type": "error", "status": code, "detail": detail})
        except Exception:
            logger.exception("Plan stream failed")
            events.put({"type": "error", "status": 500, "detail": "Something went wrong. Please try again."})
        finally:
            events.put(None)

    def lines():
        while (event := events.get()) is not None:
            yield json.dumps(event) + "\n"

    threading.Thread(target=work, daemon=True).start()
    response = StreamingHttpResponse(lines(), content_type="application/x-ndjson")
    response["Cache-Control"] = "no-cache"
    # GZipMiddleware buffers streamed output until the end, which would deliver
    # every progress line at once; it leaves responses with an encoding alone.
    response["Content-Encoding"] = "identity"
    return response


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
