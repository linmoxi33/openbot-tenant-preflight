# openbot-tenant-preflight

Catch a broken OpenBot tenant package — including a coworker still sitting in `catalog/` — before a restart turns it into a server that refuses to boot.

`Upstream: https://github.com/CopilotKit/OpenBot`

## Why now

OpenBot ships ten ready-made coworkers as single YAML files in `examples/fintech/catalog/`. That directory is a staging area the loader never reads: the upstream docs say it plainly — *"Ten more are in `catalog/`, which is not read. Copy one into `agents/` to add it"* ([docs/configuration.md, line 1159](https://github.com/CopilotKit/OpenBot/blob/main/docs/configuration.md#L1159)). The catalog README repeats it: *"Nothing in this directory is loaded."* ([catalog/README.md](https://github.com/CopilotKit/OpenBot/blob/main/examples/fintech/catalog/README.md#L3)).

The loader validates a package once, at startup, and refuses the **whole deployment** on the first bad row. A copied file that names a skill the package does not ship throws `agent "X" names skill "Y", which this package does not ship` ([server/src/tenant-package.ts, line 570](https://github.com/CopilotKit/OpenBot/blob/main/server/src/tenant-package.ts#L570)); a duplicate id, a reserved id, a channel pointing at a missing agent and a bad `model.provider` all stop the server the same way. Because `catalog/` is inert, none of those mistakes are visible until after a human copies the file in and restarts — and then the error arrives as one line in a boot log, with no way to check the rest of the package offline.

Open issue [#398, "A coworker can arrive as an endpoint, but not as a file"](https://github.com/CopilotKit/OpenBot/issues/398) records the same intake gap (open, no reactions — cited as corroboration, not as the primary evidence).

## What it does / does not do

It reads a tenant package directory and applies the loader's own refusal rules, offline:

- `check` — `agents.yaml`, every file in `agents/`, `channels.yaml`, `model.yaml`, `knowledge.yaml`, `brand.yaml`, `skills.yaml`
- `catalog` — every file in `catalog/`, which the loader never reads, validated against the same rules **before** you copy it in; also reports which catalog entries are already installed

Rules mirrored from `server/src/tenant-package.ts`: agent type enum, non-empty `id`/`name`/`role_description`, `title` ≤ 120 chars, `system_prompt` required for `built-in`, blank `endpoint` on a remote agent dropped as a warning (not an error), reserved ids (`policy`, `fleet`, `policy-dry-run`), `person-<32 hex>` ids, duplicate ids across `agents.yaml` and `agents/*.yaml`, duplicate/unknown skill slugs, skill slug regex, `serverId/toolName` tool refs, duplicate channel ids, channels referencing unknown agents, `model.provider` enum, knowledge source types, `brand.tenant` fields.

It does **not** start OpenBot, talk to a database, call the API, or rewrite your files. It does not validate the parts of the package it does not understand, and it is a mirror of the loader rules as of the commit linked above — not an oracle.

## Install / usage

Python 3.9+ and PyYAML (preinstalled as `python3-yaml` on Ubuntu; no network needed):

```sh
python3 -m unittest discover -s tests          # 17 tests, offline
./bin/openbot-tenant-preflight check examples/in/fintech
./bin/openbot-tenant-preflight catalog examples/in/fintech
```

Exit codes: `0` clean, `1` findings, `2` usage or input error.

Text output:

```
WARNING agent-omitted              agents.yaml agents[1].endpoint: agent "risk-analyst" has no endpoint and is dropped by the loader (not an error)
check: 0 error(s), 1 warning(s) in .../examples/in/fintech
```

`--json` output (one object on stdout, parseable by `json.load`):

```json
{
  "tool": "openbot-tenant-preflight",
  "version": "0.1.0",
  "command": "catalog",
  "package": ".../examples/in/fintech",
  "ok": true,
  "summary": {"errors": 0, "warnings": 1, "catalog_files": 2, "installed": 3, "staged": 1},
  "findings": [
    {"severity": "warning", "code": "catalog-already-installed", "file": "catalog/expense-review.yaml",
     "path": "id", "message": "agent \"expense-review\" is already installed in this package"}
  ]
}
```

Full samples: [`examples/out/check-clean.json`](examples/out/check-clean.json), [`examples/out/check-broken.json`](examples/out/check-broken.json), [`examples/out/catalog-clean.json`](examples/out/catalog-clean.json). The broken fixture reports 7 errors with exit code 1.

## 与同类项目的差异

No existing tool was found that covers this (`gh search repos "openbot tenant package"`, `"agents.yaml validator"`, `"tenant package preflight"` all returned zero results; `gh search code "catalog is not read"` returned unrelated repositories). Generic YAML linters such as yamllint check syntax only — they cannot know that `policy` is a reserved agent id, that a slug must match `skills.yaml`, or that an id is declared in two files.

## Limits

- Rules are transcribed by hand from `server/src/tenant-package.ts`; upstream can change them and this tool will lag until updated.
- Only the agent/skill/channel/model/knowledge/brand fields listed above are checked. Theme CSS, plugin grants and anything resolved at runtime are out of scope.
- `catalog` mode assumes each catalog file holds one coworker (or a list under `agents:`), matching the shipped files.
- Warnings do not affect the exit code; only errors do.

MIT licensed.
