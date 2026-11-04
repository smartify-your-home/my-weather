# Contributing

Read [AGENTS.md](AGENTS.md) first. Open a pull request for each behavior change.
Keep secret values and Home Assistant's secrets.yaml out of commits.

Minimum checks:
```bash
python -m compileall -q custom_components/my_weather
python -m unittest discover -s tests -p 'test_*.py'
```
Validate JSON in strings.json, all translations and manifest.json. Integration
changes should also be tested in a running Home Assistant installation, paying
attention to DST, reloads, API failures, schedule boundaries and quota usage.

When changing behavior, update README, CHANGELOG, localization strings and
service descriptions. Do not merge merely because compile checks pass.
