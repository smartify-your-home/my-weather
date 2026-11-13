# my-weather

A custom Home Assistant integration for the [Meteonomiqs](http://www.wetter.com) weather API. Provides current conditions, hourly forecasts, and daily forecasts as HA entities — including a full `weather` entity usable in the standard weather card.

> **Important:** The Meteonomiqs free tier allows only **50 API calls per key per month**. Automatic polling is **disabled by default**. You can configure up to four daily refresh times in the integration options, or call `my_weather.update` manually.

---
Use https://github.com/mlamberts78/weather-chart-card (HACS) or original HA weather card to show the data called by my-weather.

<img width="506" height="662" alt="image" src="https://github.com/user-attachments/assets/5f2bfa8f-0c91-4d6b-a67d-75b1cc812603" />




## Optional: GeoSphere Austria solar forecast (C-LAEF) – no API key

Enable **GeoSphere Austria Solar Forecast** in **Settings → Devices & Services →
my-weather → Configure**. This uses GeoSphere's public **direct** Data Hub
timeseries API, not Open-Meteo. The setting is off by default for existing
installations. GeoSphere updates **independently every 3 hours**, uses the
integration's configured coordinates and does **not** consume Meteonomiqs
API quota or modify its four selected publication times. The data source is
free and CC BY 4.0, including commercial use with attribution.

- **Dataset:** `nwp-v2-1h-1km`, deterministic C-LAEF AlpeAdria, 1-km grid,
  hourly forecasts covering up to 60 hours, updated by GeoSphere every 3 hours.
- **Native parameters:** `ssrd` (hourly-mean horizontal global solar radiation,
  **W/m²**, *not* cumulative irradiance) and `tcc` (total cloud cover, %).
- **Entities:** `GeoSphere Solar Radiation GHI` (W/m²), `GeoSphere Cloud Forecast
  48h` (mean cloud %), `GeoSphere Solar Irradiation 48h` (remaining kWh/m²),
  and a diagnostic `GeoSphere Model Run` timestamp. Entity IDs vary with HA.
- **Forecast attributes** of both series sensors: `forecast` list with
  `datetime`, `end`, `ghi_w_m2`, `cloud_coverage`, plus actual available-hour
  counts, model run, provider and license. Missing values remain null.
- **Service:** `my_weather.update_solar` forces a GeoSphere-only refresh.
  `my_weather.update` still only calls Meteonomiqs.
- **Caveat:** GHI is horizontal solar radiation, **not PV production** or
  plane-of-array irradiance. Smartify Energy Pro must project it onto each
  configured roof surface, apply losses/calibration and convert to Wh before
  using it for PV planning. A 48h rolling view can be shorter than the
  provider's nominal 60h forecast near the end of the model run.
- **Failure behavior:** failed updates keep valid cached data. Expired forecast
  hours must be treated as unavailable, never as sunny or 0 W/m².
- **Source/attribution:** GeoSphere Austria Data Hub,
  https://data.hub.geosphere.at/dataset/nwp-v2-1h-1km (CC BY 4.0).
  The forecast API is marked prerelease by GeoSphere; monitor upstream changes.

**Operational verification:** offline regression tests do not replace a
live Home Assistant check of first setup/reload, DST transition, GeoSphere API
schema, 3-hour refresh, 429/5xx errors, and sensor availability.

## Features

## Bewölkungsprognose bis 48 Stunden für SEP

My-Weather provides the existing **Meteonomiqs Cloud Forecast 8h** sensor and a new **Meteonomiqs Cloud Forecast 48h** sensor. The new sensor uses the same Meteonomiqs API response (no additional API requests). Its
state is the mean of available cloud percentages (0–100 %) in the current
and next seven hourly slots. The `forecast` attribute is the machine-readable
interface for Smartify Energy Pro (SEP):

```yaml
forecast:
  - datetime: "2026-11-08T10:00:00+00:00"
    end: "2026-11-08T11:00:00+00:00"
    cloud_coverage: 50
```

The legacy 8h sensor still exposes up to eight entries. The 48h sensor exposes **as many hourly slots as the Meteonomiqs response actually contains, up to 48**. Its attributes include `forecast_hours` (available slots), `valid_cloud_hours` (non-null cloud readings) and `max_forecast_hours: 48`. Entries use UTC ISO-8601 timestamps; missing
cloud readings are `null`, never assumed to be 0 %. A stale cache
produces an unavailable value and an empty list, not a misleading forecast.
The series refreshes from the existing cached API response **without any
additional API requests**. It follows the same scheduled/manual publication
rules as all other weather entities.

**Chart:** After installing/restarting My-Weather, add a *Manual* dashboard
card (the integration registers the bundled card resource):

```yaml
type: custom:my-weather-cloud-8h-card
entity: sensor.meteonomiqs_cloud_forecast_8h
title: Bewölkung – nächste 8 Stunden
```

The actual entity ID can differ; select it under Developer Tools → States.
The chart keeps 8h as its default. For a longer chart, configure `entity: sensor.meteonomiqs_cloud_forecast_48h`; the visible **8h / 24h / 48h** controls switch the display and make the longer bar chart horizontally scrollable. `hours: 24` or `hours: 48` can set the initial selection. Only received hours are displayed; missing slots are never invented. The chart uses the Home Assistant theme.
When installing an update, reload the frontend to load the changed card.
Since 0.1.3.6 the card is registered as a Lovelace resource
(`/my_weather/my-weather-cloud-8h-card.js?v=<version>`, storage mode, created
automatically after Home Assistant has started). With Lovelace in YAML mode add
this URL manually under `lovelace: resources:` (type: module).
The `forecast` attribute is **cloud cover, not PV watt-hours**: SEP must use
it alongside a solar irradiation/PV production model. Do not add this sensor
to SEP's existing PV-forecast *energy* sensor list, because that list expects
Wh, not %. For SEP's extended self-calculated PV plan choose the **new 48h sensor** in SEP's cloud entity setting; an existing selection of the 8h sensor is deliberately not changed automatically. Forecast reliability decreases with local fog, mist and rapidly
changing cloud cover.



- Up to **4 API keys** with rotation on HTTP 401/403 (key access denied) and 429 (rate limited). If every key receives 403, check provider entitlements and API key validity. Cached data is preserved.
- API keys are automatically loaded from fixed names in Home Assistant's `/config/secrets.yaml`, with no secret names entered in the integration dialog.
- **Manual update** via the `my_weather.update` service — full control over your API quota
- **Optional scheduled updates**: up to four configurable full hours (HH:00) per day (Home Assistant local timezone)
- **Atomic forecast replacement**: no temporary clearing when API keys rotate or refreshes fail
- **Timestamp-aligned hourly forecast**: no fallback to the wrong hour if cached data expires
- Persistent cache: data survives HA restarts without an extra API call
- Current index recalculated every minute from cached data (no extra call)
- Supports **DE / EN / FR / IT / ES** weather descriptions from the API
- Full `weather` entity + individual sensor entities

---

## API Quota & Key Rotation

The Meteonomiqs free tier gives you **50 calls per API key per month**.

| Keys configured | Monthly calls available |
|:-:|:-:|
| 1 | 50 |
| 2 | 100 |
| 3 | 150 |
| 4 | 200 |

The integration rotates to the next key automatically when the API returns HTTP 429 (rate limit exceeded). The currently active key index is exposed as a diagnostic sensor.

### Recommended Automation

By default, auto-polling is disabled. You can set up to four scheduled fetch times under **Settings → Devices & Services → Meteonomiqs → Configure**, or use an automation as below. An example manual update for one key (50 calls/month):

```yaml
automation:
  - alias: "Meteonomiqs – daily weather update"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: my_weather.update
```

Two keys permit roughly 100 calls per month. Scheduling three daily calls uses about 90–93 requests per month, leaving limited quota for manual calls or retries. Prefer the built-in full-hour schedule instead of duplicating it with automations.

---

## Installation

### Via HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/smartify-your-home/my-weather` as type **Integration**
3. Install **my-weather** and restart Home Assistant

### Manual

1. Copy the `custom_components/my_weather/` folder into your HA `custom_components/` directory
2. Restart Home Assistant

---

## Configuration

Go to **Settings → Devices & Services → Add Integration** and search for **Meteonomiqs**.

| Field | Description |
|---|---|
| API Key 1 | Optional when using automatic secrets.yaml detection. |
| API Key 2–4 | Optional direct keys for legacy/manual setup; not needed with secrets.yaml. |
| Latitude | Location latitude (e.g. `48.2083`) |
| Longitude | Location longitude (e.g. `16.3731`) |
| Language | Language for weather descriptions: DE / EN / FR / IT / ES |

Get your API key at https://www.meteonomiqs.com/weather-api/#heading-price-packages_2

## Fixed API keys from secrets.yaml

The integration **automatically discovers** one to four API keys from Home Assistant's `/config/secrets.yaml`, using these **fixed names**:

```yaml
# /config/secrets.yaml
my_weather_api_1: "YOUR_FIRST_API_KEY"
my_weather_api_2: "YOUR_SECOND_API_KEY" # optional
my_weather_api_3: "YOUR_THIRD_API_KEY"  # optional
my_weather_api_4: "YOUR_FOURTH_API_KEY" # optional
```

**Only one key is required.** Any missing optional slot is skipped, even if the numbering has gaps: `my_weather_api_1` and `my_weather_api_3` work together without entries 2 and 4. The integration loads the available keys in numerical order and rotates between them on HTTP 429. Duplicate key values are used only once.

Do not enter secret names or `!secret` in the integration UI: **no API-key name input is required**. Leave all direct API-key fields empty when using `secrets.yaml`. If no fixed secrets are present, the existing manually entered API keys continue to work for compatibility. An existing but empty or invalid fixed secret entry triggers a configuration error, never a fallback to a different key.

After editing `secrets.yaml`, reload the integration to reread its keys. Do not commit `secrets.yaml` to Git. Older plaintext keys already stored in a config entry are not automatically removed when fixed secrets are used; recreating an existing entry is required if you want to remove those stored values.


## Scheduled updates and hourly rollover

Open **Settings → Devices & Services → Meteonomiqs → Configure** and enter up to four **full-hour publication times** in local 24-hour `HH:00` format (for example `06:00` and `14:00`). Leave all fields empty to disable scheduled fetching.

For each scheduled publication at **14:00**, the integration **fetches at 13:55** and holds the downloaded response without changing any sensor values. At **14:00**, the forecast hour shifts and the complete new forecast is published **in one coordinator update**. The old snapshot remains visible until that moment. This prevents an old-forecast hour shift followed by a second API-revision jump.

If prefetch fails, the regular hourly rollover still occurs using cached data. If the API is slow and responds after the intended hour, the new snapshot is published once it arrives (a second transition is possible in this unusual case). **Manual `my_weather.update` calls always publish immediately** and override any staged response. The usual hourly time-shift continues on hours without scheduled fetching. All times use Home Assistant's configured local timezone.

**Quota warning:** Four updates per day use approximately 120–124 successful requests per month, which exceeds the 50-call allowance of one free API key. Disable any existing update automations if you do not want additional API requests.

If the cached forecast no longer covers the current hour, affected sensors return `unknown` instead of incorrectly resetting to the first (stale) forecast hour. Genuine provider forecast revisions can still change values.

## Entities

### Weather Entity

| Entity | Description |
|---|---|
| `weather.my_weather` | Standard HA weather entity with current conditions and forecast |

### Current Conditions (Sensors)

These reflect the **current hour** from the cached forecast data.

| Entity | Unit | Description |
|---|---|---|
| `sensor.my_weather_current_temperature` | °C | Current temperature |
| `sensor.my_weather_current_humidity` | % | Relative humidity |
| `sensor.my_weather_current_cloud_coverage` | % | Cloud coverage |
| `sensor.my_weather_current_wind_speed` | km/h | Wind speed |
| `sensor.my_weather_current_wind_gusts` | km/h | Wind gusts |
| `sensor.my_weather_current_precipitation` | mm | Precipitation |

### Hourly Forecast (Sensors)

8 sensors covering the **next 0–7 hours** relative to the current hour. State = HA weather condition string.

| Entity | Description |
|---|---|
| `sensor.my_weather_forecast_0h` | Current hour |
| `sensor.my_weather_forecast_1h` | +1 hour |
| … | … |
| `sensor.my_weather_forecast_7h` | +7 hours |

**Attributes per hourly sensor:**

| Attribute | Description |
|---|---|
| `hour_local` | Local time (e.g. `14:00`) |
| `temperature` | Temperature in °C |
| `precipitation` | Precipitation in mm |
| `cloud_coverage` | Cloud coverage in % |
| `wind_speed` | Wind speed in km/h |
| `wind_gust` | Wind gusts in km/h |

### Daily Forecast (Sensors)

7 sensors covering **today + 6 days**. State = HA weather condition string (weighted by severity across all hours of the day).

| Entity | Description |
|---|---|
| `sensor.my_weather_day_0` | Today |
| `sensor.my_weather_day_1` | Tomorrow |
| … | … |
| `sensor.my_weather_day_6` | +6 days |

**Attributes per daily sensor:**

| Attribute | Description |
|---|---|
| `date` | Date (YYYY-MM-DD) |
| `temp_max` | Maximum temperature in °C |
| `temp_min` | Minimum temperature in °C |
| `precipitation` | Total precipitation in mm |
| `cloud_coverage` | Average cloud coverage in % |
| `wind_speed` | Average wind speed in km/h |
| `wind_gust_max` | Maximum wind gusts in km/h |
| `wind_warning` | `true` if significant wind warning for that day |

### Diagnostic Sensors

| Entity | Description |
|---|---|
| `sensor.my_weather_last_api_update` | Timestamp of last successful API call |
| `sensor.my_weather_data_age` | Age of current data in minutes |
| `sensor.my_weather_monthly_api_calls` | Total API calls made this month (across all keys) |
| `sensor.my_weather_api_status` | `OK` / `Warning` (≥80 calls) / `Limit reached` (≥100 calls) |
| `sensor.my_weather_active_api_key` | Index (1–4) of the currently active API key |

---

## Services

| Service | Description |
|---|---|
| `my_weather.update` | Manually trigger a fresh API fetch. Use this in automations to control your quota. |

---

## License

MIT License — see [LICENSE](LICENSE)
