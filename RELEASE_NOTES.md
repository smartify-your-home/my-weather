# my-weather 0.1.3.6 – cloud chart "Configuration error" fix

The bundled cloud chart (`custom:my-weather-cloud-8h-card`) could permanently show **Configuration error** (`Custom element doesn't exist`) until the page was reloaded. It was loaded only through the page head and could run before Home Assistant's custom-element polyfill.

- The card is now registered as a Lovelace resource (`/my_weather/my-weather-cloud-8h-card.js?v=<version>`), created and updated automatically in storage mode.
- Lovelace YAML mode: the previous frontend loading remains as fallback; the log names the URL for a manual `lovelace: resources:` entry (type: module).
- No change to sensors, API requests, scheduling or key handling.

After updating: restart Home Assistant and reload the dashboard/app once.

**Verification:** offline unit tests cover resource creation, update, de-duplication, retry and the YAML fallback. The change was not tested in a running Home Assistant installation.
