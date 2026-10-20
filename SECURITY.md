# Security

## API keys

- API keys are entered in the Home Assistant UI (masked) and stored by Home Assistant in its
  own config entry storage (`.storage/core.config_entries`). They are **never** part of this
  repository.
- Keys are only sent to the Meteonomiqs API as the `x-api-key` request header.
- The integration does not write API keys to the log.

Please **never** post your API keys, your `.storage` folder or full Home Assistant logs in
issues. Remove keys before sharing anything.

## Reporting a vulnerability

Please do not open a public issue for security problems. Use the repository's
**Security → Report a vulnerability** form on GitHub instead.
