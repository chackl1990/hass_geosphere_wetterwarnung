import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_EXTRA_COORDS,
    DEFAULT_EXTRA_COORDS,
    CONF_GRACE_PERIOD,
    DEFAULT_GRACE_PERIOD,
    MIN_GRACE_PERIOD,
    MAX_GRACE_PERIOD,
    STEP_GRACE_PERIOD,
)


class GeosphaereWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config-Flow fÇ¬r GeosphÇÏre Wetterwarnung."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        # Nur eine Instanz zulassen
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            seconds = user_input[CONF_SCAN_INTERVAL]
            extra_coords = user_input.get(CONF_EXTRA_COORDS, DEFAULT_EXTRA_COORDS)
            grace_period = user_input.get(CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD)
            return self.async_create_entry(
                title="GeosphÇÏre Wetterwarnung",
                data={
                    CONF_SCAN_INTERVAL: seconds,
                    CONF_EXTRA_COORDS: extra_coords,
                    CONF_GRACE_PERIOD: grace_period,
                },
            )

        # Slider: 30 bis 600, Schritt 30, Einheit "s"; Textfeld fÇ¬r Extra-Koordinaten
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30,
                        max=600,
                        step=30,
                        unit_of_measurement="s",
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_EXTRA_COORDS,
                    default=DEFAULT_EXTRA_COORDS,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=False)
                ),
                vol.Optional(
                    CONF_GRACE_PERIOD,
                    default=DEFAULT_GRACE_PERIOD,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_GRACE_PERIOD,
                        max=MAX_GRACE_PERIOD,
                        step=STEP_GRACE_PERIOD,
                        unit_of_measurement="s",
                        mode="slider",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_import(self, user_input=None) -> FlowResult:
        """YAML-Import (falls du das irgendwann nutzt) ƒ?" behandeln wie user-step."""
        return await self.async_step_user(user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Optionen fÇ¬r Scan-Intervall und Zusatz-Koordinaten."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            seconds = user_input[CONF_SCAN_INTERVAL]
            extra_coords = user_input.get(CONF_EXTRA_COORDS, DEFAULT_EXTRA_COORDS)
            grace_period = user_input.get(CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD)
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: seconds,
                    CONF_EXTRA_COORDS: extra_coords,
                    CONF_GRACE_PERIOD: grace_period,
                },
            )

        defaults = self.config_entry.options or self.config_entry.data
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30,
                        max=600,
                        step=30,
                        unit_of_measurement="s",
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_EXTRA_COORDS,
                    default=defaults.get(CONF_EXTRA_COORDS, DEFAULT_EXTRA_COORDS),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=False)
                ),
                vol.Optional(
                    CONF_GRACE_PERIOD,
                    default=defaults.get(CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_GRACE_PERIOD,
                        max=MAX_GRACE_PERIOD,
                        step=STEP_GRACE_PERIOD,
                        unit_of_measurement="s",
                        mode="slider",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
