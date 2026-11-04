# Agent instructions – my-weather

## Mandatory read before edits
Read this file, README.md, CHANGELOG.md, custom_components/my_weather/manifest.json,
custom_components/my_weather/config_flow.py, __init__.py, coordinator.py, sensor.py,
weather.py, secrets.py, timing.py, const.py, services.yaml, strings.json and translations/*.
Read all relevant tests, RELEASE_NOTES.md, and CONTRIBUTING.md before changing functionality. Compare the default branch
and recent pull requests to avoid reintroducing removed regressions.

## Non-negotiable behavior
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
- Never clear sensor data because of HTTP 429/key switching; never use hourly
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

## Releases
A passing syntax/JSON workflow alone does not certify runtime correctness.
Use a reviewed PR and validate Home Assistant config-flow, scheduler, timezone,
API errors, and hour rollover before merging/releasing. Never claim a GitHub
release exists without checking GitHub.
