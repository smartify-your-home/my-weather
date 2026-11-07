# my-weather 0.1.3.3 – HTTP 403 access-denied hotfix

Meteonomiqs may return HTTP 403 when a key lacks permission for the requested forecast endpoint. Previously the integration rotated only on 429, so a rejected first key prevented other configured keys from being tried.

- Try each available secret key once on HTTP 401, 403 or 429.
- Preserve existing forecast cache and publish no failed API responses.
- Log slot numbers and HTTP codes, never secret values.
- If **all** configured keys are denied, the problem must be resolved at the API provider or by correcting the keys; a code change cannot authorize a forbidden endpoint.
- Keep the 0.1.3.2 unload hotfix and all earlier behavior.

**Verification:** automated tests verify Python syntax and configuration structure. The live provider's authorization response cannot be reproduced without account credentials.
