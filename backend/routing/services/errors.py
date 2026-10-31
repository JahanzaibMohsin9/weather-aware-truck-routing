class ProviderError(Exception):
    """An external API failed or returned something unusable (HTTP 502)."""


class PlaceNotFound(Exception):
    """Geocoding found nothing for the text the user typed (HTTP 422)."""


class NoRouteFound(Exception):
    """The routing API found no route between the points (HTTP 422)."""


class InvalidTrip(Exception):
    """The input is well-formed but the trip can't be planned (HTTP 422)."""
