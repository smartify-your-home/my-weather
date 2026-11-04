# my-weather 0.1.3.2 – Hotfix

Fix unloading and reloading the Meteonomiqs Home Assistant integration.

### Fixed
- Removed an incorrect call to `ConfigEntry.async_unload()` inside the integration's `async_unload_entry` function.
- Home Assistant itself manages the config-entry lifecycle; integrations unload their entity platforms, cancel scheduled callbacks and stop timers.
- Added a regression test to prevent the incorrect nested unload call from returning.

### Installation
Update via HACS to 0.1.3.2, restart Home Assistant after code installation, then test **Reload** for the Meteonomiqs integration.

### Previous changes (0.1.3.1)
All improvements from 0.1.3.1 remain: automatic 1–4 fixed API keys from `secrets.yaml`, scheduled weather prefetch/publish, translations and docs.

### Testing
CI syntax/unit tests are required. An end-to-end test with the user's Home Assistant instance has not been performed.
