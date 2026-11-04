# Changelog

All notable changes are documented here; only published versions should be
treated as releases.

## [Unreleased] – planned 0.1.3.1 (Pull Request #1)

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
- Expanded regression tests and CI validation.

**Not yet released.** Home Assistant runtime/integration tests are required
before publishing 0.1.3.1. Prior historical version notes were not
reconstructed because authoritative release history has not been verified.
