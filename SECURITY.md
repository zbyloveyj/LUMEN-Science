# Security and research-data boundaries

This is a local, single-user early preview.

## Important properties

- HTTP binds to loopback only. API calls require a per-launch token, with Host and Origin checks.
- Project file APIs validate resolved paths. Raw data cannot be overwritten through the text-save API.
- Windows secrets use DPAPI; other platforms retain secrets in memory only.
- SSH connections pin an explicitly confirmed host key. Changed keys are rejected.
- Remote uploads use exclusive creation; downloads are bounded and go to a new project output directory.
- Export excludes application settings, credentials, private keys, hidden application state and compiler caches.

## Non-goals and known limits

- Executed code has the current user's operating-system permissions. Path checks on file tools do not constrain arbitrary code.
- The application is not an authenticated multi-user or internet-facing service. Do not expose it with a public reverse proxy.
- Stopping an SSH channel does not prove the remote process stopped.
- Tool traces and metadata are not a complete capture of dynamic I/O, network dependencies or kernel memory.
- Online model providers receive messages and tool results sent to them. Configure services appropriate for your data policy.
- No automated security audit, penetration test or full supply-chain assurance is claimed.

Do not publish real credentials or sensitive research examples in public Issues. Until the repository has a configured private disclosure channel, report the issue without exploit details or sensitive data and request a private contact route.
