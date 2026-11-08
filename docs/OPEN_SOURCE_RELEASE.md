# Open-source release preparation

## Repository

Public repository: https://github.com/zbyloveyj/LUMEN-Science

The initial public repository was created by the project owner. Publish updates only to this intended repository, preserving its existing history.

The release source excludes .state, .vendor, .venv, test-results, logs, compiler caches, generated research projects, credentials and private keys.

## Build the source archive

~~~console
python scripts/build_release.py
~~~

The explicit source allowlist is audited for common credential markers and private absolute Windows user paths. The archive includes a file hash manifest; a separate SHA-256 file identifies the ZIP bytes. This bounded check is not a comprehensive security audit.

## First publication

1. Verify the final local tests and docs/VERIFICATION.md.
2. Review the allowed source file list and the resulting archive.
3. Upload only the source tree and documentation to the intended public repository.
4. Observe actual GitHub Actions results before adding a passing-CI badge or claiming hosted CI passed.
5. Update docs/LAUNCH_COPY.md with the real repository URL.
6. Capture actual screenshots/recordings; do not label the brand banner as a screenshot.
7. Share the early-preview description, installation conditions and limitations together.

The initial Git tag or public release should be created only after repository checks are known. A prepared source archive is not an uploaded GitHub release.
