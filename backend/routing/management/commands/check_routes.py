"""Try a real trip against TomTom and print what comes back.

    python manage.py check_routes "Dallas, TX" "Denver, CO" --load 36000 --interval 25
"""

from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.management.base import BaseCommand

from routing.domain.geo import build_checkpoints, shared_fraction
from routing.services.routes import find_routes
from routing.services.tomtom import TomTomClient


class Command(BaseCommand):
    help = "Geocode two places, fetch three truck routes and list their checkpoints."

    def add_arguments(self, parser):
        parser.add_argument("origin")
        parser.add_argument("destination")
        parser.add_argument("--load", type=float, default=36000, help="load in lb")
        parser.add_argument("--interval", type=float, default=25, help="checkpoint spacing in miles")
        parser.add_argument("--hours-ahead", type=float, default=2, help="departure from now")

    def handle(self, *args, **opts):
        client = TomTomClient(settings.TOMTOM_API_KEY)
        origin = client.geocode(opts["origin"])
        destination = client.geocode(opts["destination"])
        self.stdout.write(f"From {origin.label} {origin.point}")
        self.stdout.write(f"To   {destination.label} {destination.point}")

        depart = datetime.now(timezone.utc) + timedelta(hours=opts["hours_ahead"])
        routes, notes = find_routes(
            client, origin.point, destination.point, load_lbs=opts["load"], depart_at=depart
        )
        self.stdout.write(f"\n{len(routes)} route(s), departing {depart:%Y-%m-%d %H:%M}Z")
        for note in notes:
            self.stdout.write(self.style.WARNING(note))

        for idx, route in enumerate(routes):
            checkpoints = build_checkpoints(route.points, opts["interval"], route.profile, depart)
            overlaps = ", ".join(
                f"{chr(65 + j)} {shared_fraction(route.points, other.points):.0%}"
                for j, other in enumerate(routes)
                if j != idx
            )
            self.stdout.write(
                f"\nRoute {chr(65 + idx)} ({route.source}): {route.distance_mi:.1f} mi, "
                f"{route.duration_s / 3600:.2f} h, {len(route.points)} points, "
                f"{len(checkpoints)} checkpoints; shared with {overlaps or '-'}"
            )
            shown = checkpoints if len(checkpoints) <= 5 else [*checkpoints[:3], None, *checkpoints[-2:]]
            for cp in shown:
                if cp is None:
                    self.stdout.write("   ...")
                    continue
                self.stdout.write(
                    f"   mile {cp.mile:7.1f}  ({cp.lat:.4f}, {cp.lng:.4f})  ETA {cp.eta:%m-%d %H:%M}Z"
                )
