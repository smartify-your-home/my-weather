# Security policy

Do not open public issues containing API keys, tokens, complete secrets.yaml,
Home Assistant credentials or other private configuration.

For a security concern, use GitHub's private vulnerability reporting feature
when available for this repository, or contact the repository owner privately.
Avoid public disclosure until the issue can be investigated.

The integration reads only the four fixed `my_weather_api_1` to
`my_weather_api_4` entries from the local Home Assistant secrets.yaml.
Never commit the file or expose key values in logs or diagnostics.
