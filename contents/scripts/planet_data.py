#!/usr/bin/env python3
"""
Mini Planet data helper.

Fetches weather conditions from the OpenWeatherMap current weather endpoint and computes
an approximate moon phase. Results are cached to keep API usage low.

Configuration order of precedence:
1. Environment variables MINIPLANET_LAT, MINIPLANET_LON, MINIPLANET_LOCATION_NAME (optional)
2. JSON file at ~/.config/miniplanet/config.json containing {"lat": ..., "lon": ..., "location_name": ...}
3. Fallback coordinates (0, 0) when nothing else is supplied.

Set the OpenWeatherMap API key via the OPENWEATHER_API_KEY environment variable or
"api_key" field inside the config file.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

CACHE_TTL_SECONDS = 55 * 60
CACHE_PATH = Path.home() / ".cache" / "miniplanet" / "planet_cache.json"
CONFIG_PATH = Path.home() / ".config" / "miniplanet" / "config.json"
WEATHER_ENDPOINT = "https://api.openweathermap.org/data/2.5/weather"


class MiniPlanetError(Exception):
    """Custom exception for predictable data issues."""


def ensure_dirs() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def resolve_coordinates(config: Dict[str, Any]) -> Dict[str, Any]:
    lat = os.environ.get("MINIPLANET_LAT")
    lon = os.environ.get("MINIPLANET_LON")
    location_name = os.environ.get("MINIPLANET_LOCATION_NAME")
    if lat is None or lon is None:
        lat = config.get("lat")
        lon = config.get("lon")
        location_name = location_name or config.get("location_name")

    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        raise MiniPlanetError("Invalid latitude/longitude supplied.")

    if lat is None or lon is None:
        # Default to Null Island; encourages user to configure coordinates.
        lat, lon = 0.0, 0.0
        location_name = location_name or "Configure coordinates"

    return {"lat": lat, "lon": lon, "location_name": location_name or ""}


def resolve_api_key(config: Dict[str, Any]) -> Optional[str]:
    return os.environ.get("OPENWEATHER_API_KEY") or config.get("api_key")


def read_cache() -> Optional[Dict[str, Any]]:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    timestamp = data.get("timestamp")
    if not isinstance(timestamp, (float, int)):
        return None
    age = _dt.datetime.now(_dt.timezone.utc).timestamp() - timestamp
    if age > CACHE_TTL_SECONDS:
        return None
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return None
    return payload


def write_cache(payload: Dict[str, Any]) -> None:
    ensure_dirs()
    bundle = {
        "timestamp": _dt.datetime.now(_dt.timezone.utc).timestamp(),
        "payload": payload,
    }
    try:
        CACHE_PATH.write_text(json.dumps(bundle), encoding="utf-8")
    except OSError:
        pass


def fetch_weather(api_key: str, lat: float, lon: float, units: str = "metric") -> Dict[str, Any]:
    query = urlencode(
        {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": units,
        }
    )
    url = f"{WEATHER_ENDPOINT}?{query}"
    try:
        with urlopen(url, timeout=10) as response:
            content = response.read().decode("utf-8")
    except HTTPError as exc:
        raise MiniPlanetError(f"Weather API error: {exc.code}") from exc
    except URLError as exc:
        raise MiniPlanetError("Weather service unreachable") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise MiniPlanetError("Invalid response from weather service") from exc

    weather_entries = payload.get("weather") or []
    weather = weather_entries[0] if weather_entries else {}
    main = payload.get("main", {})
    sys_info = payload.get("sys", {})

    try:
        temp = round(float(main.get("temp", 0)))
    except (TypeError, ValueError):
        temp = 0

    condition = weather.get("main") or weather.get("description") or "Unknown"
    icon = str(weather.get("icon") or "")
    is_day = icon.endswith("d")

    # Fall back to sunrise/sunset check if icon missing.
    if not icon:
        now_ts = payload.get("dt") or _dt.datetime.now(_dt.timezone.utc).timestamp()
        sunrise = sys_info.get("sunrise")
        sunset = sys_info.get("sunset")
        if sunrise and sunset:
            is_day = sunrise <= now_ts < sunset

    return {
        "temp": temp,
        "condition": condition.title(),
        "is_day": is_day,
    }


def moon_phase_name(date: Optional[_dt.date] = None) -> str:
    """Return a coarse moon phase label mapped to available assets."""
    if date is None:
        date = _dt.datetime.now(_dt.timezone.utc).date()

    # Simple Conway moon phase algorithm.
    year = date.year
    month = date.month
    day = date.day

    if month < 3:
        year -= 1
        month += 12

    a = math.floor(year / 100)
    b = math.floor(a / 4)
    c = 2 - a + b
    e = math.floor(365.25 * (year + 4716))
    f = math.floor(30.6001 * (month + 1))
    julian_day = c + day + e + f - 1524.5

    # Days since known new moon (January 6, 2000 18:14 UT)
    days_since_new = julian_day - 2451550.1
    synodic_month = 29.53058867
    age = days_since_new % synodic_month

    if age < 1.0 or age > 28.5:
        return "new"
    if 1.0 <= age < 6.5:
        return "half"
    if 6.5 <= age < 12.5:
        return "waning" if age > synodic_month / 2 else "half"
    if 12.5 <= age < 17.5:
        return "full"
    if 17.5 <= age < 23.5:
        return "waning"
    return "half"


def make_payload(api_key: Optional[str], lat: float, lon: float, units: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "temp": "--",
        "condition": "Configure API",
        "is_day": True,
        "moon_phase": moon_phase_name(),
    }

    if not api_key:
        return result

    weather = fetch_weather(api_key, lat, lon, units)
    result.update(weather)
    result["moon_phase"] = moon_phase_name()
    return result


def main() -> None:
    config = load_config()
    coords = resolve_coordinates(config)
    api_key = resolve_api_key(config)
    units = config.get("units") or os.environ.get("MINIPLANET_UNITS", "metric")

    cached = read_cache()
    if cached is not None:
        print(json.dumps(cached))
        return

    try:
        payload = make_payload(api_key, coords["lat"], coords["lon"], units)
    except MiniPlanetError as exc:
        payload = {
            "temp": "--",
            "condition": str(exc),
            "is_day": True,
            "moon_phase": moon_phase_name(),
        }

    write_cache(payload)
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
