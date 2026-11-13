# my-weather v0.1.3.7 – GeoSphere Austria C-LAEF solar forecast

Optional direct GeoSphere Austria C-LAEF forecast without API key, using a separate periodic coordinator and cache. Existing Meteonomiqs sensors, quota and schedules stay unchanged. Enable in the integration's options after upgrading. Hourly `ssrd` radiation is W/m², not PV watts; SEP needs a separate irradiance-to-PV model before selecting it. Attribution GeoSphere Austria CC BY 4.0.

New HA sensors: GeoSphere Solar Radiation GHI, GeoSphere Cloud Forecast 60h, GeoSphere Solar Irradiation 60h, GeoSphere Model Run. Manual refresh: `my_weather.update_solar`. The direct GeoSphere forecast interface is still considered prerelease by its provider.

**Verification:** offline parser and sensor tests plus the GitHub validation workflow, including the 60h sensor state/attribute bridge and separate three-hour polling. The provider endpoint is documented by GeoSphere, but a live API response and deployment in a running Home Assistant installation have not been verified in this release process. Verify the 60h sensor's `forecast` attribute after enabling, and report API errors. The underlying GeoSphere forecast API is considered prerelease by its provider.

---

# my-weather 0.1.3.6 – cloud chart "Configuration error" fix

The bundled cloud chart (`custom:my-weather-cloud-8h-card`) could permanently show **Configuration error** (`Custom element doesn't exist`) until the page was reloaded. It was loaded only through the page head and could run before Home Assistant's custom-element polyfill.

- The card is now registered as a Lovelace resource (`/my_weather/my-weather-cloud-8h-card.js?v=<version>`), created and updated automatically in storage mode.
- Lovelace YAML mode: the previous frontend loading remains as fallback; the log names the URL for a manual `lovelace: resources:` entry (type: module).
- No change to sensors, API requests, scheduling or key handling.

After updating: restart Home Assistant and reload the dashboard/app once.

**Verification:** offline unit tests cover resource creation, update, de-duplication, retry and the YAML fallback. The change was not tested in a running Home Assistant installation.
