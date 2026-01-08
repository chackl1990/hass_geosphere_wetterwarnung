from __future__ import annotations

import logging
from datetime import timedelta
from typing import List, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_EXTRA_COORDS,
    DEFAULT_EXTRA_COORDS,
    CONF_GRACE_PERIOD,
    DEFAULT_GRACE_PERIOD,
)

_LOGGER = logging.getLogger(__name__)


def _parse_extra_coords(text: str) -> List[Tuple[float, float]]:
    """Parse Eingabe 'lat1,lon1;lat2,lon2' zu Float-Tupeln."""
    if not text:
        return []
    coords: List[Tuple[float, float]] = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        pieces = part.split(",")
        if len(pieces) != 2:
            continue
        try:
            lat = float(pieces[0].strip())
            lon = float(pieces[1].strip())
        except (TypeError, ValueError):
            continue
        coords.append((lat, lon))
    return coords


def _has_active_warnings(warnings: list[dict], now_utc) -> bool:
    now_ts = int(now_utc.timestamp())
    for w in warnings:
        raw = w.get("properties", {}).get("rawinfo", {})
        try:
            start = int(raw.get("start", 0))
            end = int(raw.get("end", 0))
        except (TypeError, ValueError):
            continue
        if start <= now_ts <= end:
            return True
    return False


class GeosphaereCoordinator(DataUpdateCoordinator):
    """Coordinator für Geosphere Wetterwarnung."""

    def __init__(self, hass: HomeAssistant, config_entry):
        self.hass = hass
        self.config_entry = config_entry

        # Felder für API-Status
        self.last_http_status: int | None = None
        self.last_http_response: str | None = None
        self.had_partial_failure: bool = False
        self._last_successful_data: dict | None = None
        self._last_non_empty_data: dict | None = None
        self._last_non_empty_utc = None
        self._last_active_data: dict | None = None
        self._last_active_utc = None
        self.last_request_utc = None

        scan_interval = self._get_entry_value(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Daten von der ZAMG / Geosphere API holen."""
        self.last_request_utc = dt_util.utcnow()
        grace_seconds = self._get_entry_value(
            CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD
        )
        grace_delta = timedelta(seconds=grace_seconds)

        zone = self.hass.states.get("zone.home")
        if zone is None:
            self.last_http_status = None
            self.last_http_response = "zone.home not found"
            raise UpdateFailed("zone.home not found")

        lon = zone.attributes.get("longitude")
        lat = zone.attributes.get("latitude")
        if lon is None or lat is None:
            self.last_http_status = None
            self.last_http_response = "zone.home has no coordinates"
            raise UpdateFailed("zone.home has no coordinates")

        coords: List[Tuple[float, float]] = []
        try:
            coords.append((float(lat), float(lon)))
        except (TypeError, ValueError):
            self.last_http_status = None
            self.last_http_response = "zone.home has invalid coordinates"
            raise UpdateFailed("zone.home has invalid coordinates")

        extra = self._get_entry_value(CONF_EXTRA_COORDS, DEFAULT_EXTRA_COORDS)
        coords.extend(_parse_extra_coords(extra))
        if not coords:
            self.last_http_status = None
            self.last_http_response = "no coordinates to query"
            raise UpdateFailed("no coordinates to query")

        session = async_get_clientsession(self.hass)
        combined_warnings: list = []
        any_success = False
        max_http_status: int | None = None
        error_messages: list[str] = []

        for lat_val, lon_val in coords:
            url = (
                "https://warnungen.zamg.at/wsapp/api/getWarningsForCoords"
                f"?lon={lon_val}&lat={lat_val}&lang=de"
            )
            try:
                async with session.get(url, timeout=10) as resp:
                    status = resp.status
                    if max_http_status is None or status > max_http_status:
                        max_http_status = status

                    if status != 200:
                        try:
                            text = await resp.text()
                        except Exception:  # noqa: BLE001
                            text = "<no body>"
                        error_messages.append(
                            f"{lat_val},{lon_val}: HTTP {status} {text}"
                        )
                        continue

                    data = await resp.json()
                    any_success = True

                    props = data.get("properties", {}) or {}
                    warnings = props.get("warnings", []) or []
                    combined_warnings.extend(warnings)

            except Exception as err:  # noqa: BLE001
                error_messages.append(f"{lat_val},{lon_val}: {err!r}")
                continue

        self.had_partial_failure = bool(error_messages)
        if max_http_status is None:
            max_http_status = 200 if any_success else None
        self.last_http_status = max_http_status
        self.last_http_response = "; ".join(error_messages) if error_messages else None

        if any_success:
            result = {"properties": {"warnings": combined_warnings}}
            self._last_successful_data = result
            if combined_warnings:
                self._last_non_empty_data = result
                self._last_non_empty_utc = self.last_request_utc
                has_active = _has_active_warnings(
                    combined_warnings, self.last_request_utc
                )
                if has_active:
                    self._last_active_data = result
                    self._last_active_utc = self.last_request_utc
                    return result

                if (
                    self._last_active_data is not None
                    and self._last_active_utc is not None
                ):
                    age = self.last_request_utc - self._last_active_utc
                    if age <= grace_delta:
                        return self._last_active_data
                return result

            if (
                self._last_active_data is not None and self._last_active_utc is not None
            ):
                age = self.last_request_utc - self._last_active_utc
                if age <= grace_delta:
                    return self._last_active_data
            if (
                self._last_non_empty_data is not None
                and self._last_non_empty_utc is not None
            ):
                age = self.last_request_utc - self._last_non_empty_utc
                if age <= grace_delta:
                    return self._last_non_empty_data
            return result

        if self._last_successful_data is not None:
            return self._last_successful_data

        raise UpdateFailed("Error fetching data: all requests failed")

    def set_update_interval(self, seconds: int) -> None:
        """Update-Intervall ändern (falls du später doch Optionen nutzt)."""
        self.update_interval = timedelta(seconds=seconds)

    def _get_entry_value(self, key: str, default):
        """Hole Wert bevorzugt aus Optionen, sonst aus Daten."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )
