# Contributing

Thanks for helping improve LUMEN Science.

## Development setup

Use Python 3.11+ in an isolated environment and install requirements.txt. Optional format support is listed in requirements-data.txt. Language toolchains are installed separately.

Run python run.py and open the loopback URL printed by the process. For headless backend development use python run.py --no-browser --data-dir test-results/dev-state.

Do not use a production research project as a test fixture. The application generates a synthetic sample project automatically.

## Changes

1. Describe the concrete behavior and why the change is needed.
2. Keep language adapters, model adapters, file access and UI responsibilities separate.
3. Add meaningful tests for changed execution, cancellation, isolation, credentials or provenance behavior.
4. Run relevant tests and check the real UI for visible changes.
5. Document limitations and distinguish local fixtures from real-service verification.
6. Avoid automatic installs, destructive file operations and silent retries of write actions.

Language adapters live in lumen/runners.py. Add executable detection, explicit compilation/execution argument arrays and environment status; do not compose local shell command strings.

All frontend text derived from user/model/file content must be escaped. Never render untrusted raw HTML.

## Test command

python -m unittest discover -s tests -v

The full suite starts local Jupyter, HTTP and SSH services and may compile sample programs. Missing optional language environments should be reported explicitly.

## Reporting issues

Include OS, application version, exact steps, expected/actual behavior and a minimal synthetic example. Redact credentials, host addresses, usernames, personal paths and private data.

Contributions are licensed under the project's MIT license. Do not contribute third-party code without compatible permission and attribution.
