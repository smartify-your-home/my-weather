## 0.1.3.4 – 2026-11-08

# Changelog

All notable changes are documented here; only published versions should be
treated as releases.

## [Unreleased]

## [0.1.3.7] – 2026-11-13

- Optional direct GeoSphere Austria C-LAEF (`nwp-v2-1h-1km`) solar forecast without API key. Independent 3-hour update and local cache, no Meteonomiqs quota impact.
- New GeoSphere global radiation, cloud 60h, irradiation 60h and model-run sensors. Preserve missing forecast values rather than inventing zeros.
- Separate `my_weather.update_solar` service; no change to existing Meteonomiqs scheduling, card registration or sensors. Fixed 60h sensor dispatch, polling timer starvation and HA unload cleanup before release.
- New parser and sensor tests for units, time alignment, missing values, cache, 60h state/attributes and hour rollover. Runtime testing against a running Home Assistant instance and actual API response remains outstanding.


## [0.1.3.6] – 2026-11-11

- Fix: the bundled cloud chart could permanently show "Configuration error"
  (`Custom element doesn't exist: my-weather-cloud-8h-card`) until the page was
  reloaded. It was loaded only through `add_extra_js_url` in the page head and
  could run before Home Assistant's custom-element polyfill.
- The card is now registered as a Lovelace resource (storage mode, created and
  updated automatically after Home Assistant has started, with retries). In
  Lovelace YAML mode the previous frontend loading remains as fallback and the
  log names the URL for a manual resource entry.
- No change to sensors, API requests, scheduling or key handling.
- Not verified in a running Home Assistant installation; offline tests cover
  resource creation, update, de-duplication, retry and the YAML fallback.

## [0.1.3.5] – 2026-11-08

- Add separate Meteonomiqs Cloud Forecast 48h sensor with actual available/valid hour counts, keeping the existing 8h sensor unchanged.
- Existing cloud card supports selectable 8h/24h/48h views and scrolling long timelines; uses cached API response only.
- SEP may select the new sensor for extended PV planning; missing/stale forecast hours remain unknown and no extra API fetch is made.

- Add 8-hour cloud coverage forecast (mean % sensor with timestamped `forecast`
  attribute) to support SEP weather-aware PV modelling without extra API calls.
- Add responsive built-in Lovelace cloud chart and regression tests for missing
  data, timestamp alignment and stale cache; no changes to 401/403/429 handling.
- CI runs once for feature-branch pull requests and on main pushes, avoiding redundant push-triggered runs.
- Replace version-pinned structure assertion with a version-format check so future normal releases do not generate false failures.
- Keep real test errors failing visibly; account email notification settings remain user-controlled.

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
