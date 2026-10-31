# Risk model

How the app turns forecast weather and load weight into a risk level per checkpoint, and how it picks a route. All thresholds live in one config module so they can be checked against this page in one place.

## Levels

| Level | Value |
|---|---|
| Low | 0 |
| Moderate | 1 |
| High | 2 |
| Severe | 3 |
| No Travel | 4 |

## Weather thresholds

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | < 25 | 25–34 | 35–44 | 45–54 | ≥ 55 |
| Rain (in/hr) | < 0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | > 1.00 |
| Snow (in/hr) | < 0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | > 3.0 |

### Boundary handling

Neighbouring ranges in the table share their end values (rain 0.10–0.25 and 0.25–0.50 both include 0.25), and wind uses whole numbers, which leaves a gap between 34 and 35. The app reads each band as running from its lower bound up to, but not including, the next band's lower bound. The last band before No Travel includes its top value, because the table writes No Travel as "greater than".

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind `w` | w < 25 | 25 ≤ w < 35 | 35 ≤ w < 45 | 45 ≤ w < 55 | w ≥ 55 |
| Rain `r` | r < 0.10 | 0.10 ≤ r < 0.25 | 0.25 ≤ r < 0.50 | 0.50 ≤ r ≤ 1.00 | r > 1.00 |
| Snow `s` | s < 0.5 | 0.5 ≤ s < 1.0 | 1.0 ≤ s < 2.0 | 2.0 ≤ s ≤ 3.0 | s > 3.0 |

## Checkpoint level

1. Classify wind, rain and snow separately.
2. The checkpoint level is the **highest** of the three.
3. Apply the load rules, which can only raise the level:

| Wind | Load | Result |
|---|---|---|
| ≥ 55 mph | any | No Travel |
| 45–54 mph | > 30,000 lb | No Travel |
| 35–44 mph | > 40,000 lb | at least Severe |

A checkpoint whose ETA is past the end of the forecast gets the level **No Forecast** instead (see below).

Each checkpoint keeps a list of reasons, for example `wind 47 mph → Severe` and `load 34,000 lb > 30,000 lb with wind 45–54 mph → No Travel`. The map popup shows these, so every level can be traced back to its rule.

### Examples

| Wind | Rain | Snow | Load | Level | Why |
|---|---|---|---|---|---|
| 20 mph | 0.00 | 0.0 | 45,000 lb | Low | Nothing triggered |
| 40 mph | 0.00 | 0.0 | 40,000 lb | High | Load not over 40,000 |
| 40 mph | 0.00 | 0.0 | 40,001 lb | Severe | Load rule |
| 47 mph | 0.00 | 0.0 | 30,000 lb | Severe | Load not over 30,000 |
| 47 mph | 0.00 | 0.0 | 30,001 lb | No Travel | Load rule |
| 10 mph | 0.00 | 2.5 | 10,000 lb | Severe | Snow |
| 56 mph | 0.00 | 0.0 | 1,000 lb | No Travel | Wind alone |

## Weather inputs

Weather comes from the Open-Meteo hourly forecast, requested in mph and inches.

- **Wind:** `wind_speed_10m` (sustained). Gusts are shown but not scored.
- **Rain:** `rain + showers`. Open-Meteo splits large-scale rain from convective showers; both are rain on the road.
- **Snow:** `snowfall`.
- **Which hour:** rain, showers and snowfall are totals for the hour *before* each timestamp, so a checkpoint reached at 14:20 uses the 15:00 value, which covers 14:00–15:00. Wind uses the nearest hour.
- **Out of range:** if the ETA is past the end of the forecast, the checkpoint is marked "No Forecast" and is not scored as Low. Departures must precede UTC midnight today + 16 days - 49 hours, reserving all slider frames and the next precipitation timestamp. Missing heatmap forecasts produce a visible warning at the affected hour.
- **Provider failure:** if the weather API fails, the request fails. The app never returns a plan with silently missing weather.

## Route summary

### Which miles belong to which checkpoint

Every mile of road takes the level of its **nearest checkpoint**, so each checkpoint covers half the gap to its neighbour on each side.

Example: a 55-mile route sampled every 25 miles.

| Checkpoint | At mile | Covers miles | Length |
|---|---|---|---|
| A (origin) | 0 | 0 – 12.5 | 12.5 |
| B | 25 | 12.5 – 37.5 | 25 |
| C | 50 | 37.5 – 52.5 | 15 |
| D (destination) | 55 | 52.5 – 55 | 2.5 |

The origin and destination get real mileage, no mile is counted twice, and the lengths add up to the route distance.

### Per-route values

- `no_travel_mi`, `severe_mi`, `high_mi`, `no_forecast_mi`: miles at each level
- `has_no_travel`: true if **any** checkpoint is No Travel, regardless of how many miles it covers
- `forecast_complete`: true if every checkpoint has a forecast
- `avg_risk`: distance-weighted average of the level values (0–4) over the miles that have a forecast
- `duration_min`: travel time from the routing API

## Route ranking

Routes are sorted by these keys in order; a later key only matters when every earlier key is equal.

1. Has a No Travel checkpoint (routes without come first)
2. Has a checkpoint with no forecast (fully covered routes come first)
3. Fewest Severe miles
4. Fewest High miles
5. Lowest average risk
6. Shortest travel time

Keys 3–6 are the brief's preference order. The first two are added because the brief doesn't cover them:

- **No Travel:** a route the rules say not to drive should never be recommended over one that is drivable. If every route has a No Travel checkpoint, the app recommends none and says so.
- **Missing forecast:** miles without a forecast are unknown, not safe. A route with a gap in its forecast never beats a fully covered route, so missing data can't make a route look better.

Values are compared unrounded. Two numbers count as equal only when they differ by less than 10⁻⁹, which absorbs floating-point noise without merging genuinely different risks (0.821 still beats 0.824). Rounding is for display only.

Risk comes before travel time, so a faster route only wins when the routes are equally safe.

## Heat score

The heatmap needs a value that changes smoothly, so that weather building towards a threshold shows before it crosses it. Each condition is placed on a 0–4 scale, linear between its thresholds:

| Condition | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Wind (mph) | 0 | 25 | 35 | 45 | 55 |
| Rain (in/hr) | 0 | 0.10 | 0.25 | 0.50 | 1.00 |
| Snow (in/hr) | 0 | 0.5 | 1.0 | 2.0 | 3.0 |

So 30 mph wind is 1.5, and 0.375 in/hr of rain is 2.5. The worst condition counts. The result is then raised to at least the point's level (which includes the load rules) and capped just below the next level, so **the whole part of the heat score always equals the level**. The heatmap can't show a point as Severe when its level is High, or the other way round. No Travel is always 4.

The heat score is only used for drawing. Ranking and checkpoint levels use the levels above.
