# Architecture

LUMEN uses a local HTTP boundary with a static, build-free frontend and a modular Python backend.

~~~mermaid
flowchart LR
  U[Researcher] --> UI[Local interface]
  UI --> API[Validated local API]
  API --> P[Projects and sessions]
  API --> A[AI tool loop]
  API --> E[Execution service]
  A --> E
  E --> K[Jupyter kernels]
  E --> C[Compile and process adapters]
  API --> R[Pinned SSH and SFTP]
  E --> L[Run records and snapshots]
  P --> DB[(SQLite)]
  L --> DB
  API --> D[Reports and delivery]
~~~

## Responsibilities

- server.py handles loopback HTTP, per-launch request tokens, origin checks and static/file responses.
- app.py validates project/session ownership and dispatches application operations.
- agent.py adapts two model protocols and manages the tool/approval loop.
- execution.py owns local process/kernel lifetimes, execution queues, cancellation and result snapshots.
- runners.py resolves toolchains and returns argument arrays for compile/run phases.
- remote.py pins server identities, opens explicit SSH connections and bounds SFTP access.
- files.py provides resolved-path checks, text/data APIs and file identities.
- store.py owns SQLite transactions and durable records.

The frontend consists of core helpers and feature modules. Dynamic data is escaped before insertion into HTML. No remote CDN scripts are loaded.

## Adding a language

1. Register a stable language ID, filename, tool key and display mode.
2. Implement executable resolution and explicit compile/execute argument arrays.
3. Add a minimal success test, a compile/runtime failure test and cancellation coverage when the behavior differs.
4. Describe whether state persists and how outputs are saved.
5. Never label a missing runtime as verified.

The present adapter mechanism is code-based. User-editable runner manifests and multi-file project builds are roadmap items.

## Execution evidence

Inputs are declarations hashed before submission. Code is recorded exactly. Files changed under outputs/reports during execution are copied to immutable run storage and hashed again. One local run per project executes at a time to reduce cross-run output mixing.

An external editor or untracked process can still change files. These observations do not prove every dependency or complete file attribution. Remote commands record logs and exit status but do not capture remote input/output snapshots.

## Reproduction and delivery

Independent reproduction validates declared input identities, copies them to a new project and runs a new process. It does not reuse the current Python kernel.

Exports include project files according to the user's data choice, plus recorded code/environment and preserved output bytes. Credentials and application databases are never included by the source release builder.

## Protocol documentation

- [Function tools](https://developers.openai.com/api/docs/guides/function-calling)
- [Jupyter Client](https://jupyter-client.readthedocs.io/en/stable/api/jupyter_client.html)
- [Paramiko](https://docs.paramiko.org/en/stable/api/client.html)
