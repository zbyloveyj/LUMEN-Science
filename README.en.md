# LUMEN Science

A local-first, multilingual AI research workbench.

LUMEN connects project files, AI tool calls, computation, literature metadata, result snapshots, and research delivery. Version 0.1.0 is an early preview, not a validated replacement for every existing workbench.

Repository: [zbyloveyj/LUMEN-Science](https://github.com/zbyloveyj/LUMEN-Science).

## Start

Use Python 3.11+ in a dedicated environment:

~~~console
git clone https://github.com/zbyloveyj/LUMEN-Science.git
cd LUMEN-Science
python -m venv .venv
~~~

Install requirements using that environment's Python, then run:

~~~console
python -m pip install -r requirements.txt
python run.py
~~~

The application binds to loopback and opens a browser window. The first project contains 120 explicitly synthetic records; no existing research folder is scanned automatically.

## Features

- Project-scoped sessions and local files.
- Chat Completions / Responses-compatible model adapters, with a read-only discussion mode and execution review.
- Adapters for Python, R, C, C++, Java, JavaScript, TypeScript, Go, Rust, PowerShell, Bash and SQLite SQL.
- Persistent Python kernels; optional IRkernel; separate processes for compiled and other languages.
- Pinned-host-key SSH, remote command logs, and bounded SFTP transfers.
- CSV/TSV/Excel/Parquet exploration, with optional format dependencies.
- Four self-contained analysis templates and sequential custom workflows.
- Crossref/PubMed metadata, saved references and BibTeX export.
- Input hashes, executed code, environment records, result snapshots and retained versions.
- Independent reruns in a new project/process, Markdown reports, notebook and ZIP exports.

Each language needs a corresponding toolchain. TypeScript uses Node's type stripping rather than a full tsc build. Java uses a Main entry class. SSH commands currently target Linux/Unix shells.

## Boundaries

Code runs with the current user's privileges, without an OS sandbox. Online model calls transmit messages and tool results to the configured provider. Windows credentials use DPAPI; other platforms keep them in process memory only.

Declared inputs do not prove actual consumption or capture all dynamic dependencies. Independent execution does not itself establish numerical equality, scientific validity or complete reproducibility. Full cross-platform acceptance, remote persistent notebooks, multi-user access and automatic environment reconstruction are not implemented.

## Development

~~~console
python -m unittest discover -s tests -v
~~~

Tests use synthetic projects, local model fixtures and a local SSH/SFTP protocol fixture. Current verification scope is documented in [docs/VERIFICATION.md](docs/VERIFICATION.md); a checked-in CI workflow is not evidence that hosted CI has passed.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [ROADMAP.md](ROADMAP.md).

MIT licensed. Third-party dependencies retain their own licenses.
