# Roadmap

Status: desktop preview, 0.2.0.

## Implemented

- Local projects, sessions and file APIs.
- Windows native window, bundled Python workers, installer/portable packaging and gated release workflow.
- Light interface with translucent navigation, blue selection and consistent desktop controls.
- Twelve language adapters, with detected/configured toolchain status.
- Python persistent kernel and optional R environment support.
- Two model protocol adapters, tool loop and execution review.
- Four analysis templates and sequential custom workflows.
- Crossref/PubMed metadata and BibTeX export.
- Input identity, result snapshots, retained versions and independent reruns.
- Markdown reports, notebook exports and project delivery archives.
- Pinned-host-key SSH, bounded command logs and SFTP file transfer.
- Local synthetic verification and a hosted-CI configuration.
- Windows/Linux hosted CI passed; Linux R subcase was explicitly skipped because its toolchain was not installed.

## Next acceptance gates

- macOS/Linux real-machine acceptance, including cancellation and credential behavior.
- External model/provider compatibility matrix with user-configured test credentials.
- Real remote Linux acceptance with disposable user-provided infrastructure.
- Broader clean-machine installation and cross-version upgrade acceptance.

## Planned; not implemented

- Persistent remote notebooks and reconnectable remote jobs.
- Interactive terminals, SSH tunnels and cluster scheduler adapters.
- Environment lock files and reproducible environment reconstruction.
- Multi-file build systems, Rust Cargo/Java Maven/Gradle integration.
- Configurable language plugin manifests.
- Larger and resumable transfers.
- Complete dependency graphs and numerical comparison policies.
- Domain-reviewed scientific workflow plugins.
- Multi-agent collaboration with explicit ownership and artifact verification.

Priorities should follow reproducible user problems rather than feature counts.
