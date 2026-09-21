# September 21, 2026 — Windows Beast cutover (#211)

Production data and processing have moved from Google Cloud to Beast. The local
application works and the cloud hosting resources are retired. **Automatic core
Windows services still require the owner's Windows administrator approval.**
This record must not be read as completed service or reboot acceptance.

## Code and verification

Canonical repository: **1349678672**, `maglothinm/MyETF-Intelligence`.
Implementation [PR #212](https://github.com/maglothinm/MyETF-Intelligence/pull/212)
merged to main **42c6f27df5d9266decad3abc7aa6f794edda0f3a**, the application source
actually checked out on Beast. Evidence branch:
`codex/beast-local-cutover-evidence-20260921`.

Implementation PR head `5ef2daceb74fd9b75d24fa33f9d193376315d8bf` passed:

| Check | Successful GitHub Actions run |
|---|---|
| Runtime v2 safety, including real PostgreSQL | [35615691404](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35615691404) |
| Source upload and OCR | [35615691405](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35615691405) |
| Investor Edge | [35615691416](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35615691416) |
| Current Opportunity | [35615691395](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35615691395) |

Focused implementation tests: 86 passed/30 PostgreSQL variants skipped locally;
native Windows local/Vault/scheduler checks: 150 passed/1 skipped. Native smoke
checks completed two-page OCR, Chromium launch, Windows process cleanup, the
real web factory and enabled Vault API using private file storage. The first
real Windows production cycle independently succeeded for all four jobs.

The follow-up code change creates an inactive, non-superuser `cloudsqlsuperuser`
compatibility role before restoring an empty target. The original Cloud SQL
dump's final schema ACL referenced this role. The first attempt rolled back
fully; its failure log is retained. After the compatibility role was created,
the unchanged, hash-verified export restored transactionally and passed the full
database audit. The helper still refuses any populated destination. CI now
covers changes to every `scripts/local_*.py` helper.

## State continuity and recovery

The five cloud schedules were paused and all cloud jobs drained before the
frozen source export. Public cloud web ingress was restricted before export.
The 26,331,632,841-byte export SHA-256 is:

`7d5128c2f9cb4ea96e41b02f274c519178f8924e63929d204f6c29aca38d39c6`

At 15:43:41 UTC, all **18 table fingerprints**, **4,256 snapshot payload hashes**
and the four manifest-verified source heads passed. Authority moved at
15:44:47 UTC. The 15:44:48–15:47:43 local production cycle advanced each head
exactly once:

| Namespace | Frozen generation | Local generation |
|---|---:|---:|
| Legislative | 1360 | 1361 |
| Executive | 672 | 673 |
| AI | 764 | 765 |
| Dashboard | 1460 | 1461 |

A subsequent read-only audit matched all frozen row fingerprints in the other
17 tables, including the original snapshots and job runs, and checked each new
snapshot's payload, parent and source revision. Accounts, sessions, nine review
acknowledgements, the existing source upload, OCR evidence, all run history and
notification state were preserved. No baseline was reset. Dashboard 1461 has
5,152 filings, 12,737 transactions, 1,538 review items and 308 AI analyses.
The Executive cycle completed 23/23 OCR pages; existing access/retry backlogs
remain visible. No downstream review was automatically approved.

Local root: `C:\ProgramData\PolitiTrack`. The original export remains in
`backups\polititrack-final.sql.gz`. A post-cycle PostgreSQL physical backup,
25,760,825,499 bytes, passed `pg_verifybackup` at 15:50:44 UTC. Its manifest SHA:

`1a80643c24f35ea8471ef24bc1f69091b61bcd170d3989780794dfd2a7ffc4fc`

Restore from the latest verified local backup after cutover, never the old cloud
baseline once local heads have advanced. The installed scheduler will make daily
logical backups and retain the latest two separately from migration evidence.

## Local application and cloud retirement

The dashboard is at `http://127.0.0.1:8765`. PostgreSQL listens on loopback port
54329. Readiness matches Dashboard 1461; root, data and 18 checked asset/data
hashes passed. Unexpected Host requests return 403. The review session API
returned 200. The existing desktop executable keeps its tray/icon/notification
code with five cloud-URL references changed to loopback; `--check-live` passed
and parsed 40 profiles. Its original sign-in startup registry entry is enabled.
The pre-edit executable and installation directory were backed up.

Deleted dedicated Google Cloud resources: the SQL instance, one Cloud Run web
service, nine jobs, five schedules, five secrets, the container repository and
four active storage buckets. Secrets and required build/terraform recovery files
were archived privately on Beast before deletion. The 15:53:35 inventory found
zero active hosting/storage resources and no Compute instance, disk or router;
the SQL backup list is also empty. Two internal network reservations remain.
The three legacy GitHub state workflows remain manually disabled.

Google's API still lists four deleted bucket records with September 28
hard-delete dates, despite a zero-second configured soft-delete policy. Retained
object bytes and final charges were not established. Google does not allow
permanent deletion of soft-deleted resources before their retention period ends;
retained objects can continue accruing storage charges. See
[Google's soft delete documentation](https://docs.cloud.google.com/storage/docs/soft-delete).
Do not restore these buckets or recreate cloud hosting as a workaround.
There is no claim that earlier usage, export/transfer costs or retained storage
will disappear from the final Google bill. Existing external API usage can
still incur its own charges on the local installation.

Vault API stays enabled with guarded private Windows file storage and the same
signing key; its lifecycle scheduler remains paused. Current Opportunity and
manual cloud operations remain off. Internet access remains necessary for
disclosure retrieval and external APIs. Windows sleep preferences are unchanged.

## Remaining owner action

The original Windows UAC request ended with **“The operation was canceled by the
user.”** It was not retried. No PolitiTrack core services are registered and no
recurring local scheduler is currently running. PostgreSQL, web and the desktop
tray are temporarily running under the owner; the tray sign-in entry alone is
not a substitute for the services.

Double-click **Finish PolitiTrack Setup** on Beast's Desktop and approve Windows
administrator elevation. The prepared installer registers automatic
PolitiTrackDatabase, PolitiTrackWeb and PolitiTrackScheduler services under
LocalService, verifies readiness and saves `backups\installed-services.json`.
Check all three live Running states and a natural scheduled cycle afterward.
Reboot/start-before-sign-in behavior has not yet been observed. Keep #211 open
until service activation is verified. Do not re-import or reinitialize data.

Full non-secret [receipts and hashes](2026-09-21-beast-local-cutover.json) are
committed; private configuration and detailed logs remain on Beast.
