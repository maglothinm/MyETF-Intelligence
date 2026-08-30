# PolitiTrack branding and compatibility record

## Completed identity cutover

PolitiTrack is the product and repository name. The authoritative repository is `maglothinm/PolitiTrack`; `MyETF` and `MyETF-Intelligence` are historical aliases only.

User-visible application text, dashboard links, alert titles, analyst instructions, fallback repository URLs, logger identity, and HTTP client identifiers use PolitiTrack. The public `maglothinm/MyETF` repository is a disabled, archived legacy record and is not an execution target.

## Compatibility identifiers intentionally preserved

The repository rename did not reset or rename durable state. These established identities remain unchanged:

- `.trade-tracker/legislative/`, `.trade-tracker/executive/`, and `.trade-tracker/ai/`;
- `legislative-tracker-state`, `executive-tracker-state`, and `ai-analysis-state`;
- cache keys, state versions, completed analysis IDs, trade IDs, filing IDs, and paper-portfolio ledgers;
- existing `MYETF_*` environment-variable names that are still consumed by compatibility or recovery tooling;
- installer boundary comments such as `MYETF-GOVERNMENT-TRADE-TRACKER` where changing them would break idempotent historical overlays;
- legacy distribution and provenance filenames, including `MyETF-government-trade-tracker-fast-track.zip` and `myetf-investor-edge-implementation.zip`;
- historical recovery reports and commit messages that accurately record the repository name at the time.

A preserved compatibility string is not permission to target the archived public repository. Runtime repository fallbacks and generated links must resolve to `maglothinm/PolitiTrack`.

## State-preserving rule

Repository and branding changes are metadata changes, not baseline changes. Production runs must restore existing artifacts. `initialize_state` and `bootstrap_alerts` remain `false` during routine operation and cutover verification. Missing state is a recovery incident.

Simulation state is isolated and may use only simulation-named artifacts. It must never replace a production tracker or AI artifact.

## Historical alias map

| Name | Meaning after cutover |
|---|---|
| `PolitiTrack` | Current product and sole canonical repository. |
| `MyETF-Intelligence` | Previous name of the same private repository. |
| `MyETF` | Archived public legacy fork and rollback record. |

