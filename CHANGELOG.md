# Changelog

All notable changes are documented here; only published versions should be
treated as releases.

## [0.1.3.3] – 2026-11-07

- Rotate to the next configured API key when the provider returns HTTP 401 or 403, as well as HTTP 429.
- Try each loaded key at most once per scheduled/manual request.
- Keep previously cached data on denied API requests; report HTTP status and key slot without exposing secrets.
- Preserve original errors instead of wrapping `UpdateFailed` a second time.

## [0.1.3.2] – 2026-11-04

- Fix Home Assistant integration reload/unload: remove erroneous recursive call to `ConfigEntry.async_unload()`.
- Add regression test to ensure the integration delegates config-entry lifecycle to Home Assistant.

## [0.1.3.1] – 2026-11-04

- HACS options for up to four **full-hour** publication times per day.
- Scheduled API prefetch five minutes before the hour, with deferred atomic
  sensor publication at the configured hour.
- Timestamp-aligned hourly forecast, avoiding invalid first-index fallback.
- Preserve cached forecast across HTTP 429 API-key rotation and errors.
- Automatic detection of **one to four** API keys in secrets.yaml with fixed
  names `my_weather_api_1` ... `my_weather_api_4`.
  Missing slots (including gaps) are allowed; duplicates are ignored.
- Keep direct-key configuration as a legacy fallback.
- Refreshed documentation, all five language translations and service metadata.
- Added AGENTS.md, CONTRIBUTING.md, SECURITY.md, .gitignore, issue template, and CI checks for translations and timestamp calculations.
- API quota status now uses the active key count instead of fixed two-key thresholds.
- Expanded regression tests and CI validation.

Live Home Assistant runtime scenarios have not all been verified; see RELEASE_NOTES.md. Prior historical version notes were not reconstructed because authoritative release history has not been verified.
