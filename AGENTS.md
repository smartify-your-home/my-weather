# Agent instructions – my-weather

## Mandatory read before edits
Read this file, README.md, CHANGELOG.md, custom_components/my_weather/manifest.json,
custom_components/my_weather/config_flow.py, __init__.py, coordinator.py, sensor.py,
weather.py, secrets.py, timing.py, api_errors.py, const.py, services.yaml, strings.json and translations/*.
Read all relevant tests, RELEASE_NOTES.md, and CONTRIBUTING.md before changing functionality. Compare the default branch
and recent pull requests to avoid reintroducing removed regressions.

## Non-negotiable behavior
- Extended 48h bridge: introduce separate sensor and preserve the legacy 8h sensor. `forecast_hours` on 48h sensor is the actual number of returned intervals, not always 48; `valid_cloud_hours` counts non-null clouds. No API calls from chart or from extra sensors. 8/24/48 chart views must not invent missing data.
- Eight-hour cloud bridge: keep `sensor.meteonomiqs_cloud_forecast_8h`
  forecast attribute as `[{datetime, end, cloud_coverage}]`, percent 0–100
  or null. No extra weather fetch, no fallback to stale hourly[0]. Preserve
  card resource registration and its Home Assistant theme compatibility.
- Cloud card loading (0.1.3.6): the card is registered as a Lovelace storage
  resource (`card_resource.py`, after `homeassistant_started`, with retries).
  Do NOT load it via `add_extra_js_url` by default: extra JS in the page head
  can run before the frontend's custom-element polyfill and then causes a
  permanent "Configuration error / Custom element doesn't exist". Extra JS is
  only the fallback when no storage resource can be created (YAML mode).
  Listeners calling `hass.async_*` must be `@callback`. Tests:
  `tests/test_card_resource.py`.
- HACS-compatible Home Assistant custom integration, domain `my_weather`.
- Automatic discovery of **one to four** API keys from the fixed secret names
  `my_weather_api_1` ... `my_weather_api_4` in Home Assistant secrets.yaml.
  Missing slots, including gaps, MUST be accepted; invalid *present* slots fail.
  Never print, log, copy into config-entry data, or commit actual API key values.
- Keep backwards compatibility for existing manually configured API keys.
- Keep manual `my_weather.update` working and publishing immediately.
- Scheduled full-hour publication (up to 4 times/day, local timezone): prefetch
  five minutes before, stage without sensor changes, publish coherent snapshot
  at the hour. Fall back safely if request fails or is late.
- Never clear sensor data because of HTTP 401/403/429 key switching; never use hourly
  array index 0 as a fallback when the current forecast hour is absent.
- Honor the Meteonomiqs quota. No implicit polling when no schedule is selected.

## Update requirements
For every changed behavior:
1. Add/adjust focused regression tests including the failure path and HA restart.
2. Update README.md, CHANGELOG.md, relevant translations in DE/EN/FR/IT/ES,
   and descriptions in HA services/options as applicable.
3. Check that all Python compiles and all translation JSON parses; run tests.
4. Verify HACS paths/manifest and version before a release.
5. Never silently remove previous fixes or functions while refactoring.
6. Describe untested runtime scenarios explicitly in the PR and release notes.

## CI noise policy
Run validation for pull requests and main branch pushes only. Avoid redundant branch push
runs and brittle assertions tied to a specific released version. Never silence genuine
CI failures with `continue-on-error`, unconditional success, or skipped validations.

## Releases
A passing syntax/JSON workflow alone does not certify runtime correctness.
Use a reviewed PR and validate Home Assistant config-flow, scheduler, timezone,
API errors, and hour rollover before merging/releasing. Never claim a GitHub
release exists without checking GitHub.
