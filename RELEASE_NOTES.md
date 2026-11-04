# my-weather 0.1.3.1

## New features
- Up to four configured full-hour publication slots in the integration options.
- Forecast download five minutes ahead of each configured hour, with a staged
  snapshot published together at the hour.
- Automatic loading of **one to four** fixed API-key secrets from
  `/config/secrets.yaml` under the names `my_weather_api_1` through
  `my_weather_api_4`; missing slots, including gaps, are allowed.
- Manual refresh service remains available and publishes immediately.

## Fixes
- Avoid spurious use of the oldest forecast interval after API errors.
- Handle timezone offsets and forecast-hour changes using actual timestamps.
- Keep cached data during HTTP 429/key rotation.
- Make quota warning thresholds depend on the number of available API keys.

## Migration
Existing manual API key configuration remains functional if no fixed secrets
are defined. To switch, place one or more fixed keys in `/config/secrets.yaml`
and reload the integration. Use the fixed secret names exactly; you do not need
to enter names in the UI. Older plaintext keys saved in config entries are
not automatically erased.

## Testing limitations
Static validation and unit tests passed on the PR. Live Home Assistant integration testing, API response timing, restarts near an hour boundary and recorder/history validation have **not** yet been verified; treat scheduled publishing as a new behavior and monitor its first runs.

See CHANGELOG.md for the versioned change list.
