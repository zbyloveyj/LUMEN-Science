# Verification record

Date: 2026-11-08. Version: 0.1.0 early preview.

## Actual local results

Windows local synthetic suite: **19 top-level tests passed**, 0 failures and 0 skipped, final full run 161.100 seconds. Several tests contain additional language or workflow subcases.

This is the original local suite record. After the hosted Windows compatibility findings, a twentieth regression was added and checked locally: compiling from an ASCII staging directory still writes relative outputs in the unchanged Unicode project directory. Local R/Shell and Java checks were also repeated after the fix.

## Hosted verification

[GitHub Actions run 42445475251](https://github.com/zbyloveyj/LUMEN-Science/actions/runs/42445475251) completed successfully on 2026-11-08 for code commit c723e1908602531f6e3153974911e385051edd4f:

- Windows: 20 tests, 55.185 seconds, successful.
- Linux: 20 tests, 17.791 seconds, successful overall; the R subcase skipped because the toolchain was not configured.

The initial hosted Windows attempt exposed compiler argument encoding and R temporary-directory space restrictions. The fix stages affected single-file compiler/R inputs in a per-run compatible temporary directory without renaming the project or changing its working directory. The regression covers actual relative output creation, rather than changing the test project to an ASCII-only name.

Hosted execution uses test model/SSH fixtures and synthetic data; it is not real-service or complete desktop acceptance.

Verified language execution:

| Language | Scope |
|---|---|
| Python | Persistent variables across cells, runtime error recovery, active/queued cancellation |
| R | Existing R 4.3.2, independent Rscript execution |
| C | Actual compilation and execution through Zig C driver |
| C++ | Actual compilation and execution through Zig C++ driver |
| Java | Actual JDK 24 compilation and execution |
| JavaScript | Actual Node.js 24 execution |
| TypeScript | Actual Node.js type-stripping execution |
| PowerShell | Independent process |
| Bash | Installed Git Bash, independent process |
| SQL | SQLite execution and CSV query result |

Go/Rust adapters are implemented but were not run because those toolchains were not installed. R continuous IRkernel operation was not tested; the local R test used Rscript.

Other local coverage:

- Project/session ownership and path traversal rejection.
- Synthetic table checks, missingness and import without overwriting.
- Four complete analysis templates, output identities and exact snapshot bytes.
- New-project independent reproduction.
- Retained-version and table-value comparison.
- Export excludes application credentials and optionally input data.
- Local HTTP token/Origin checks and required static resources.
- Chat Completions and Responses protocol fixtures.
- Actual tool dispatch with an execution approval gate.
- Sequential workflow stops at the first failing step.
- Credential values are not returned by settings responses.
- Notebook export.
- SSH key probing, password authentication and SFTP directory access.
- SSH command output and exit status.
- SFTP upload/download, no-overwrite and traversal rejection.
- Changed SSH host key rejection.

SSH tests used an in-process local protocol fixture with synthetic credentials and files. They did not connect to a real laboratory server or validate a remote Linux environment.

## External metadata checks

Crossref and PubMed were each queried using the public phrase “gut brain axis”, two records per source. Both returned actual metadata/identifiers. No local study data or credentials were sent. This check does not verify completeness, relevance or paper conclusions.

No paid/credentialed live AI provider was invoked. Model integration tests used a local deterministic HTTP fixture; provider-specific compatibility and billing remain unverified.

## UI check

The local browser displayed the project overview and twelve-language Notebook controls. A Python cell was run through the interface and its actual 120-row synthetic data preview was observed.

Further browser automation stopped because the UI tool could not reliably determine the current browser URL. No screenshot was saved and no complete visual or responsive acceptance is claimed. Backend verification was completed separately.

## Remaining boundaries

- No macOS/Linux desktop real-machine acceptance; Windows/Linux hosted CI scope is recorded above.
- No real-user SSH credential/server acceptance.
- No complete external provider/model compatibility matrix.
- No signed standalone installer or clean-machine package acceptance.
- No full OS sandbox, complete dynamic dependency capture or automatic scientific validation.

Runtime logs are local-only and excluded from source publication because they can contain machine paths and diagnostic context.
