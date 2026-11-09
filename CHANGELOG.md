# Changelog

## 0.2.1 — 2026-11-09

- Check that the local workbench responds before opening its window. Local startup checks and the embedded workbench connect directly to loopback.
- Report desktop loading failures, record WebView2 errors in `desktop-startup.log`, and offer to open the running workbench in the default browser.
- Add a browser mode shortcut to the Windows Start menu and treat the WebView2 `0.0.0.0` registry value as missing.

## 0.2.0 — 2026-11-08

- Windows native desktop window using WebView2, with an application icon and download support.
- Light desktop design with a translucent sidebar, blue selection, quieter cards and improved small-text legibility.
- Bundled Python runtime with dedicated kernel/script workers; externally configured Python remains supported.
- Per-user data storage independent of the installation folder; uninstall preserves project data and unknown files.
- Windows x64 installer, portable ZIP, dependency license inventory and SHA-256 checksums.
- Release workflow verifies source, packaged execution, installer and uninstaller before publishing a prerelease.
- macOS/Linux remain source distributions; native installers and application auto-update are not implemented.

## 0.1.0 — 2026-11-08

Initial local preview.

- Local project/session management and synthetic demonstration.
- Twelve language adapters, Python persistent kernels and explicit compiler/process phases.
- AI Chat Completions/Responses adapters with read-only and execution-review modes.
- Four self-contained analysis templates and sequential custom workflows.
- Data exploration, literature metadata and BibTeX export.
- Provenance records, exact output snapshots, retained versions and independent reruns.
- Markdown, notebook and project delivery exports.
- Pinned-host-key SSH, remote command logs and SFTP transfers.
- Local automated verification, contribution/security documents and release preparation.
- Windows Unicode project compatibility: isolated compiler/R staging, compatible temp paths, unchanged project working directory.

Known limitations and acceptance gates are listed in ROADMAP.md and docs/VERIFICATION.md.
