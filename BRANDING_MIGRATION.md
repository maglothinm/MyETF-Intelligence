# PolitiTrack branding and compatibility record

## Product rebrand complete; repository-settings cutover pending

PolitiTrack is the product name and approved final repository name. The
authoritative repository is ID `1349678672`, currently named
`maglothinm/MyETF-Intelligence` and awaiting an authenticated in-place rename to
`maglothinm/PolitiTrack`; `MyETF` and `MyETF-Intelligence` remain aliases.

User-visible application text, alert titles, analyst instructions, logger identity,
and HTTP client identifiers use PolitiTrack. Runtime-generated repository and
Pages links follow `GITHUB_REPOSITORY`, so they use the current name and will move
with the rename. Public `maglothinm/MyETF` is code-frozen and is not an execution
target, but its Pages-disable and archive settings remain pending.

## Compatibility identifiers intentionally preserved

The product rebrand and pending repository rename do not reset or rename durable
state. These established identities remain unchanged:

- `.trade-tracker/legislative/`, `.trade-tracker/executive/`, and `.trade-tracker/ai/`;
- `legislative-tracker-state`, `executive-tracker-state`, and `ai-analysis-state`;
- cache keys, state versions, completed analysis IDs, trade IDs, filing IDs, and paper-portfolio ledgers;
- existing `MYETF_*` environment-variable names that are still consumed by compatibility or recovery tooling;
- installer boundary comments such as `MYETF-GOVERNMENT-TRADE-TRACKER` where changing them would break idempotent historical overlays;
- legacy distribution and provenance filenames, including `MyETF-government-trade-tracker-fast-track.zip` and `myetf-investor-edge-implementation.zip`;
- historical recovery reports and commit messages that accurately record the repository name at the time.

A preserved compatibility string is not permission to target the legacy public
repository. Runtime-generated links must follow the canonical repository identity;
hard-coded fallbacks use the approved `maglothinm/PolitiTrack` target.

## State-preserving rule

Repository and branding changes are metadata changes, not baseline changes. Production runs must restore existing artifacts. `initialize_state` and `bootstrap_alerts` remain `false` during routine operation and cutover verification. Missing state is a recovery incident.

Simulation state is isolated and may use only simulation-named artifacts. It must never replace a production tracker or AI artifact.

## Historical alias map

| Name | Meaning after cutover |
|---|---|
| `PolitiTrack` | Current product and approved final name of repository ID `1349678672`. |
| `MyETF-Intelligence` | Current pre-rename GitHub name of the same canonical repository. |
| `MyETF` | Code-frozen public legacy fork; settings archive remains pending. |
