#!/usr/bin/env bash
# Incident-specific, sourceable helpers for retrying failed Phase 5 run
# 33979778020.  The retained smoke executions from that run are evidence of the
# interrupted attempt only; no helper in this file can promote them to a Phase 5
# certificate.

: "${PHASE5_RETRY_DESCRIPTOR:=deploy/runtime-v2/phase5-retry-evidence-33979778020.json}"
: "${EVIDENCE_DIR:?EVIDENCE_DIR is required}"
: "${CONTROL_REVISION:?CONTROL_REVISION is required}"
: "${PRIVATE_WEB_AUDIENCE:?PRIVATE_WEB_AUDIENCE is required}"

PHASE5_RETRY_INCIDENT_DIR="${EVIDENCE_DIR}/incident"
PHASE5_RETRY_RUN_ID="33979778020"
PHASE5_RETRY_FAILED_RETRY_RUN_ID="33990741282"
PHASE5_RETRY_PHASE4_RUN_ID="33979432233"
PHASE5_RETRY_LEGACY_AI_RUN_ID="33980946687"
PHASE5_RETRY_DASHBOARD_RUN_ID="33974683885"
PHASE5_RETRY_RECOVERY_RUN_IDS=(33981311523 33981312757)
PHASE5_RETRY_FROZEN_SUCCESSOR_RUN_IDS=(
  33987160591 33987130349
  33992770754 33992772006
)
PHASE5_RETRY_SCHEDULER_CONTROL_ROLE="roles/cloudscheduler.admin"
PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID="polititrackPhase3Terraform"
PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT="${RESOURCE_DIR}/permanent-control-role.json"
PHASE5_RETRY_ROLE_VIEWER_ROLE="roles/iam.roleViewer"
PHASE5_RETRY_ROLE_VIEWER_POLICY="${RESOURCE_DIR}/role-viewer-policy.json"
PHASE5_RETRY_ROLE_VIEWER_BEFORE_POLICY="${RESOURCE_DIR}/role-viewer-before-policy.json"
PHASE5_RETRY_ROLE_VIEWER_GRANTED_POLICY="${RESOURCE_DIR}/role-viewer-granted-policy.json"
PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY="${RESOURCE_DIR}/role-viewer-removed-policy.json"
PHASE5_RETRY_ROLE_VIEWER_CONDITION="${RESOURCE_DIR}/role-viewer-condition.json"
PHASE5_RETRY_ROLE_VIEWER_GRANT="${RESOURCE_DIR}/role-viewer-grant.json"
PHASE5_RETRY_SCHEDULER_CONTROL_POLICY="${RESOURCE_DIR}/scheduler-control-policy.json"
PHASE5_RETRY_SCHEDULER_CONTROL_BEFORE_POLICY="${RESOURCE_DIR}/scheduler-control-before-policy.json"
PHASE5_RETRY_SCHEDULER_CONTROL_GRANTED_POLICY="${RESOURCE_DIR}/scheduler-control-granted-policy.json"
PHASE5_RETRY_SCHEDULER_CONTROL_REMOVED_POLICY="${RESOURCE_DIR}/scheduler-control-removed-policy.json"
PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION="${RESOURCE_DIR}/scheduler-control-condition.json"
PHASE5_RETRY_SCHEDULER_CONTROL_GRANT="${RESOURCE_DIR}/scheduler-control-grant.json"
PHASE5_RETRY_SCHEDULER_CONTROL_SUMMARY="${RESOURCE_DIR}/scheduler-activation-authority.json"
PHASE5_RETRY_SCHEDULER_TRANSITION="${RESOURCE_DIR}/scheduler-transition.json"
PHASE5_RETRY_SCHEDULER_ATTEMPTS="${RESOURCE_DIR}/scheduler-resume-attempts.ndjson"
PHASE5_RETRY_ALL_SCHEDULERS=(
  polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard
  polititrack-vault-lifecycle
)

phase5_retry_descriptor_value() {
  local expression="$1"
  jq -er "${expression}" "${PHASE5_RETRY_DESCRIPTOR}"
}

phase5_retry_verify_descriptor_identity() {
  [[ -f "${PHASE5_RETRY_DESCRIPTOR}" ]] || {
    echo "Phase 5 retry descriptor is missing: ${PHASE5_RETRY_DESCRIPTOR}." >&2
    return 1
  }
  jq -e \
    --arg phase4_run "${PHASE5_RETRY_PHASE4_RUN_ID}" \
    --arg failed_run "${PHASE5_RETRY_RUN_ID}" \
    --arg failed_retry_run "${PHASE5_RETRY_FAILED_RETRY_RUN_ID}" \
    --arg legacy_ai_run "${PHASE5_RETRY_LEGACY_AI_RUN_ID}" \
    --arg recovery_legislative "${PHASE5_RETRY_RECOVERY_RUN_IDS[0]}" \
    --arg recovery_executive "${PHASE5_RETRY_RECOVERY_RUN_IDS[1]}" \
    --argjson successor_legislative "${PHASE5_RETRY_FROZEN_SUCCESSOR_RUN_IDS[0]}" \
    --argjson successor_executive "${PHASE5_RETRY_FROZEN_SUCCESSOR_RUN_IDS[1]}" \
    --argjson successor2_legislative "${PHASE5_RETRY_FROZEN_SUCCESSOR_RUN_IDS[2]}" \
    --argjson successor2_executive "${PHASE5_RETRY_FROZEN_SUCCESSOR_RUN_IDS[3]}" \
    --arg dashboard_run "${PHASE5_RETRY_DASHBOARD_RUN_ID}" \
    'type == "object" and .schema_version == 1 and
     .result == "phase5_failed_promotion_reconciliation_authorized" and
     .repository_id == 1349678672 and
     .repository == "maglothinm/MyETF-Intelligence" and
     (.certified_control_revision | test("^[0-9a-f]{40}$")) and
     (.certified_tree_sha | test("^[0-9a-f]{40}$")) and
     (.runtime_source_revision | test("^[0-9a-f]{40}$")) and
     (.immutable_image | test("@sha256:[0-9a-f]{64}$")) and
     (.phase4.run_id | tostring) == $phase4_run and
     (.failed_phase5.run_id | tostring) == $failed_run and
     .failed_phase5_retry == {
       run_id:33990741282,run_number:3,run_attempt:1,
       event:"workflow_dispatch",head_sha:"7dba656fe37098f0b7a2576f49803eb10d49f1be",
       conclusion:"failure",created_at:"2026-09-05T20:39:01Z",
       run_started_at:"2026-09-05T20:39:01Z",updated_at:"2026-09-05T21:26:13Z",
       workflow:{id:351113264,name:"Reconcile failed Phase 5 promotion 33979778020",
                 path:".github/workflows/phase5_failed_promotion_retry.yml"},
       job:{id:101372396515,name:"reconcile-and-retry",
            started_at:"2026-09-05T20:39:05Z",completed_at:"2026-09-05T21:26:12Z"},
       artifact:{id:9977196639,
                 name:"phase5-failed-promotion-retry-rollback-33979778020",
                 size_in_bytes:9862789,
                 digest:"sha256:b20af9ba4ad5dff00d81fc7646dd05ff30c16cf0bf3f811495044818afc026ec",
                 expires_at:"2026-12-04T20:39:03Z"},
       predecessor_replay_sha256:"07056fa175c71195039bbfdf420036d382373b53700bbd6ca6857fa1bfddcad7",
       predecessor_descriptor_sha256:"74172ed974d5608d0d935a8f5463a63d7f658ee8ded31d637c09165e88548ebc",
       status_members:["retry-smoke-sequence-1-legislative-status.json",
                       "retry-smoke-sequence-2-executive-status.json",
                       "retry-smoke-sequence-3-ai-status.json",
                       "retry-smoke-sequence-4-dashboard-status.json"],
       baseline_heads:{
         legislative:{generation:7,snapshot_sha256:"db8ed21c1a5cb9b668ee23acb0a9813eb3ba2561130337677ab7b2c73013931a"},
         executive:{generation:7,snapshot_sha256:"0c0c141424f4d4a597606ed95f00d0fb5c64d75a3cc59ae3e35539f90125ee72"},
         ai:{generation:6,snapshot_sha256:"69b001d2b307843ae6f708ccdc3717272596225a46847b5892c984da90053ae6"},
         dashboard:{generation:7,snapshot_sha256:"0f601dfb15d5ed5809d61245ee4feff9ac1eec63ff50f79ce6d88ac090d92348"}},
       terminal_heads:{
         legislative:{generation:8,snapshot_sha256:"ad767bf6f098f4f7bf47bff655a38d04c281a8826f6cf7733dc4cdeebe5a2208"},
         executive:{generation:8,snapshot_sha256:"9902fb9fdebd93e089f3a9e0b2a8c0fc60481237f05dc11bd639f40e6770eb57"},
         ai:{generation:7,snapshot_sha256:"adac132b2e629eff086e505c980e8912bcbf697c4b2deab3030c5d925116ce1e"},
         dashboard:{generation:8,snapshot_sha256:"42e6dea7db23a933bff2f653f57f05d7b4a46e67d9b4acd64fcb3a83619d200b"}}
     } and
     (.concurrent_legacy_ai.run_id | tostring) == $legacy_ai_run and
     .legacy_dashboard.role == "dashboard" and
     (.legacy_dashboard.run_id | tostring) == $dashboard_run and
     (.recovery_runs | type) == "array" and (.recovery_runs | length) == 2 and
     (.recovery_runs[0].role == "legislative") and
     (.recovery_runs[0].run_id | tostring) == $recovery_legislative and
     (.recovery_runs[0].predecessor_artifact.id | type) == "number" and
     .recovery_runs[0].predecessor_artifact.id > 0 and
     (.recovery_runs[0].artifact.id | type) == "number" and
     .recovery_runs[0].artifact.id > 0 and
     (.recovery_runs[0].output_artifact.id | type) == "number" and
     .recovery_runs[0].output_artifact.id > 0 and
     (.recovery_runs[1].role == "executive") and
     (.recovery_runs[1].run_id | tostring) == $recovery_executive and
     (.recovery_runs[1].predecessor_artifact.id | type) == "number" and
     .recovery_runs[1].predecessor_artifact.id > 0 and
     (.recovery_runs[1].artifact.id | type) == "number" and
     .recovery_runs[1].artifact.id > 0 and
     (.recovery_runs[1].output_artifact.id | type) == "number" and
     .recovery_runs[1].output_artifact.id > 0 and
     .frozen_legacy_successors == [
       {
         role:"legislative",run_id:$successor_legislative,run_number:59,run_attempt:1,
         event:"schedule",head_sha:"40d252f4b26f8235a8a61d5c05d1e8a1b2bc76f2",
         conclusion:"success",created_at:"2026-09-05T19:27:28Z",
         run_started_at:"2026-09-05T19:27:28Z",updated_at:"2026-09-05T19:29:36Z",
         workflow:{id:345003824,name:"Legislative purchase tracker v2",
                   path:".github/workflows/legislative_trade_tracker_v2.yml"},
         job:{id:101362770866,name:"track",started_at:"2026-09-05T19:27:30Z",
              completed_at:"2026-09-05T19:29:35Z"},
         predecessor_artifact:{
           id:9973858440,name:"legislative-tracker-state",size_in_bytes:759113,
           digest:"sha256:2b80d235e7cfc74cde59c47bdb4fcecd4f80ab7a420dc31462baf83db1f72d4e",
           expires_at:"2026-12-04T17:33:07Z",producer_run_id:33981311523,
           producer_head_sha:"042f22e0a08f1f3ea69f62a0842a4cefdea6230c"},
         artifact:{
           id:9975534045,name:"legislative-tracker-state",size_in_bytes:759138,
           digest:"sha256:49b12457193ec72629ec4afea38acdb0074c49687354993842c7495a3919c951",
           expires_at:"2026-12-04T19:27:28Z"},
         output_artifact:{
           id:9975534339,name:"legislative-purchase-output-33987160591-1",
           size_in_bytes:149716,
           digest:"sha256:882d587ba282d8bc1801f76e2ad85cf69508c9d61ac2b7925a1a683426ded497",
           expires_at:"2026-10-05T19:29:31Z"}
       },
       {
         role:"executive",run_id:$successor_executive,run_number:50,run_attempt:1,
         event:"schedule",head_sha:"40d252f4b26f8235a8a61d5c05d1e8a1b2bc76f2",
         conclusion:"success",created_at:"2026-09-05T19:26:49Z",
         run_started_at:"2026-09-05T19:26:49Z",updated_at:"2026-09-05T19:29:17Z",
         workflow:{id:344663671,name:"Executive purchase tracker",
                   path:".github/workflows/executive_trade_tracker.yml"},
         job:{id:101362685264,name:"track",started_at:"2026-09-05T19:26:51Z",
              completed_at:"2026-09-05T19:29:17Z"},
         predecessor_artifact:{
           id:9973859530,name:"executive-tracker-state",size_in_bytes:512016,
           digest:"sha256:f86fe1b4c8dd832aefe71c0385d848add243820a8a7158342ba4e2448349e0e1",
           expires_at:"2026-12-04T17:33:09Z",producer_run_id:33981312757,
           producer_head_sha:"042f22e0a08f1f3ea69f62a0842a4cefdea6230c"},
         artifact:{
           id:9975529940,name:"executive-tracker-state",size_in_bytes:512042,
           digest:"sha256:0f0cd0e3fb30a43e32d50bd684b5bfb143343460c69bcb54b590ebd0d687c67f",
           expires_at:"2026-12-04T19:26:49Z"},
          output_artifact:{
            id:9975530113,name:"executive-purchase-output-33987130349",
            size_in_bytes:495654,
            digest:"sha256:c947b27b4a006efa074db1295753a0d4d215c3857acd942d634026a8a9355d4d",
            expires_at:"2026-10-05T19:29:14Z"}
       },
       {
         role:"legislative",run_id:$successor2_legislative,run_number:60,run_attempt:1,
         event:"workflow_dispatch",head_sha:"7dba656fe37098f0b7a2576f49803eb10d49f1be",
         conclusion:"success",created_at:"2026-09-05T21:20:40Z",
         run_started_at:"2026-09-05T21:20:40Z",updated_at:"2026-09-05T21:23:20Z",
         workflow:{id:345003824,name:"Legislative purchase tracker v2",
                   path:".github/workflows/legislative_trade_tracker_v2.yml"},
         job:{id:101377828721,name:"track",started_at:"2026-09-05T21:20:45Z",
              completed_at:"2026-09-05T21:23:19Z"},
         predecessor_artifact:{
           id:9975534045,name:"legislative-tracker-state",size_in_bytes:759138,
           digest:"sha256:49b12457193ec72629ec4afea38acdb0074c49687354993842c7495a3919c951",
           expires_at:"2026-12-04T19:27:28Z",producer_run_id:33987160591,
           producer_head_sha:"40d252f4b26f8235a8a61d5c05d1e8a1b2bc76f2"},
         artifact:{
           id:9977152928,name:"legislative-tracker-state",size_in_bytes:759177,
           digest:"sha256:d228a953420d0e3d259363d9825b9f21a0a07e1d518828ea4973fe954db3e59f",
           expires_at:"2026-12-04T21:20:42Z"},
         output_artifact:{
           id:9977153300,name:"legislative-purchase-output-33992770754-1",
           size_in_bytes:149724,
           digest:"sha256:b444e6f83038fd3f44c70287e37849a6a175a2be0384e5df2d245f7915a09c7b",
           expires_at:"2026-10-05T21:23:14Z"}
       },
       {
         role:"executive",run_id:$successor2_executive,run_number:51,run_attempt:1,
         event:"workflow_dispatch",head_sha:"7dba656fe37098f0b7a2576f49803eb10d49f1be",
         conclusion:"success",created_at:"2026-09-05T21:20:42Z",
         run_started_at:"2026-09-05T21:20:42Z",updated_at:"2026-09-05T21:23:09Z",
         workflow:{id:344663671,name:"Executive purchase tracker",
                   path:".github/workflows/executive_trade_tracker.yml"},
         job:{id:101377831574,name:"track",started_at:"2026-09-05T21:20:45Z",
              completed_at:"2026-09-05T21:23:08Z"},
         predecessor_artifact:{
           id:9975529940,name:"executive-tracker-state",size_in_bytes:512042,
           digest:"sha256:0f0cd0e3fb30a43e32d50bd684b5bfb143343460c69bcb54b590ebd0d687c67f",
           expires_at:"2026-12-04T19:26:49Z",producer_run_id:33987130349,
           producer_head_sha:"40d252f4b26f8235a8a61d5c05d1e8a1b2bc76f2"},
         artifact:{
           id:9977151026,name:"executive-tracker-state",size_in_bytes:512074,
           digest:"sha256:c3884c54bfb554e867e072c2463f3b2a4a510b295b228c5bb3fe5edada7c3d17",
           expires_at:"2026-12-04T21:20:43Z"},
         output_artifact:{
           id:9977151187,name:"executive-purchase-output-33992772006",
           size_in_bytes:495657,
           digest:"sha256:739c9cc69fb2c83ae90daeddae348a45f8e99f3e3059b0a26f02b912e23e4d05",
           expires_at:"2026-10-05T21:23:06Z"}
       }
     ] and
     .frozen_legacy_successors[0].predecessor_artifact ==
       (.recovery_runs[0].artifact + {
         producer_run_id:.recovery_runs[0].run_id,
         producer_head_sha:.recovery_runs[0].head_sha}) and
     .frozen_legacy_successors[1].predecessor_artifact ==
       (.recovery_runs[1].artifact + {
         producer_run_id:.recovery_runs[1].run_id,
         producer_head_sha:.recovery_runs[1].head_sha}) and
     .frozen_legacy_successors[2].predecessor_artifact ==
       (.frozen_legacy_successors[0].artifact + {
         producer_run_id:.frozen_legacy_successors[0].run_id,
         producer_head_sha:.frozen_legacy_successors[0].head_sha}) and
     .frozen_legacy_successors[3].predecessor_artifact ==
       (.frozen_legacy_successors[1].artifact + {
         producer_run_id:.frozen_legacy_successors[1].run_id,
         producer_head_sha:.frozen_legacy_successors[1].head_sha}) and
     (.expected_continuation_heads | type) == "object" and
     (.expected_continuation_heads | keys | sort) == (["ai","dashboard","executive","legislative"] | sort) and
     all(.expected_continuation_heads[];
       (.generation | type) == "number" and .generation > 0 and
       (.snapshot_sha256 | test("^[0-9a-f]{64}$"))) and
     .rebaseline_authorized == false and
     .legacy_artifact_merge_or_import_authorized == false and
     .concurrent_legacy_ai.merge_or_import_authorized == false and
     (.concurrent_legacy_ai.conflict.runtime_snapshot_sha256 | test("^[0-9a-f]{64}$")) and
     (.concurrent_legacy_ai.conflict.analysis_id | type) == "string" and
     (.concurrent_legacy_ai.conflict.trade_id | type) == "string" and
     (.concurrent_legacy_ai.conflict.document_content_hash | type) == "string"' \
    "${PHASE5_RETRY_DESCRIPTOR}" >/dev/null || {
      echo "Phase 5 retry descriptor does not bind the exact authorized incident." >&2
      return 1
    }
}

phase5_retry_verify_frozen_context() {
  local live_repository live_main checkout
  verify_canonical_context || return 1
  [[ "${GITHUB_EVENT_NAME:-}" == "workflow_dispatch" ]] || {
    echo "The failed Phase 5 retry is workflow_dispatch only." >&2
    return 1
  }
  [[ "${GITHUB_REF:-}" == "refs/heads/main" ]] || {
    echo "The failed Phase 5 retry is restricted to main." >&2
    return 1
  }
  [[ "${CONTROL_REVISION}" =~ ^[0-9a-f]{40}$ ]] || {
    echo "The frozen retry revision is malformed." >&2
    return 1
  }
  [[ "${GITHUB_SHA:-}" == "${CONTROL_REVISION}" ]] || {
    echo "The dispatched revision differs from the acknowledged frozen main revision." >&2
    return 1
  }
  checkout="$(git rev-parse HEAD)" || return 1
  [[ "${checkout}" == "${CONTROL_REVISION}" ]] || {
    echo "The retry checkout differs from the frozen main revision." >&2
    return 1
  }
  live_repository="$(gh api "repos/${GITHUB_REPOSITORY}")" || return 1
  jq -e \
    'type == "object" and .id == 1349678672 and
     .full_name == "maglothinm/MyETF-Intelligence" and
     .default_branch == "main"' <<<"${live_repository}" >/dev/null || {
      echo "The live repository identity or default branch differs from the retry boundary." >&2
      return 1
    }
  live_main="$(gh api "repos/${GITHUB_REPOSITORY}/commits/main" --jq '.sha')" || return 1
  [[ "${live_main}" == "${CONTROL_REVISION}" ]] || {
    echo "Canonical main advanced after the retry was dispatched." >&2
    return 1
  }
}

phase5_retry_capture_run() {
  local descriptor_path="$1" stem="$2" run_id
  run_id="$(phase5_retry_descriptor_value "${descriptor_path}.run_id | select(type == \"number\" and . > 0)")" || return 1
  gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}" \
    > "${PHASE5_RETRY_INCIDENT_DIR}/${stem}-run.json" || return 1
  gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}/jobs?filter=all&per_page=100" \
    > "${PHASE5_RETRY_INCIDENT_DIR}/${stem}-jobs.json" || return 1
}

phase5_retry_capture_artifact() {
  local descriptor_path="$1" stem="$2" artifact_id
  artifact_id="$(phase5_retry_descriptor_value "${descriptor_path}.id | select(type == \"number\" and . > 0)")" || return 1
  gh api "repos/${GITHUB_REPOSITORY}/actions/artifacts/${artifact_id}" \
    > "${PHASE5_RETRY_INCIDENT_DIR}/${stem}-artifact.json" || return 1
  gh api "repos/${GITHUB_REPOSITORY}/actions/artifacts/${artifact_id}/zip" \
    > "${PHASE5_RETRY_INCIDENT_DIR}/${stem}.zip" || return 1
}

phase5_retry_download_incident_evidence() {
  mkdir -p "${PHASE5_RETRY_INCIDENT_DIR}" || return 1
  phase5_retry_verify_descriptor_identity || return 1

  phase5_retry_capture_run '.phase4' phase4 || return 1
  phase5_retry_capture_artifact '.phase4.artifact' phase4 || return 1
  phase5_retry_capture_run '.failed_phase5' failed-phase5 || return 1
  phase5_retry_capture_artifact '.failed_phase5.artifact' failed-phase5 || return 1
  phase5_retry_capture_run '.failed_phase5_retry' failed-retry || return 1
  phase5_retry_capture_artifact '.failed_phase5_retry.artifact' failed-retry || return 1

  phase5_retry_capture_run '.concurrent_legacy_ai' concurrent-legacy-ai || return 1
  phase5_retry_capture_artifact \
    '.concurrent_legacy_ai.predecessor_artifact' concurrent-legacy-ai-predecessor || return 1
  phase5_retry_capture_artifact \
    '.concurrent_legacy_ai.state_artifact' concurrent-legacy-ai-state || return 1
  phase5_retry_capture_artifact \
    '.concurrent_legacy_ai.output_artifact' concurrent-legacy-ai-output || return 1

  phase5_retry_capture_run '.recovery_runs[0]' recovery-legislative || return 1
  phase5_retry_capture_artifact \
    '.recovery_runs[0].predecessor_artifact' recovery-legislative-predecessor || return 1
  phase5_retry_capture_artifact '.recovery_runs[0].artifact' recovery-legislative || return 1
  phase5_retry_capture_artifact \
    '.recovery_runs[0].output_artifact' recovery-legislative-output || return 1
  phase5_retry_capture_run '.recovery_runs[1]' recovery-executive || return 1
  phase5_retry_capture_artifact \
    '.recovery_runs[1].predecessor_artifact' recovery-executive-predecessor || return 1
  phase5_retry_capture_artifact '.recovery_runs[1].artifact' recovery-executive || return 1
  phase5_retry_capture_artifact \
    '.recovery_runs[1].output_artifact' recovery-executive-output || return 1

  phase5_retry_capture_run \
    '.frozen_legacy_successors[0]' frozen-successor-legislative || return 1
  phase5_retry_capture_artifact \
    '.frozen_legacy_successors[0].artifact' frozen-successor-legislative || return 1
  phase5_retry_capture_artifact \
    '.frozen_legacy_successors[0].output_artifact' frozen-successor-legislative-output || return 1
  phase5_retry_capture_run \
    '.frozen_legacy_successors[1]' frozen-successor-executive || return 1
  phase5_retry_capture_artifact \
    '.frozen_legacy_successors[1].artifact' frozen-successor-executive || return 1
  phase5_retry_capture_artifact \
    '.frozen_legacy_successors[1].output_artifact' frozen-successor-executive-output || return 1
  phase5_retry_capture_run \
    '.frozen_legacy_successors[2]' frozen-successor2-legislative || return 1
  phase5_retry_capture_artifact \
    '.frozen_legacy_successors[2].artifact' frozen-successor2-legislative || return 1
  phase5_retry_capture_artifact \
    '.frozen_legacy_successors[2].output_artifact' frozen-successor2-legislative-output || return 1
  phase5_retry_capture_run \
    '.frozen_legacy_successors[3]' frozen-successor2-executive || return 1
  phase5_retry_capture_artifact \
    '.frozen_legacy_successors[3].artifact' frozen-successor2-executive || return 1
  phase5_retry_capture_artifact \
    '.frozen_legacy_successors[3].output_artifact' frozen-successor2-executive-output || return 1
  phase5_retry_verify_legacy_high_water downloaded || return 1
}

phase5_retry_capture_workflow_run_inventory() {
  local workflow="$1" output="$2" pages
  pages="${output}.pages"
  gh api --method GET --paginate --slurp \
    "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/runs" \
    -f per_page=100 > "${pages}" || return 1
  jq -e \
    '. as $pages |
     type == "array" and length > 0 and
     all($pages[];
       type == "object" and (.total_count | type) == "number" and
       (.workflow_runs | type) == "array" and
       .total_count == $pages[0].total_count)' "${pages}" >/dev/null || {
      echo "The ${workflow} workflow-run pagination response is malformed." >&2
      return 1
    }
  jq '{total_count:.[0].total_count,workflow_runs:[.[].workflow_runs[]]}' \
    "${pages}" > "${output}" || return 1
  rm -f -- "${pages}"
  jq -e \
    '(.total_count | type) == "number" and
     (.workflow_runs | type) == "array" and
     .total_count == (.workflow_runs | length) and
     ([.workflow_runs[].id] | unique | length) == (.workflow_runs | length)' \
    "${output}" >/dev/null || {
      echo "The ${workflow} workflow-run inventory is incomplete or duplicated." >&2
      return 1
    }
}

phase5_retry_capture_artifact_inventory() {
  local artifact_name="$1" output="$2" pages
  pages="${output}.pages"
  gh api --method GET --paginate --slurp \
    "repos/${GITHUB_REPOSITORY}/actions/artifacts" \
    -f name="${artifact_name}" -f per_page=100 > "${pages}" || return 1
  jq -e \
    '. as $pages |
     type == "array" and length > 0 and
     all($pages[];
       type == "object" and (.total_count | type) == "number" and
       (.artifacts | type) == "array" and
       .total_count == $pages[0].total_count)' "${pages}" >/dev/null || {
      echo "The ${artifact_name} artifact pagination response is malformed." >&2
      return 1
    }
  jq '{total_count:.[0].total_count,artifacts:[.[].artifacts[]]}' \
    "${pages}" > "${output}" || return 1
  rm -f -- "${pages}"
  jq -e \
    '(.total_count | type) == "number" and
     (.artifacts | type) == "array" and
     .total_count == (.artifacts | length) and
     ([.artifacts[].id] | unique | length) == (.artifacts | length)' \
    "${output}" >/dev/null || {
      echo "The ${artifact_name} artifact inventory is incomplete or duplicated." >&2
      return 1
    }
}

phase5_retry_verify_no_active_legacy_runs() {
  local suffix="${1:-current}" workflow
  local active_file="${PHASE5_RETRY_INCIDENT_DIR}/legacy-active-run-ids-${suffix}.txt"
  : > "${active_file}" || return 1
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    if ! gh api --paginate \
      "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/runs?per_page=100" \
      --jq '.workflow_runs[] | select(.status != "completed") | .id' \
      >> "${active_file}"; then
      echo "Unable to verify the post-capture active-run inventory for ${workflow}." >&2
      return 1
    fi
  done
  sort -u -o "${active_file}" "${active_file}" || return 1
  if [[ -s "${active_file}" ]]; then
    echo "A legacy workflow run became active during high-water capture." >&2
    return 1
  fi
}

phase5_retry_verify_legacy_high_water() {
  local suffix="${1:-current}" role run_path artifact_path workflow artifact_name
  local expected_run_id expected_run_created_at expected_artifact_id runs_file artifacts_file
  local specifications=(
    'legislative|.frozen_legacy_successors[2]|.frozen_legacy_successors[2].artifact|legislative_trade_tracker_v2.yml'
    'executive|.frozen_legacy_successors[3]|.frozen_legacy_successors[3].artifact|executive_trade_tracker.yml'
    'ai|.concurrent_legacy_ai|.concurrent_legacy_ai.state_artifact|ai_filing_analyst.yml'
  )
  mkdir -p "${PHASE5_RETRY_INCIDENT_DIR}" || return 1
  verify_legacy_workflows_state disabled_manually || {
    echo "The legacy writer fence was not closed before high-water capture." >&2
    return 1
  }
  for specification in "${specifications[@]}"; do
    IFS='|' read -r role run_path artifact_path workflow <<<"${specification}"
    expected_run_id="$(phase5_retry_descriptor_value "${run_path}.run_id")" || return 1
    expected_run_created_at="$(phase5_retry_descriptor_value "${run_path}.created_at")" || return 1
    expected_artifact_id="$(phase5_retry_descriptor_value "${artifact_path}.id")" || return 1
    artifact_name="$(phase5_retry_descriptor_value "${artifact_path}.name")" || return 1
    runs_file="${PHASE5_RETRY_INCIDENT_DIR}/legacy-${role}-runs-${suffix}.json"
    artifacts_file="${PHASE5_RETRY_INCIDENT_DIR}/legacy-${role}-artifacts-${suffix}.json"

    phase5_retry_capture_workflow_run_inventory "${workflow}" "${runs_file}" || return 1
    phase5_retry_capture_artifact_inventory "${artifact_name}" "${artifacts_file}" || return 1

    jq -e --argjson expected_run_id "${expected_run_id}" \
      --arg expected_run_created_at "${expected_run_created_at}" \
      '.workflow_runs | type == "array" and length > 0 and
       all(.[]; .status == "completed") and
       .[0].id == $expected_run_id and
       any(.[]; .id == $expected_run_id and .status == "completed" and
         .conclusion == "success" and .created_at == $expected_run_created_at and
         .head_branch == "main" and .head_repository.id == 1349678672) and
       all(.[]; (.created_at <= $expected_run_created_at) or
         (.status == "completed" and .conclusion != "success"))' \
      "${runs_file}" >/dev/null || {
        echo "A later successful ${role} legacy producer run exists or its high-water is ambiguous." >&2
        return 1
      }
    jq -e --argjson expected_artifact_id "${expected_artifact_id}" \
      --argjson expected_run_id "${expected_run_id}" \
      '[.artifacts[] | select(.expired == false)] |
       sort_by(.created_at, .id) | last |
       .id == $expected_artifact_id and .workflow_run.id == $expected_run_id and
       .workflow_run.repository_id == 1349678672 and
       .workflow_run.head_branch == "main"' "${artifacts_file}" >/dev/null || {
        echo "The current ${role} protected-artifact high-water differs from the pinned incident artifact." >&2
        return 1
      }
  done

  expected_run_id="$(phase5_retry_descriptor_value '.legacy_dashboard.run_id')" || return 1
  expected_run_created_at="$(phase5_retry_descriptor_value '.legacy_dashboard.created_at')" || return 1
  runs_file="${PHASE5_RETRY_INCIDENT_DIR}/legacy-dashboard-runs-${suffix}.json"
  phase5_retry_capture_workflow_run_inventory \
    publish_trade_dashboard.yml "${runs_file}" || return 1
  jq -e --argjson expected_run_id "${expected_run_id}" \
    --arg expected_run_created_at "${expected_run_created_at}" \
    '.workflow_runs | type == "array" and length > 0 and
     all(.[]; .status == "completed") and
     .[0].id == $expected_run_id and .[0].status == "completed" and
     .[0].created_at == $expected_run_created_at and
     .[0].conclusion == "success" and .[0].head_branch == "main" and
     .[0].head_repository.id == 1349678672' "${runs_file}" >/dev/null || {
      echo "The dashboard legacy workflow no longer has the pinned completed run at its high-water." >&2
      return 1
    }
  verify_legacy_workflows_state disabled_manually || {
    echo "The legacy writer fence opened during high-water capture." >&2
    return 1
  }
  phase5_retry_verify_no_active_legacy_runs "${suffix}" || return 1
  verify_legacy_workflows_state disabled_manually || {
    echo "The legacy writer fence opened during the post-capture active-run check." >&2
    return 1
  }
}

phase5_retry_capture_runtime_execution_inventories() {
  local suffix="$1" logical_name job output raw_output
  for logical_name in legislative executive ai dashboard; do
    job="polititrack-${logical_name}"
    output="${PHASE5_RETRY_INCIDENT_DIR}/runtime-${logical_name}-executions-${suffix}.json"
    raw_output="${output}.raw"
    gcloud run jobs executions list --job "${job}" --project "${PROJECT_ID}" \
      --region "${REGION}" --limit=1000 --format=json > "${raw_output}" || return 1
    jq -e 'type == "array" and all(.[]; type == "object")' "${raw_output}" >/dev/null || {
      echo "The Runtime execution inventory for ${job} is malformed." >&2
      return 1
    }
    jq -n --arg job "${logical_name}" --slurpfile executions "${raw_output}" \
      '{job:$job,capture_limit:1000,returned_count:($executions[0]|length),
        executions:$executions[0]}' > "${output}" || return 1
    rm -f -- "${raw_output}"
    jq -e \
      '.capture_limit == 1000 and .returned_count == (.executions | length) and
       .returned_count < .capture_limit' "${output}" >/dev/null || {
        echo "The Runtime execution inventory for ${job} reached its capture boundary." >&2
        return 1
      }
  done
}

phase5_retry_capture_disabled_legacy_workflow_states() {
  local suffix="$1" specification role workflow output
  local specifications=(
    'legislative|legislative_trade_tracker_v2.yml'
    'executive|executive_trade_tracker.yml'
    'ai|ai_filing_analyst.yml'
    'dashboard|publish_trade_dashboard.yml'
  )
  for specification in "${specifications[@]}"; do
    IFS='|' read -r role workflow <<<"${specification}"
    output="${PHASE5_RETRY_INCIDENT_DIR}/legacy-${role}-workflow-${suffix}.json"
    gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}" > "${output}" || return 1
    jq -e --arg path ".github/workflows/${workflow}" \
      '.state == "disabled_manually" and .path == $path and
       (.id | type) == "number" and (.name | type) == "string"' \
      "${output}" >/dev/null || {
        echo "The ${role} legacy workflow is not exactly and manually disabled." >&2
        return 1
      }
  done
}

phase5_retry_write_observed_legacy_states() {
  local temporary="${LEGACY_STATE_FILE}.tmp"
  mkdir -p "$(dirname "${LEGACY_STATE_FILE}")" || return 1
  jq -n \
    '{"legislative_trade_tracker_v2.yml":"active",
      "executive_trade_tracker.yml":"active",
      "ai_filing_analyst.yml":"disabled_manually",
      "publish_trade_dashboard.yml":"active"}' > "${temporary}" || return 1
  mv "${temporary}" "${LEGACY_STATE_FILE}" || return 1
}

phase5_retry_write_frozen_legacy_states() {
  local temporary="${LEGACY_STATE_FILE}.tmp"
  mkdir -p "$(dirname "${LEGACY_STATE_FILE}")" || return 1
  jq -n \
    '{"legislative_trade_tracker_v2.yml":"disabled_manually",
      "executive_trade_tracker.yml":"disabled_manually",
      "ai_filing_analyst.yml":"disabled_manually",
      "publish_trade_dashboard.yml":"disabled_manually"}' > "${temporary}" || return 1
  mv "${temporary}" "${LEGACY_STATE_FILE}" || return 1
}

phase5_retry_observed_legacy_route_kind() {
  [[ -f "${LEGACY_STATE_FILE}" ]] || {
    echo "Observed legacy workflow state is missing." >&2
    return 1
  }
  if jq -e \
    '. == {"legislative_trade_tracker_v2.yml":"disabled_manually",
            "executive_trade_tracker.yml":"disabled_manually",
            "ai_filing_analyst.yml":"disabled_manually",
            "publish_trade_dashboard.yml":"disabled_manually"}' \
    "${LEGACY_STATE_FILE}" >/dev/null; then
    printf '%s\n' frozen_disabled
    return 0
  fi
  if jq -e \
    '. == {"legislative_trade_tracker_v2.yml":"active",
            "executive_trade_tracker.yml":"active",
            "ai_filing_analyst.yml":"disabled_manually",
            "publish_trade_dashboard.yml":"active"}' \
    "${LEGACY_STATE_FILE}" >/dev/null; then
    printf '%s\n' historic_active
    return 0
  fi
  echo "Observed legacy workflow state is neither the exact frozen nor historic rollback route." >&2
  return 1
}

phase5_retry_restore_pre_live_legacy_route() {
  # Before cloud mutation the only authorized starting routes are the temporary
  # all-disabled maintenance fence and the exact historical rollback route.  A
  # mixed state is never normalized automatically.
  if verify_legacy_workflows_state disabled_manually >/dev/null 2>&1; then
    phase5_retry_write_observed_legacy_states || return 1
    restore_legacy_workflows_observed || return 1
  else
    phase5_retry_write_observed_legacy_states || return 1
    verify_legacy_workflows_match_observed || {
      echo "Pre-live failure found neither the frozen maintenance fence nor the historical rollback route." >&2
      return 1
    }
  fi
  [[ "$(phase5_retry_observed_legacy_route_kind)" == "historic_active" ]] || return 1
  verify_legacy_workflows_match_observed
}

phase5_retry_validate_permanent_control_role_receipt() {
  local permanent_control_role
  permanent_control_role="projects/${PROJECT_ID}/roles/${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID}"
  [[ -s "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}" ]] || {
    echo "The live permanent Phase 3 control-role receipt is missing." >&2
    return 1
  }
  jq -e --arg name "${permanent_control_role}" \
    '. as $role |
     .name == $name and (.deleted // false) == false and .stage == "GA" and
     (.includedPermissions | type) == "array" and
     all(["cloudscheduler.jobs.pause","cloudscheduler.jobs.get","cloudscheduler.jobs.list"][];
       . as $permission | ($role.includedPermissions | index($permission)) != null) and
     (.includedPermissions | index("cloudscheduler.jobs.enable") | not) and
     (.includedPermissions | index("cloudscheduler.jobs.run") | not) and
     (.includedPermissions | index("cloudscheduler.jobs.delete") | not)' \
    "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}" >/dev/null || {
      echo "The permanent Phase 3 control role cannot guarantee constrained rollback." >&2
      return 1
    }
}

phase5_retry_capture_role_viewer_policy() {
  if ! gcloud projects get-iam-policy "${PROJECT_ID}" --format=json \
    > "${PHASE5_RETRY_ROLE_VIEWER_POLICY}"; then
    echo "Unable to read project IAM while checking temporary Role Viewer authority." >&2
    return 1
  fi
  jq -e 'type == "object" and (.bindings | type) == "array"' \
    "${PHASE5_RETRY_ROLE_VIEWER_POLICY}" >/dev/null || {
      echo "Project IAM policy is malformed while checking temporary Role Viewer authority." >&2
      return 1
    }
}

phase5_retry_role_viewer_any_present() {
  phase5_retry_capture_role_viewer_policy || return 2
  jq -e --arg member "${DEPLOYER_MEMBER}" --arg role "${PHASE5_RETRY_ROLE_VIEWER_ROLE}" \
    '[.bindings[]? | select(.role == $role) | .members[]?] |
     any(. == $member)' "${PHASE5_RETRY_ROLE_VIEWER_POLICY}" >/dev/null
}

phase5_retry_role_viewer_exact_present() {
  [[ -s "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" ]] || return 2
  phase5_retry_capture_role_viewer_policy || return 2
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    --arg role "${PHASE5_RETRY_ROLE_VIEWER_ROLE}" \
    --slurpfile expected "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" \
    '([.bindings[]? |
        select(.role == $role and .condition == $expected[0] and
               any(.members[]?; . == $member))] | length) == 1 and
     ([.bindings[]? | select(.role == $role) | .members[]? |
        select(. == $member)] | length) == 1' \
    "${PHASE5_RETRY_ROLE_VIEWER_POLICY}" >/dev/null
}

phase5_retry_role_viewer_exact_binding_present() {
  [[ -s "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" ]] || return 2
  phase5_retry_capture_role_viewer_policy || return 2
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    --arg role "${PHASE5_RETRY_ROLE_VIEWER_ROLE}" \
    --slurpfile expected "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" \
    'any(.bindings[]?;
       .role == $role and .condition == $expected[0] and
       any(.members[]?; . == $member))' \
    "${PHASE5_RETRY_ROLE_VIEWER_POLICY}" >/dev/null
}

phase5_retry_verify_role_viewer_removed() {
  local status
  if phase5_retry_role_viewer_any_present; then
    echo "IAM Role Viewer remains bound to the deployer." >&2
    return 1
  else
    status=$?
  fi
  [[ "${status}" == "1" ]] || {
    echo "Temporary IAM Role Viewer cleanup is unverified." >&2
    return 1
  }
}

phase5_retry_verify_role_viewer_condition_window() {
  [[ -s "${PHASE5_RETRY_ROLE_VIEWER_GRANT}" ]] || {
    echo "Temporary IAM Role Viewer grant metadata is missing." >&2
    return 1
  }
  python - "${PHASE5_RETRY_ROLE_VIEWER_GRANT}" <<'PY'
import datetime as dt
import json
import sys
from pathlib import Path

grant = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
now = dt.datetime.now(dt.timezone.utc)
issued = dt.datetime.fromisoformat(grant["issued_at"].replace("Z", "+00:00"))
expires = dt.datetime.fromisoformat(grant["expires_at"].replace("Z", "+00:00"))
propagation_deadline = dt.datetime.fromisoformat(
    grant["propagation_deadline_at"].replace("Z", "+00:00")
)
window = (expires - issued).total_seconds()
remaining = (expires - now).total_seconds()
if not (
    890 <= window <= 910
    and 595 <= (propagation_deadline - issued).total_seconds() <= 605
    and propagation_deadline < expires
    and 240 <= remaining <= 910
):
    raise SystemExit("Temporary IAM Role Viewer condition is outside its authorized time window.")
PY
}

phase5_retry_remove_role_viewer() {
  local attempt status error_file
  for attempt in $(seq 1 18); do
    error_file="${RESOURCE_DIR}/role-viewer-remove-attempt-${attempt}.stderr"
    if phase5_retry_role_viewer_exact_binding_present; then
      gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
        --member "${DEPLOYER_MEMBER}" --role "${PHASE5_RETRY_ROLE_VIEWER_ROLE}" \
        --condition-from-file="${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" \
        --quiet --format=none >/dev/null 2> "${error_file}" || true
    else
      status=$?
      [[ "${status}" == "1" || "${status}" == "2" ]] || return 1
    fi
    if phase5_retry_verify_role_viewer_removed; then
      cp -- "${PHASE5_RETRY_ROLE_VIEWER_POLICY}" \
        "${PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}" || return 1
      return 0
    fi
    sleep 10
  done
  echo "Temporary IAM Role Viewer could not be verified physically absent." >&2
  return 1
}

phase5_retry_finalize_role_viewer_evidence() {
  local receipt_tmp before_sha granted_sha removed_sha condition_sha grant_sha
  local permanent_control_role
  phase5_retry_validate_permanent_control_role_receipt || return 1
  phase5_retry_verify_role_viewer_removed || return 1
  cp -- "${PHASE5_RETRY_ROLE_VIEWER_POLICY}" \
    "${PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}" || return 1
  permanent_control_role="projects/${PROJECT_ID}/roles/${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID}"
  jq -e --arg member "${DEPLOYER_MEMBER}" --arg role "${permanent_control_role}" \
    '([.bindings[]? |
       select(.role == $role and (.condition? == null) and
              any(.members[]?; . == $member))] | length) == 1' \
    "${PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}" >/dev/null || {
      echo "The permanent rollback role binding changed during the JIT role read." >&2
      return 1
    }
  jq -e --arg member "${DEPLOYER_MEMBER}" --arg role "${PHASE5_RETRY_SCHEDULER_CONTROL_ROLE}" \
    '([.bindings[]? | select(.role == $role) | .members[]?] |
      any(. == $member) | not)' \
    "${PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}" >/dev/null || {
      echo "Scheduler activation authority overlapped the JIT role read." >&2
      return 1
    }
  before_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_ROLE_VIEWER_BEFORE_POLICY}")" || return 1
  granted_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_ROLE_VIEWER_GRANTED_POLICY}")" || return 1
  removed_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}")" || return 1
  condition_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}")" || return 1
  grant_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_ROLE_VIEWER_GRANT}")" || return 1
  receipt_tmp="${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}.tmp"
  jq --slurpfile grant "${PHASE5_RETRY_ROLE_VIEWER_GRANT}" \
    --arg before_sha "${before_sha}" --arg granted_sha "${granted_sha}" \
    --arg removed_sha "${removed_sha}" --arg condition_sha "${condition_sha}" \
    --arg grant_sha "${grant_sha}" \
    '. + {temporary_role_viewer_evidence:{
      result:"jit_role_viewer_removed",grant:$grant[0],absent_before_grant:true,
      grant_observed:true,live_role_described:true,physically_absent_after_removal:true,
      evidence_sha256:{before_policy:$before_sha,granted_policy:$granted_sha,
        removed_policy:$removed_sha,condition:$condition_sha,grant_request:$grant_sha}}}' \
    "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}" > "${receipt_tmp}" || return 1
  mv -- "${receipt_tmp}" "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}" || return 1
  phase5_retry_validate_permanent_control_role_receipt
}

phase5_retry_role_describe_denial_is_propagation() {
  local error_file="$1"
  local expected_role="projects/${PROJECT_ID}/roles/${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID}"
  [[ -s "${error_file}" ]] || return 1
  grep -Fq 'PERMISSION_DENIED' "${error_file}" || return 1
  if grep -Fq "${expected_role}" "${error_file}"; then
    return 0
  fi
  # Some gcloud surfaces split the same canonical target across the project
  # and role-id fields instead of printing one resource-name token.
  grep -Fq "${PROJECT_ID}" "${error_file}" &&
    grep -Fq "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID}" "${error_file}"
}

phase5_retry_capture_and_verify_permanent_control_role() {
  local issued_at expires_at propagation_deadline_at condition_title condition_description
  local condition_expression attempt status error_file receipt_tmp role_described=false
  local deadline now remaining command_timeout
  [[ -f "${EVIDENCE_DIR}/live-mutation-started" ]] || {
    echo "The rollback trap is not armed for temporary IAM Role Viewer authority." >&2
    return 1
  }
  phase5_retry_verify_role_viewer_removed || return 1
  cp -- "${PHASE5_RETRY_ROLE_VIEWER_POLICY}" \
    "${PHASE5_RETRY_ROLE_VIEWER_BEFORE_POLICY}" || return 1
  rm -f -- "${PHASE5_RETRY_ROLE_VIEWER_GRANTED_POLICY}" \
    "${PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}" \
    "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" \
    "${PHASE5_RETRY_ROLE_VIEWER_GRANT}" \
    "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}"

  issued_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" || return 1
  expires_at="$(date -u -d '+15 minutes' +'%Y-%m-%dT%H:%M:%SZ')" || return 1
  propagation_deadline_at="$(date -u -d '+10 minutes' +'%Y-%m-%dT%H:%M:%SZ')" || return 1
  condition_title="phase5-retry-${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}-${GITHUB_RUN_ATTEMPT:?GITHUB_RUN_ATTEMPT is required}-role-viewer"
  condition_description="JIT read of the exact permanent Phase 3 custom role"
  condition_expression="request.time < timestamp(\"${expires_at}\")"
  jq -n --arg title "${condition_title}" --arg description "${condition_description}" \
    --arg expression "${condition_expression}" \
    '{title:$title,description:$description,expression:$expression}' \
    > "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" || return 1
  jq -n --arg project "${PROJECT_ID}" --arg member "${DEPLOYER_MEMBER}" \
    --arg role "${PHASE5_RETRY_ROLE_VIEWER_ROLE}" \
    --arg target_role "projects/${PROJECT_ID}/roles/${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID}" \
    --arg issued_at "${issued_at}" --arg expires_at "${expires_at}" \
    --arg propagation_deadline_at "${propagation_deadline_at}" \
    --slurpfile condition "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" \
    '{schema_version:1,result:"role_viewer_live_role_capture_requested",
      project_id:$project,member:$member,role:$role,target_role_name:$target_role,
      authorized_operation:"iam.roles.get",issued_at:$issued_at,expires_at:$expires_at,
      propagation_deadline_at:$propagation_deadline_at,condition:$condition[0],
      condition_scope:"request_time_only"}' \
    > "${PHASE5_RETRY_ROLE_VIEWER_GRANT}" || return 1
  phase5_retry_verify_role_viewer_condition_window || return 1

  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member "${DEPLOYER_MEMBER}" --role "${PHASE5_RETRY_ROLE_VIEWER_ROLE}" \
    --condition-from-file="${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" \
    --quiet --format=none || return 1

  receipt_tmp="${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}.tmp"
  deadline="$(date -u -d "${propagation_deadline_at}" +%s)" || return 1
  for attempt in $(seq 1 60); do
    now="$(date +%s)" || return 1
    (( now < deadline )) || {
      echo "Temporary IAM Role Viewer did not propagate within 600 seconds." >&2
      return 1
    }
    if phase5_retry_role_viewer_exact_present; then
      cp -- "${PHASE5_RETRY_ROLE_VIEWER_POLICY}" \
        "${PHASE5_RETRY_ROLE_VIEWER_GRANTED_POLICY}" || return 1
      phase5_retry_verify_role_viewer_condition_window || return 1
      error_file="${RESOURCE_DIR}/role-viewer-describe-attempt-${attempt}.stderr"
      remaining=$(( deadline - now ))
      command_timeout=30
      (( remaining >= command_timeout )) || command_timeout="${remaining}"
      (( command_timeout > 0 )) || return 1
      if timeout "${command_timeout}s" gcloud iam roles describe "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID}" \
        --project "${PROJECT_ID}" --format=json > "${receipt_tmp}" 2> "${error_file}"; then
        mv -- "${receipt_tmp}" "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}" || return 1
        phase5_retry_validate_permanent_control_role_receipt || return 1
        role_described=true
        break
      fi
      rm -f -- "${receipt_tmp}"
      if ! phase5_retry_role_describe_denial_is_propagation "${error_file}"; then
        cat "${error_file}" >&2
        return 1
      fi
    else
      status=$?
      [[ "${status}" == "1" ]] || return 1
    fi
    now="$(date +%s)" || return 1
    (( now + 10 < deadline )) || {
      echo "Temporary IAM Role Viewer did not propagate within 600 seconds." >&2
      return 1
    }
    sleep 10
  done
  [[ "${role_described}" == "true" ]] || {
    echo "Temporary IAM Role Viewer did not permit the bounded live role read." >&2
    return 1
  }
  phase5_retry_remove_role_viewer || return 1
  phase5_retry_verify_role_viewer_removed || return 1
  phase5_retry_finalize_role_viewer_evidence
}

phase5_retry_verify_current_base_authority_absent() {
  local job policy_file project_policy permanent_control_role
  mkdir -p "${RESOURCE_DIR}" || return 1
  rm -f -- "${LOGGING_VIEW_POLICY_RECEIPT}" \
    "${RESOURCE_DIR}/retry-preflight-logging-view-absence-receipt.json" || return 1

  # Prove the retry begins without any job-execution or project logging grant.
  # These direct reads do not depend on the logging-view cleanup receipt.
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    policy_file="${RESOURCE_DIR}/retry-preflight-${job}-execution-policy.json"
    gcloud run jobs get-iam-policy "${job}" --project "${PROJECT_ID}" \
      --region "${REGION}" --format=json > "${policy_file}" || return 1
    jq -e --arg member "${DEPLOYER_MEMBER}" \
      'type == "object" and
       ([.bindings[]? |
         select(.role == "roles/run.jobsExecutorWithOverrides") | .members[]?] |
        any(. == $member) | not)' "${policy_file}" >/dev/null || {
        echo "Temporary execution authority is already present on ${job}." >&2
        return 1
      }
  done
  project_policy="${RESOURCE_DIR}/retry-preflight-project-iam-policy.json"
  permanent_control_role="projects/${PROJECT_ID}/roles/${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID}"
  gcloud projects get-iam-policy "${PROJECT_ID}" --format=json \
    > "${project_policy}" || return 1
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    'type == "object" and
     ([.bindings[]? | select(.role == "roles/logging.admin") | .members[]?] |
      any(. == $member) | not)' "${project_policy}" >/dev/null || {
      echo "Temporary logging.admin authority is already present." >&2
      return 1
    }
  jq -e --arg member "${DEPLOYER_MEMBER}" --arg role "${PHASE5_RETRY_ROLE_VIEWER_ROLE}" \
    '([.bindings[]? | select(.role == $role) | .members[]?] |
      any(. == $member) | not)' "${project_policy}" >/dev/null || {
      echo "Temporary IAM Role Viewer authority is already present." >&2
      return 1
    }
  jq -e --arg member "${DEPLOYER_MEMBER}" --arg role "${permanent_control_role}" \
    'any(.bindings[]?;
       .role == $role and (.condition? == null) and any(.members[]?; . == $member))' \
    "${project_policy}" >/dev/null || {
      echo "The constrained deployer is no longer bound to its exact permanent control role." >&2
      return 1
    }
}

phase5_retry_capture_current_logging_view_absence_receipt() {
  local view_policy receipt_tmp attempt
  local view_policy_read=false
  # The base deployer cannot inspect a log-view IAM policy.  Grant only the
  # temporary logging.admin role, capture the current exact policy, require the
  # deployer viewAccessor binding to be absent, then remove the grant.  The
  # already-armed rollback trap removes it on every intermediate failure.
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" \
    --role roles/logging.admin --condition=None --quiet --format=none || return 1
  view_policy="${RESOURCE_DIR}/retry-preflight-logging-view-policy.json"
  for attempt in $(seq 1 18); do
    if gcloud logging views get-iam-policy _Default --bucket _Default --location global \
      --project "${PROJECT_ID}" --format=json > "${view_policy}"; then
      view_policy_read=true
      break
    fi
    sleep 5
  done
  [[ "${view_policy_read}" == "true" ]] || {
    echo "Unable to capture the current logging-view policy." >&2
    return 1
  }
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    'type == "object" and
     ([.bindings[]? | select(.role == "roles/logging.viewAccessor") | .members[]?] |
      any(. == $member) | not)' "${view_policy}" >/dev/null || {
      echo "Temporary logging-view authority is already present." >&2
      return 1
    }

  receipt_tmp="${LOGGING_VIEW_POLICY_RECEIPT}.tmp"
  jq -n \
    --arg project "${PROJECT_ID}" \
    --arg member "${DEPLOYER_MEMBER}" \
    --slurpfile policy "${view_policy}" \
    '{schema_version:1,result:"logging_view_accessor_removed",
      project_id:$project,location:"global",bucket:"_Default",view:"_Default",
      member:$member,role:"roles/logging.viewAccessor",verified_absent:true,
      policy:$policy[0]}' > "${receipt_tmp}" || return 1
  mv "${receipt_tmp}" "${LOGGING_VIEW_POLICY_RECEIPT}" || return 1
  verify_logging_view_removal_receipt || return 1
  remove_logging_authority || return 1
  verify_execution_authority_removed || return 1
  cp -- "${LOGGING_VIEW_POLICY_RECEIPT}" \
    "${RESOURCE_DIR}/retry-preflight-logging-view-absence-receipt.json" || return 1
}

phase5_retry_restore_preflight_logging_receipt_if_safe() {
  local project_policy backup
  verify_logging_view_removal_receipt >/dev/null 2>&1 && return 0
  project_policy="${RESOURCE_DIR}/retry-rollback-project-iam-policy.json"
  gcloud projects get-iam-policy "${PROJECT_ID}" --format=json \
    > "${project_policy}" || return 1
  # If logging.admin is present, the shared cleanup must capture current view
  # state itself.  Restore the preflight receipt only when the shared grant
  # failed before it could reach either logging mutation.
  if jq -e --arg member "${DEPLOYER_MEMBER}" \
    '[.bindings[]? | select(.role == "roles/logging.admin") | .members[]?] |
     any(. == $member)' "${project_policy}" >/dev/null; then
    return 0
  fi
  backup="${RESOURCE_DIR}/retry-preflight-logging-view-absence-receipt.json"
  [[ -s "${backup}" ]] || return 1
  cp -- "${backup}" "${LOGGING_VIEW_POLICY_RECEIPT}" || return 1
  verify_logging_view_removal_receipt
}

phase5_retry_verify_safe_rollback_state() {
  phase5_retry_verify_frozen_context || return 1
  verify_producer_scheduler_state PAUSED || return 1
  verify_vault_scheduler_paused || return 1
  verify_web_private || return 1
  verify_runtime_configuration shadow || return 1
  verify_legacy_workflows_match_observed || return 1
  verify_cloud_sql_private || return 1
  collect_service_accounts || return 1
  phase5_retry_verify_current_base_authority_absent || return 1
  phase5_retry_verify_scheduler_control_removed || return 1
  verify_service_account_user_removed || return 1
  phase5_retry_verify_private_web_invoker_removed || return 1
}

phase5_retry_capture_scheduler_control_policy() {
  if ! gcloud projects get-iam-policy "${PROJECT_ID}" --format=json \
    > "${PHASE5_RETRY_SCHEDULER_CONTROL_POLICY}"; then
    echo "Unable to read project IAM while checking temporary scheduler control." >&2
    return 1
  fi
  jq -e 'type == "object" and (.bindings | type) == "array"' \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_POLICY}" >/dev/null || {
      echo "Project IAM policy is malformed while checking temporary scheduler control." >&2
      return 1
    }
}

phase5_retry_scheduler_control_any_present() {
  phase5_retry_capture_scheduler_control_policy || return 2
  jq -e --arg member "${DEPLOYER_MEMBER}" --arg role "${PHASE5_RETRY_SCHEDULER_CONTROL_ROLE}" \
    '[.bindings[]? | select(.role == $role) | .members[]?] |
     any(. == $member)' "${PHASE5_RETRY_SCHEDULER_CONTROL_POLICY}" >/dev/null
}

phase5_retry_scheduler_control_exact_present() {
  [[ -s "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" ]] || return 2
  phase5_retry_capture_scheduler_control_policy || return 2
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    --arg role "${PHASE5_RETRY_SCHEDULER_CONTROL_ROLE}" \
    --slurpfile expected "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" \
    '([.bindings[]? |
        select(.role == $role and .condition == $expected[0] and
               any(.members[]?; . == $member))] | length) == 1 and
     ([.bindings[]? | select(.role == $role) | .members[]? |
        select(. == $member)] | length) == 1' \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_POLICY}" >/dev/null
}

phase5_retry_scheduler_control_exact_binding_present() {
  [[ -s "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" ]] || return 2
  phase5_retry_capture_scheduler_control_policy || return 2
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    --arg role "${PHASE5_RETRY_SCHEDULER_CONTROL_ROLE}" \
    --slurpfile expected "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" \
    'any(.bindings[]?;
       .role == $role and .condition == $expected[0] and
       any(.members[]?; . == $member))' \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_POLICY}" >/dev/null
}

phase5_retry_verify_scheduler_control_removed() {
  local status
  if phase5_retry_scheduler_control_any_present; then
    echo "Cloud Scheduler Admin remains bound to the deployer." >&2
    return 1
  else
    status=$?
  fi
  [[ "${status}" == "1" ]] || {
    echo "Temporary Cloud Scheduler control cleanup is unverified." >&2
    return 1
  }
}

phase5_retry_verify_scheduler_condition_window() {
  [[ -s "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}" ]] || {
    echo "Temporary Cloud Scheduler grant metadata is missing." >&2
    return 1
  }
  python - "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}" <<'PY'
import datetime as dt
import json
import sys
from pathlib import Path

grant = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
now = dt.datetime.now(dt.timezone.utc)
issued = dt.datetime.fromisoformat(grant["issued_at"].replace("Z", "+00:00"))
expires = dt.datetime.fromisoformat(grant["expires_at"].replace("Z", "+00:00"))
propagation_deadline = dt.datetime.fromisoformat(
    grant["propagation_deadline_at"].replace("Z", "+00:00")
)
window = (expires - issued).total_seconds()
remaining = (expires - now).total_seconds()
if not (
    1190 <= window <= 1210
    and 595 <= (propagation_deadline - issued).total_seconds() <= 605
    and propagation_deadline < expires
    and 300 <= remaining <= 1210
):
    raise SystemExit("Temporary Cloud Scheduler condition is outside its authorized time window.")
PY
}

phase5_retry_grant_scheduler_control() {
  local issued_at expires_at propagation_deadline_at
  local condition_title condition_description condition_expression attempt
  phase5_retry_verify_scheduler_control_removed || return 1
  phase5_retry_capture_and_verify_permanent_control_role || return 1
  phase5_retry_verify_role_viewer_removed || return 1
  # The Role Viewer propagation wait can be several minutes.  Recapture the
  # Scheduler policy only after that temporary reader is physically gone so an
  # intervening activation grant cannot hide behind the older pre-read policy.
  phase5_retry_verify_scheduler_control_removed || return 1
  cp -- "${PHASE5_RETRY_SCHEDULER_CONTROL_POLICY}" \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_BEFORE_POLICY}" || return 1
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    --arg role "projects/${PROJECT_ID}/roles/${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_ID}" \
    'any(.bindings[]?;
       .role == $role and (.condition? == null) and any(.members[]?; . == $member))' \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_BEFORE_POLICY}" >/dev/null || {
      echo "Rollback authority changed immediately before the JIT Scheduler grant." >&2
      return 1
    }
  rm -f -- "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANTED_POLICY}" \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_REMOVED_POLICY}" \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}" \
    "${PHASE5_RETRY_SCHEDULER_CONTROL_SUMMARY}" \
    "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}"

  issued_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" || return 1
  expires_at="$(date -u -d '+20 minutes' +'%Y-%m-%dT%H:%M:%SZ')" || return 1
  propagation_deadline_at="$(date -u -d '+10 minutes' +'%Y-%m-%dT%H:%M:%SZ')" || return 1
  condition_title="phase5-retry-${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}-${GITHUB_RUN_ATTEMPT:?GITHUB_RUN_ATTEMPT is required}-scheduler-activation"
  condition_description="JIT activation of the exact four Phase 5 producer schedules"
  condition_expression="request.time < timestamp(\"${expires_at}\")"
  jq -n --arg title "${condition_title}" --arg description "${condition_description}" \
    --arg expression "${condition_expression}" \
    '{title:$title,description:$description,expression:$expression}' \
    > "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" || return 1
  jq -n --arg project "${PROJECT_ID}" --arg location "${REGION}" \
    --arg member "${DEPLOYER_MEMBER}" --arg role "${PHASE5_RETRY_SCHEDULER_CONTROL_ROLE}" \
    --arg issued_at "${issued_at}" --arg expires_at "${expires_at}" \
    --arg propagation_deadline_at "${propagation_deadline_at}" \
    --slurpfile condition "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" \
    --argjson resources "$(printf '%s\n' "${PRODUCER_SCHEDULERS[@]}" | jq -R . | jq -s .)" \
    --argjson resource_names "$(printf '%s\n' "${PRODUCER_SCHEDULERS[@]}" |
      sed "s#^#projects/${PROJECT_ID}/locations/${REGION}/jobs/#" | jq -R . | jq -s .)" \
    '{schema_version:1,result:"scheduler_activation_authority_requested",
      project_id:$project,location:$location,member:$member,role:$role,
      issued_at:$issued_at,expires_at:$expires_at,
      propagation_deadline_at:$propagation_deadline_at,condition:$condition[0],
      condition_scope:"request_time_only",authorized_scheduler_short_names:$resources,
      exact_authorized_resource_names:$resource_names}' \
    > "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}" || return 1
  phase5_retry_verify_scheduler_condition_window || return 1

  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member "${DEPLOYER_MEMBER}" --role "${PHASE5_RETRY_SCHEDULER_CONTROL_ROLE}" \
    --condition-from-file="${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" \
    --quiet --format=none || return 1
  for attempt in $(seq 1 18); do
    if phase5_retry_scheduler_control_exact_present; then
      cp -- "${PHASE5_RETRY_SCHEDULER_CONTROL_POLICY}" \
        "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANTED_POLICY}" || return 1
      phase5_retry_verify_scheduler_condition_window || return 1
      return 0
    fi
    sleep 10
  done
  echo "Exact conditional Cloud Scheduler control did not become visible in project IAM." >&2
  return 1
}

phase5_retry_remove_scheduler_control() {
  local attempt status error_file
  for attempt in $(seq 1 18); do
    error_file="${RESOURCE_DIR}/scheduler-control-remove-attempt-${attempt}.stderr"
    if phase5_retry_scheduler_control_exact_binding_present; then
      gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
        --member "${DEPLOYER_MEMBER}" --role "${PHASE5_RETRY_SCHEDULER_CONTROL_ROLE}" \
        --condition-from-file="${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" \
        --quiet --format=none >/dev/null 2> "${error_file}" || true
    else
      status=$?
      [[ "${status}" == "1" || "${status}" == "2" ]] || return 1
    fi
    if phase5_retry_verify_scheduler_control_removed; then
      cp -- "${PHASE5_RETRY_SCHEDULER_CONTROL_POLICY}" \
        "${PHASE5_RETRY_SCHEDULER_CONTROL_REMOVED_POLICY}" || return 1
      return 0
    fi
    sleep 10
  done
  echo "Temporary Cloud Scheduler control could not be verified physically absent." >&2
  return 1
}

phase5_retry_private_web_invoker_present() {
  local policy_file="${RESOURCE_DIR}/private-web-invoker-policy.json"
  gcloud run services get-iam-policy "${WEB_SERVICE}" --project "${PROJECT_ID}" \
    --region "${REGION}" --format=json > "${policy_file}" || return 2
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    '[.bindings[]? | select(.role == "roles/run.invoker") | .members[]?] |
     any(. == $member)' "${policy_file}" >/dev/null
}

phase5_retry_grant_private_web_invoker() {
  local granted_policy="${RESOURCE_DIR}/private-web-invoker-granted-policy.json"
  gcloud run services add-iam-policy-binding "${WEB_SERVICE}" --project "${PROJECT_ID}" \
    --region "${REGION}" --member "${DEPLOYER_MEMBER}" --role roles/run.invoker \
    --quiet --format=none || return 1
  for attempt in $(seq 1 12); do
    if phase5_retry_private_web_invoker_present; then
      cp -- "${RESOURCE_DIR}/private-web-invoker-policy.json" "${granted_policy}" || return 1
      jq -e --arg member "${DEPLOYER_MEMBER}" \
        '[.bindings[]? | select(.role == "roles/run.invoker") | .members[]?] |
         any(. == $member)' "${granted_policy}" >/dev/null || return 1
      return 0
    fi
    sleep 2
  done
  echo "Temporary private web invocation authority did not become effective." >&2
  return 1
}

phase5_retry_remove_private_web_invoker() {
  local removed_policy="${RESOURCE_DIR}/private-web-invoker-removed-policy.json"
  gcloud run services remove-iam-policy-binding "${WEB_SERVICE}" --project "${PROJECT_ID}" \
    --region "${REGION}" --member "${DEPLOYER_MEMBER}" --role roles/run.invoker \
    --quiet >/dev/null 2>&1 || true
  for attempt in $(seq 1 12); do
    if phase5_retry_verify_private_web_invoker_removed; then
      cp -- "${RESOURCE_DIR}/private-web-invoker-policy.json" "${removed_policy}" || return 1
      jq -e --arg member "${DEPLOYER_MEMBER}" \
        '[.bindings[]? | select(.role == "roles/run.invoker") | .members[]?] |
         any(. == $member) | not' "${removed_policy}" >/dev/null || return 1
      return 0
    fi
    sleep 2
  done
  return 1
}

phase5_retry_verify_private_web_invoker_removed() {
  local status
  if phase5_retry_private_web_invoker_present; then
    echo "Temporary private web invocation authority is still present." >&2
    return 1
  else
    status=$?
  fi
  [[ "${status}" == "1" ]] || {
    echo "Temporary private web invocation-authority cleanup is unverified." >&2
    return 1
  }
}

phase5_retry_header_value() {
  local headers="$1" name="$2"
  awk -v target="${name}" '
    BEGIN { IGNORECASE=1 }
    {
      line=$0
      sub("\\r$", "", line)
      split(line, fields, ":")
      if (tolower(fields[1]) == tolower(target)) {
        sub("^[^:]*:[[:space:]]*", "", line)
        value=line
      }
    }
    END { print value }
  ' "${headers}"
}

phase5_retry_capture_private_id_token_claims() {
  local identity_token="$1"
  local output="${EVIDENCE_DIR}/private-web-id-token-claims.json"
  [[ -n "${identity_token}" ]] || {
    echo "The private web ID token is unavailable for claim verification." >&2
    return 1
  }
  PHASE5_RETRY_ID_TOKEN="${identity_token}" python - \
    "${PRIVATE_WEB_AUDIENCE}" "${DEPLOYER_SERVICE_ACCOUNT}" "${output}" <<'PY'
import base64
import binascii
import json
import os
import sys
import time
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


token = os.environ.pop("PHASE5_RETRY_ID_TOKEN", "")
expected_audience, expected_email, output_name = sys.argv[1:]
parts = token.split(".")
if len(parts) != 3:
    fail("The private web ID token is not a three-part JWT.")
try:
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
except (binascii.Error, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
    fail(f"The private web ID token payload is invalid: {exc}")
if not isinstance(claims, dict):
    fail("The private web ID token claims are not an object.")

issuer = claims.get("iss")
audience = claims.get("aud")
subject = claims.get("sub")
email = claims.get("email")
email_verified = claims.get("email_verified")
issued_at = claims.get("iat")
expires_at = claims.get("exp")
if issuer not in ("accounts.google.com", "https://accounts.google.com"):
    fail("The private web ID token issuer is not Google.")
if audience != expected_audience:
    fail("The private web ID token audience does not match the exact service URL.")
if email != expected_email or email_verified is not True:
    fail("The private web ID token is not the verified deployer service-account identity.")
if not isinstance(subject, str) or not subject.isdecimal():
    fail("The private web ID token subject is invalid.")
if (
    isinstance(issued_at, bool)
    or not isinstance(issued_at, int)
    or isinstance(expires_at, bool)
    or not isinstance(expires_at, int)
):
    fail("The private web ID token lifetime claims are invalid.")
now = int(time.time())
if issued_at > now + 60 or expires_at - now < 1800:
    fail("The private web ID token has insufficient verified lifetime remaining.")

evidence = {
    "schema_version": 1,
    "result": "private_web_id_token_claims_decoded_and_matched",
    "issuer": issuer,
    "audience": audience,
    "subject": subject,
    "email": email,
    "email_verified": True,
    "issued_at": issued_at,
    "expires_at": expires_at,
    "minimum_remaining_lifetime_seconds": 1800,
}
Path(output_name).write_text(
    json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
}

phase5_retry_verify_private_web_invocation_denied() {
  local identity_token="$1" url="$2" http_code="000" denied=false retryable=false
  local deadline attempts=0 delay=5 remaining sleep_for request_timeout attempted_at
  local started_utc finished_utc www_authenticate server iam_denial=false
  local headers="${EVIDENCE_DIR}/private-web-invoker-denial.headers"
  local body="${EVIDENCE_DIR}/private-web-invoker-denial.body"
  local timeline="${EVIDENCE_DIR}/private-web-invoker-denial-attempts.ndjson"
  [[ -n "${identity_token}" && "${url}" == "${PRIVATE_WEB_AUDIENCE}" ]] || {
    echo "The private web revocation probe lacks the exact token or audience." >&2
    return 1
  }
  : > "${timeline}" || return 1
  started_utc="$(date -u +'%Y-%m-%dT%H:%M:%S.%6NZ')"
  deadline=$((SECONDS + 600))
  while ((SECONDS < deadline)); do
    ((attempts += 1))
    remaining=$((deadline - SECONDS))
    ((remaining > 0)) || break
    request_timeout=30
    if ((request_timeout > remaining)); then
      request_timeout="${remaining}"
    fi
    http_code="$(curl --silent --show-error --connect-timeout 10 --max-time "${request_timeout}" \
      --header "Authorization: Bearer ${identity_token}" \
      --dump-header "${headers}" --output "${body}" --write-out '%{http_code}' \
      "${url}/data/ai-analyses.json")" || http_code="000"
    retryable=false
    iam_denial=false
    www_authenticate=""
    server=""
    case "${http_code}" in
      403)
        www_authenticate="$(phase5_retry_header_value "${headers}" WWW-Authenticate 2>/dev/null || true)"
        server="$(phase5_retry_header_value "${headers}" Server 2>/dev/null || true)"
        if [[ "${www_authenticate}" == *'Bearer error="insufficient_scope"'* &&
              "${server,,}" == *"google frontend"* ]]; then
          denied=true
          iam_denial=true
        fi
        ;;
      000|200|429|5??) retryable=true ;;
    esac
    attempted_at="$(date -u +'%Y-%m-%dT%H:%M:%S.%6NZ')"
    jq -cn --argjson attempt "${attempts}" --arg attempted_at "${attempted_at}" \
      --arg http_status "${http_code}" --arg retryable "${retryable}" \
      --arg iam_denial "${iam_denial}" \
      '{attempt:$attempt,attempted_at:$attempted_at,http_status:$http_status,
        retryable:($retryable == "true"),
        cloud_run_iam_denial_verified:($iam_denial == "true")}' \
      >> "${timeline}" || return 1
    [[ "${denied}" == "true" ]] && break
    [[ "${retryable}" == "true" ]] || break
    remaining=$((deadline - SECONDS))
    ((remaining > 0)) || break
    sleep_for="${delay}"
    if ((sleep_for > remaining)); then
      sleep_for="${remaining}"
    fi
    sleep "${sleep_for}"
    if ((delay < 30)); then
      delay=$((delay * 2))
      if ((delay > 30)); then
        delay=30
      fi
    fi
  done
  finished_utc="$(date -u +'%Y-%m-%dT%H:%M:%S.%6NZ')"
  jq -n \
    --arg started_at "${started_utc}" \
    --arg finished_at "${finished_utc}" \
    --arg final_http_status "${http_code}" \
    --arg denied "${denied}" \
    --argjson attempts "${attempts}" \
    '{schema_version:1,result:"private_web_invocation_revocation_checked",
      started_at:$started_at,finished_at:$finished_at,attempts:$attempts,
      final_http_status:$final_http_status,data_plane_invocation_denied:($denied == "true"),
      cloud_run_iam_denial_verified:($denied == "true"),
      authorization_relaxed:false,maximum_propagation_wait_seconds:600}' \
    > "${EVIDENCE_DIR}/private-web-invoker-revocation.json" || return 1
  [[ "${denied}" == "true" ]] || {
    echo "Private web invocation remained effective or became unverifiable after revocation (HTTP ${http_code})." >&2
    return 1
  }
}

phase5_retry_capture_private_ai_analyses() {
  local output="$1" expected_digest="$2" identity_token="${3:-}"
  local url http_code content_type served
  local deadline attempts=0 delay=5 remaining sleep_for request_timeout retryable attempted_at
  local started_utc finished_utc www_authenticate server iam_denial
  local headers="${EVIDENCE_DIR}/private-ai-analyses.headers"
  local timeline="${EVIDENCE_DIR}/private-ai-auth-attempts.ndjson"
  [[ "${expected_digest}" =~ ^[0-9a-f]{64}$ ]] || {
    echo "The private dashboard snapshot digest is malformed." >&2
    return 1
  }
  url="$(gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" \
    --region "${REGION}" --format='value(status.url)')" || return 1
  [[ "${url}" == https://* ]] || {
    echo "The private Runtime v2 web URL is invalid." >&2
    return 1
  }
  [[ "${url}" == "${PRIVATE_WEB_AUDIENCE}" ]] || {
    echo "The live private web URL differs from the ID-token audience." >&2
    return 1
  }
  [[ -n "${identity_token}" ]] || {
    echo "The short-lived private web ID token is unavailable." >&2
    return 1
  }
  if ! phase5_retry_capture_private_id_token_claims "${identity_token}"; then
    identity_token=""
    return 1
  fi

  # A newly added Cloud Run invoker binding can be visible in the IAM policy
  # before route authorization has propagated.  Retry only authorization-
  # propagation and transient responses inside a fixed ten-minute wall-clock
  # budget; a 401, redirect, or deterministic non-authentication 4xx fails
  # immediately.  Never relax the exact JSON and snapshot checks below.
  http_code="000"
  : > "${timeline}" || return 1
  started_utc="$(date -u +'%Y-%m-%dT%H:%M:%S.%6NZ')"
  deadline=$((SECONDS + 600))
  while ((SECONDS < deadline)); do
    ((attempts += 1))
    remaining=$((deadline - SECONDS))
    ((remaining > 0)) || break
    request_timeout=30
    if ((request_timeout > remaining)); then
      request_timeout="${remaining}"
    fi
    http_code="$(curl --silent --show-error --connect-timeout 10 --max-time "${request_timeout}" \
      --header "Authorization: Bearer ${identity_token}" \
      --dump-header "${headers}" --output "${output}" --write-out '%{http_code}' \
      "${url}/data/ai-analyses.json")" || http_code="000"
    retryable=false
    iam_denial=false
    www_authenticate=""
    server=""
    case "${http_code}" in
      200) ;;
      403)
        www_authenticate="$(phase5_retry_header_value "${headers}" WWW-Authenticate 2>/dev/null || true)"
        server="$(phase5_retry_header_value "${headers}" Server 2>/dev/null || true)"
        if [[ "${www_authenticate}" == *'Bearer error="insufficient_scope"'* &&
              "${server,,}" == *"google frontend"* ]]; then
          retryable=true
          iam_denial=true
        fi
        ;;
      000|429|5??) retryable=true ;;
    esac
    attempted_at="$(date -u +'%Y-%m-%dT%H:%M:%S.%6NZ')"
    jq -cn --argjson attempt "${attempts}" --arg attempted_at "${attempted_at}" \
      --arg http_status "${http_code}" --arg retryable "${retryable}" \
      --arg iam_denial "${iam_denial}" \
      '{attempt:$attempt,attempted_at:$attempted_at,http_status:$http_status,
        retryable:($retryable == "true"),
        cloud_run_iam_denial_verified:($iam_denial == "true")}' \
      >> "${timeline}" || return 1
    [[ "${http_code}" == "200" ]] && break
    [[ "${retryable}" == "true" ]] || break
    remaining=$((deadline - SECONDS))
    ((remaining > 0)) || break
    sleep_for="${delay}"
    if ((sleep_for > remaining)); then
      sleep_for="${remaining}"
    fi
    sleep "${sleep_for}"
    if ((delay < 30)); then
      delay=$((delay * 2))
      if ((delay > 30)); then
        delay=30
      fi
    fi
  done
  finished_utc="$(date -u +'%Y-%m-%dT%H:%M:%S.%6NZ')"
  jq -n \
    --arg started_at "${started_utc}" \
    --arg finished_at "${finished_utc}" \
    --arg final_http_status "${http_code}" \
    --argjson attempts "${attempts}" \
    '{schema_version:1,result:"private_web_authenticated_inventory_attempted",
      started_at:$started_at,finished_at:$finished_at,attempts:$attempts,
      final_http_status:$final_http_status,authorization_relaxed:false,
      maximum_propagation_wait_seconds:600}' \
    > "${EVIDENCE_DIR}/private-ai-auth-attempts.json" || return 1
  [[ "${http_code}" == "200" ]] || {
    echo "The authenticated private AI analysis inventory returned HTTP ${http_code}." >&2
    return 1
  }
  content_type="$(phase5_retry_header_value "${headers}" Content-Type)" || return 1
  [[ "${content_type,,}" == application/json* ]] || {
    echo "The private AI analysis inventory is not JSON." >&2
    return 1
  }
  served="$(phase5_retry_header_value "${headers}" X-PolitiTrack-Snapshot)" || return 1
  [[ "${served}" == "${expected_digest}" ]] || {
    echo "The private AI analysis inventory was not served from the pinned Runtime snapshot." >&2
    return 1
  }
  jq -e 'type == "array" and all(.[]; type == "object")' "${output}" >/dev/null || {
    echo "The private AI analysis inventory is malformed." >&2
    return 1
  }
  phase5_retry_remove_private_web_invoker || return 1
  phase5_retry_verify_private_web_invoker_removed || return 1
  phase5_retry_verify_private_web_invocation_denied "${identity_token}" "${url}" || return 1
  identity_token=""
}

phase5_retry_verify_public_web() {
  local expected_digest="$1" url ready=false
  local ready_code dashboard_code ready_type dashboard_type served
  local health_code health_server health_classification
  [[ "${expected_digest}" =~ ^[0-9a-f]{64}$ ]] || {
    echo "The expected public dashboard digest is malformed." >&2
    return 1
  }
  url="$(gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" \
    --region "${REGION}" --format='value(status.url)')" || return 1
  [[ "${url}" == https://* ]] || {
    echo "The Runtime v2 public URL is invalid." >&2
    return 1
  }
  printf '%s\n' "${url}" > "${EVIDENCE_DIR}/web-url.txt"

  for attempt in $(seq 1 30); do
    ready_code="$(curl --silent --show-error --location --connect-timeout 10 --max-time 30 \
      --dump-header "${EVIDENCE_DIR}/readyz.headers" \
      --output "${EVIDENCE_DIR}/readyz.json" --write-out '%{http_code}' \
      "${url}/readyz")" || ready_code="000"
    dashboard_code="$(curl --silent --show-error --location --connect-timeout 10 --max-time 30 \
      --dump-header "${EVIDENCE_DIR}/dashboard.headers" \
      --output "${EVIDENCE_DIR}/dashboard.html" --write-out '%{http_code}' \
      "${url}/")" || dashboard_code="000"
    ready_type="$(phase5_retry_header_value "${EVIDENCE_DIR}/readyz.headers" Content-Type 2>/dev/null || true)"
    dashboard_type="$(phase5_retry_header_value "${EVIDENCE_DIR}/dashboard.headers" Content-Type 2>/dev/null || true)"
    served="$(phase5_retry_header_value "${EVIDENCE_DIR}/dashboard.headers" X-PolitiTrack-Snapshot 2>/dev/null || true)"
    if [[ "${ready_code}" == "200" && "${ready_type,,}" == application/json* &&
          "${dashboard_code}" == "200" && "${dashboard_type,,}" == text/html* &&
          "${served}" == "${expected_digest}" ]] &&
       jq -e --arg digest "${expected_digest}" \
         '.status == "ready" and .dashboard == true and .snapshot_sha256 == $digest' \
         "${EVIDENCE_DIR}/readyz.json" >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 5
  done
  [[ "${ready}" == "true" ]] || {
    echo "The public Runtime route did not satisfy the /readyz JSON and dashboard HTML gates." >&2
    return 1
  }
  printf '%s\n' "${served}" > "${EVIDENCE_DIR}/served-dashboard-sha256.txt"

  # /healthz is deliberately diagnostic-only for this incident.  A Google
  # Frontend 404 is accepted as platform-routing evidence, never as application
  # health.  /api/healthz is not queried and cannot satisfy either health gate.
  health_code="$(curl --silent --show-error --location --connect-timeout 10 --max-time 30 \
    --dump-header "${EVIDENCE_DIR}/healthz.headers" \
    --output "${EVIDENCE_DIR}/healthz.body" --write-out '%{http_code}' \
    "${url}/healthz")" || health_code="000"
  [[ "${health_code}" =~ ^[0-9]{3}$ ]] || health_code="000"
  health_server="$(phase5_retry_header_value "${EVIDENCE_DIR}/healthz.headers" Server 2>/dev/null || true)"
  case "${health_code}" in
    404)
      if [[ "${health_server,,}" == *"google frontend"* || "${health_server,,}" == *gfe* ]]; then
        health_classification="gfe_404_platform_diagnostic_only"
      else
        health_classification="http_404_platform_diagnostic_only"
      fi
      ;;
    200)
      health_classification="supplemental_application_diagnostic_only"
      ;;
    000)
      health_classification="unavailable_platform_diagnostic_only"
      ;;
    *)
      health_classification="http_${health_code}_platform_diagnostic_only"
      ;;
  esac

  jq -n \
    --arg url "${url}" \
    --arg digest "${expected_digest}" \
    --arg health_code "${health_code}" \
    --arg health_classification "${health_classification}" \
    --arg health_server "${health_server}" \
    --arg ready_content_type "${ready_type}" \
    --arg dashboard_content_type "${dashboard_type}" \
    '{schema_version:1,result:"phase5_retry_public_route_verified",url:$url,
      expected_snapshot_sha256:$digest,
      healthz:{http_status:($health_code|tonumber),classification:$health_classification,
               server:$health_server,certification_gate:false},
      api_healthz:{queried:false,accepted_as_health:false},
      readyz:{http_status:200,content_type:$ready_content_type,json_verified:true,
              expected_snapshot_verified:true,certification_gate:true},
      dashboard:{http_status:200,content_type:$dashboard_content_type,html_verified:true,
                 snapshot_header_verified:true,certification_gate:true}}' \
    > "${EVIDENCE_DIR}/public-web-verification.json"
}

phase5_retry_append_observation() {
  local sequence="$1" job="$2" execution="$3" status_file="$4"
  jq -cn \
    --argjson sequence "${sequence}" \
    --arg job "${job}" \
    --arg execution "${execution}" \
    --slurpfile status "${status_file}" \
    '{cycle:1,sequence:$sequence,job:$job,cloud_run_execution:$execution,status:$status[0]}' \
    >> "${EVIDENCE_DIR}/observations.ndjson"
}

phase5_retry_file_sha256() {
  sha256sum "$1" | awk '{print $1}'
}

phase5_retry_capture_scheduler_snapshot() {
  local phase="$1" scheduler expected_state raw_file raw_sha spec_sha state
  local inventory_file="${RESOURCE_DIR}/scheduler-${phase}-inventory.json"
  local records_file="${RESOURCE_DIR}/scheduler-${phase}-records.ndjson"
  local summary_file="${RESOURCE_DIR}/scheduler-${phase}-summary.json"
  local expected_names
  [[ "${phase}" == "before" || "${phase}" == "after" ]] || return 1
  [[ "${#PHASE5_RETRY_ALL_SCHEDULERS[@]}" == "5" ]] || return 1
  [[ "${PHASE5_RETRY_ALL_SCHEDULERS[*]}" == \
     "polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard polititrack-vault-lifecycle" ]] || {
    echo "The complete scheduler inventory differs from the frozen five." >&2
    return 1
  }
  expected_names="$(printf '%s\n' "${PHASE5_RETRY_ALL_SCHEDULERS[@]}" |
    sed "s#^#projects/${PROJECT_ID}/locations/${REGION}/jobs/#" | jq -R . | jq -s 'sort')" || return 1

  gcloud scheduler jobs list --project "${PROJECT_ID}" --location "${REGION}" \
    --format=json > "${inventory_file}" || return 1
  jq -e --argjson expected "${expected_names}" \
    'type == "array" and length == 5 and
     ([.[].name] | unique | sort) == $expected' "${inventory_file}" >/dev/null || {
      echo "The live Cloud Scheduler inventory is not the exact frozen set of five." >&2
      return 1
    }

  : > "${records_file}" || return 1
  for scheduler in "${PHASE5_RETRY_ALL_SCHEDULERS[@]}"; do
    raw_file="${RESOURCE_DIR}/scheduler-${phase}-${scheduler}.json"
    gcloud scheduler jobs describe "${scheduler}" --project "${PROJECT_ID}" \
      --location "${REGION}" --format=json > "${raw_file}" || return 1
    state="$(jq -er '.state | select(type == "string")' "${raw_file}")" || return 1
    if [[ "${phase}" == "before" || "${scheduler}" == "${VAULT_SCHEDULER}" ]]; then
      expected_state=PAUSED
    else
      expected_state=ENABLED
    fi
    [[ "${state}" == "${expected_state}" ]] || {
      echo "${scheduler} is ${state}, expected ${expected_state} in the ${phase} snapshot." >&2
      return 1
    }
    jq -e --arg name "projects/${PROJECT_ID}/locations/${REGION}/jobs/${scheduler}" \
      '.name == $name' "${raw_file}" >/dev/null || {
        echo "The ${phase} scheduler receipt is not for ${scheduler}." >&2
        return 1
      }
    raw_sha="$(phase5_retry_file_sha256 "${raw_file}")" || return 1
    spec_sha="$(jq -cS \
      'del(.state,.status,.userUpdateTime,.lastAttemptTime,.scheduleTime)' \
      "${raw_file}" | sha256sum | awk '{print $1}')" || return 1
    jq -cn --arg name "${scheduler}" \
      --arg resource "projects/${PROJECT_ID}/locations/${REGION}/jobs/${scheduler}" \
      --arg state "${state}" --arg raw_sha "${raw_sha}" --arg spec_sha "${spec_sha}" \
      '{name:$name,resource_name:$resource,state:$state,
        raw_sha256:$raw_sha,canonical_spec_sha256:$spec_sha}' >> "${records_file}" || return 1
  done
  jq -s --arg phase "${phase}" --arg project "${PROJECT_ID}" --arg location "${REGION}" \
    '{schema_version:1,phase:$phase,project_id:$project,location:$location,schedulers:.}' \
    "${records_file}" > "${summary_file}" || return 1
  rm -f -- "${records_file}"
}

phase5_retry_compare_scheduler_snapshots() {
  local before="${RESOURCE_DIR}/scheduler-before-summary.json"
  local after="${RESOURCE_DIR}/scheduler-after-summary.json"
  local before_sha after_sha
  jq -e --slurpfile after "${after}" \
    '.phase == "before" and (.schedulers | length) == 5 and
     $after[0].phase == "after" and ($after[0].schedulers | length) == 5 and
     all(.schedulers[] as $before;
       any($after[0].schedulers[];
         .name == $before.name and .resource_name == $before.resource_name and
         .canonical_spec_sha256 == $before.canonical_spec_sha256 and
         (if .name == "polititrack-vault-lifecycle"
          then $before.state == "PAUSED" and .state == "PAUSED"
          else $before.state == "PAUSED" and .state == "ENABLED" end)))' \
    "${before}" >/dev/null || {
      echo "The scheduler transition changed a specification, omitted a scheduler, or altered the vault." >&2
      return 1
    }
  before_sha="$(phase5_retry_file_sha256 "${before}")" || return 1
  after_sha="$(phase5_retry_file_sha256 "${after}")" || return 1
  jq -n --arg project "${PROJECT_ID}" --arg location "${REGION}" \
    --arg before_sha "${before_sha}" --arg after_sha "${after_sha}" \
    --slurpfile before "${before}" --slurpfile after "${after}" \
    '{schema_version:1,result:"exact_four_producer_schedulers_enabled_vault_unchanged",
      project_id:$project,location:$location,
      authorized_transitions:[
        $before[0].schedulers[] as $b |
        select($b.name != "polititrack-vault-lifecycle") |
        ($after[0].schedulers[] | select(.name == $b.name)) as $a |
        {name:$b.name,before_state:$b.state,after_state:$a.state,
         before_spec_sha256:$b.canonical_spec_sha256,
         after_spec_sha256:$a.canonical_spec_sha256,
         spec_unchanged:($b.canonical_spec_sha256 == $a.canonical_spec_sha256)}],
      vault:($before[0].schedulers[] as $b |
        select($b.name == "polititrack-vault-lifecycle") |
        ($after[0].schedulers[] | select(.name == $b.name)) as $a |
        {name:$b.name,before_state:$b.state,after_state:$a.state,
         before_spec_sha256:$b.canonical_spec_sha256,
         after_spec_sha256:$a.canonical_spec_sha256,
         spec_unchanged:($b.canonical_spec_sha256 == $a.canonical_spec_sha256)}),
      before_summary_sha256:$before_sha,after_summary_sha256:$after_sha,
      before:$before[0],after:$after[0]}' > "${PHASE5_RETRY_SCHEDULER_TRANSITION}" || return 1
}

phase5_retry_record_scheduler_resume_attempt() {
  local scheduler="$1" attempt="$2" outcome="$3" evidence_file="$4" evidence_sha denial_error=""
  evidence_sha="$(phase5_retry_file_sha256 "${evidence_file}")" || return 1
  if [[ "${outcome}" == "iam_propagation_pending" ]]; then
    denial_error="$(<"${evidence_file}")" || return 1
  fi
  jq -cn --arg scheduler "${scheduler}" --argjson attempt "${attempt}" \
    --arg outcome "${outcome}" --arg observed_at "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --arg evidence_file "$(basename "${evidence_file}")" --arg evidence_sha "${evidence_sha}" \
    --arg denial_error "${denial_error}" \
    '{scheduler:$scheduler,attempt:$attempt,outcome:$outcome,observed_at:$observed_at,
      evidence_file:$evidence_file,evidence_sha256:$evidence_sha,
      denial_error:(if $outcome == "iam_propagation_pending" then $denial_error else null end)}' \
    >> "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}"
}

phase5_retry_resume_scheduler_with_propagation() {
  local scheduler="$1"
  local receipt="${RESOURCE_DIR}/scheduler-resume-${scheduler}.json"
  local expected_name="projects/${PROJECT_ID}/locations/${REGION}/jobs/${scheduler}"
  local error_file attempt=0 deadline now deadline_at remaining command_timeout
  [[ "${scheduler}" == "${PRODUCER_SCHEDULERS[0]}" ]] || {
    echo "Only the first exact producer scheduler may probe IAM propagation." >&2
    return 1
  }
  deadline_at="$(jq -er '.propagation_deadline_at' "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}")" || return 1
  deadline="$(date -u -d "${deadline_at}" +%s)" || return 1
  rm -f -- "${receipt}"

  while (( attempt < 60 )); do
    now="$(date +%s)" || return 1
    (( now < deadline )) || {
      echo "Temporary Cloud Scheduler control did not propagate within 600 seconds." >&2
      return 1
    }
    remaining=$(( deadline - now ))
    command_timeout=30
    (( remaining >= command_timeout )) || command_timeout="${remaining}"
    (( command_timeout > 0 )) || return 1
    attempt=$(( attempt + 1 ))
    error_file="${RESOURCE_DIR}/scheduler-resume-${scheduler}-attempt-${attempt}.stderr"
    : > "${error_file}" || return 1
    phase5_retry_verify_scheduler_condition_window || return 1
    if timeout "${command_timeout}s" gcloud scheduler jobs resume "${scheduler}" --project "${PROJECT_ID}" \
      --location "${REGION}" --quiet --format=json > "${receipt}" 2> "${error_file}"; then
      jq -e --arg name "${expected_name}" \
        '.name == $name and .state == "ENABLED"' "${receipt}" >/dev/null || {
          echo "Cloud Scheduler returned an invalid resume receipt for ${scheduler}." >&2
          return 1
        }
      phase5_retry_record_scheduler_resume_attempt \
        "${scheduler}" "${attempt}" resumed "${receipt}" || return 1
      return 0
    fi
    if ! grep -Fq 'PERMISSION_DENIED' "${error_file}" ||
       ! grep -Fq 'cloudscheduler.jobs.enable' "${error_file}" ||
       ! grep -Fq "${expected_name}" "${error_file}"; then
      cat "${error_file}" >&2
      return 1
    fi
    phase5_retry_record_scheduler_resume_attempt \
      "${scheduler}" "${attempt}" iam_propagation_pending "${error_file}" || return 1
    now="$(date +%s)" || return 1
    if (( attempt >= 60 || now + 10 >= deadline )); then
      cat "${error_file}" >&2
      echo "Temporary Cloud Scheduler control did not propagate within 600 seconds." >&2
      return 1
    fi
    sleep 10
  done
  echo "Temporary Cloud Scheduler control exhausted its bounded propagation probe." >&2
  return 1
}

phase5_retry_resume_scheduler_once() {
  local scheduler="$1" receipt expected_name error_file
  receipt="${RESOURCE_DIR}/scheduler-resume-${scheduler}.json"
  expected_name="projects/${PROJECT_ID}/locations/${REGION}/jobs/${scheduler}"
  error_file="${RESOURCE_DIR}/scheduler-resume-${scheduler}-attempt-1.stderr"
  rm -f -- "${receipt}" "${error_file}"
  phase5_retry_verify_scheduler_condition_window || return 1
  if ! timeout 30s gcloud scheduler jobs resume "${scheduler}" --project "${PROJECT_ID}" \
    --location "${REGION}" --quiet --format=json > "${receipt}" 2> "${error_file}"; then
    cat "${error_file}" >&2
    return 1
  fi
  jq -e --arg name "${expected_name}" \
    '.name == $name and .state == "ENABLED"' "${receipt}" >/dev/null || {
      echo "Cloud Scheduler returned an invalid one-shot resume receipt for ${scheduler}." >&2
      return 1
    }
  phase5_retry_record_scheduler_resume_attempt "${scheduler}" 1 resumed "${receipt}"
}

phase5_retry_enable_exact_producer_schedulers_last() {
  local scheduler
  [[ "${#PRODUCER_SCHEDULERS[@]}" == "4" ]] || {
    echo "The retry may enable exactly four producer schedulers." >&2
    return 1
  }
  [[ "${PRODUCER_SCHEDULERS[*]}" == \
     "polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard" ]] || {
    echo "The producer scheduler inventory differs from the authorized four." >&2
    return 1
  }
  phase5_retry_scheduler_control_exact_present || {
    echo "Exact conditional Cloud Scheduler control is absent before final activation." >&2
    return 1
  }
  : > "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}" || return 1
  phase5_retry_resume_scheduler_with_propagation "${PRODUCER_SCHEDULERS[0]}" || return 1
  for scheduler in "${PRODUCER_SCHEDULERS[@]:1}"; do
    phase5_retry_resume_scheduler_once "${scheduler}" || return 1
  done
  verify_producer_scheduler_state ENABLED || return 1
  touch "${EVIDENCE_DIR}/producer-schedulers-enabled-last"
}

phase5_retry_finalize_scheduler_activation_evidence() {
  local permanent_role_sha before_policy_sha granted_policy_sha removed_policy_sha condition_sha
  local grant_sha attempts_sha transition_sha
  phase5_retry_verify_scheduler_control_removed || return 1
  phase5_retry_verify_role_viewer_removed || return 1
  phase5_retry_validate_permanent_control_role_receipt || return 1
  phase5_retry_compare_scheduler_snapshots || return 1
  jq -e \
    'length >= 4 and
     ([.[] | select(.outcome == "resumed") | .scheduler] | sort) ==
       (["polititrack-legislative","polititrack-executive","polititrack-ai","polititrack-dashboard"] | sort) and
     all(.[] | select(.outcome == "iam_propagation_pending");
       .scheduler == "polititrack-legislative") and
     ([.[] | select(.scheduler != "polititrack-legislative") | .attempt] | all(. == 1))' \
    <(jq -s '.' "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}") >/dev/null || {
      echo "Scheduler activation attempts do not prove one bounded propagation probe and three one-shot resumes." >&2
      return 1
    }
  permanent_role_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_PERMANENT_CONTROL_ROLE_RECEIPT}")" || return 1
  before_policy_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_SCHEDULER_CONTROL_BEFORE_POLICY}")" || return 1
  granted_policy_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANTED_POLICY}")" || return 1
  removed_policy_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_SCHEDULER_CONTROL_REMOVED_POLICY}")" || return 1
  condition_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}")" || return 1
  grant_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}")" || return 1
  attempts_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}")" || return 1
  transition_sha="$(phase5_retry_file_sha256 "${PHASE5_RETRY_SCHEDULER_TRANSITION}")" || return 1
  jq -n --slurpfile grant "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}" \
    --arg permanent_role_sha "${permanent_role_sha}" \
    --arg before_policy_sha "${before_policy_sha}" --arg granted_policy_sha "${granted_policy_sha}" \
    --arg removed_policy_sha "${removed_policy_sha}" --arg condition_sha "${condition_sha}" \
    --arg grant_sha "${grant_sha}" --arg attempts_sha "${attempts_sha}" \
    --arg transition_sha "${transition_sha}" \
    --argjson attempts "$(jq -s '.' "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}")" \
    --argjson receipts "$(for scheduler in "${PRODUCER_SCHEDULERS[@]}"; do
      receipt="${RESOURCE_DIR}/scheduler-resume-${scheduler}.json"
      jq -cn --arg scheduler "${scheduler}" --arg sha "$(phase5_retry_file_sha256 "${receipt}")" \
        '{scheduler:$scheduler,sha256:$sha}'
    done | jq -s '.')" \
    '{schema_version:1,result:"jit_scheduler_activation_authority_removed",
      grant:$grant[0],absent_before_grant:true,grant_observed:true,
      physically_absent_after_removal:true,
      propagation_probe_scheduler:"polititrack-legislative",
      propagation_deadline_seconds:600,attempts:$attempts,resume_attempts:$attempts,
      resume_receipts:$receipts,
      scheduler_transition_result:"exact_four_producer_schedulers_enabled_vault_unchanged",
      evidence_sha256:{permanent_control_role:$permanent_role_sha,
        before_policy:$before_policy_sha,granted_policy:$granted_policy_sha,
        removed_policy:$removed_policy_sha,condition:$condition_sha,grant_request:$grant_sha,
        resume_attempts:$attempts_sha,scheduler_transition:$transition_sha}}' \
    > "${PHASE5_RETRY_SCHEDULER_CONTROL_SUMMARY}" || return 1
}

phase5_retry_dispatch_legacy_recovery_once() {
  local receipt="${EVIDENCE_DIR}/legacy-recovery-dispatch.json"
  if [[ -f "${receipt}" ]]; then
    jq -e \
      '.result == "legacy_recovery_runs_succeeded" and
       (.workflows | length) == 2 and
       all(.workflows[]; .result == "legacy_recovery_run_succeeded")' \
      "${receipt}" >/dev/null
    return $?
  fi
  # The shared tracked helper writes durable per-workflow pending/accepted state
  # before dispatch.  An ambiguous dispatch is never attempted a second time.
  dispatch_legacy_recovery_tracked
}

phase5_retry_rollback() {
  local schedulers_paused=false web_private=false runtime_shadow=false legacy_restored=false
  local recovery_required=false recovery_complete=false execution_authority_removed=false
  local service_account_user_removed=false private_web_invoker_removed=false
  local scheduler_control_removed=false role_viewer_removed=false cloud_sql_private=false
  local vault_scheduler_paused=false legacy_route_kind=invalid
  local legacy_maintenance_fence_preserved=false
  local scheduler_removed_policy_sha256="" scheduler_condition_sha256=""
  local role_viewer_removed_policy_sha256="" role_viewer_condition_sha256=""
  set +e

  [[ -f "${EVIDENCE_DIR}/live-mutation-started" ]] || {
    echo "No live mutation was started; rollback is intentionally a no-op." >&2
    set -e
    return 0
  }

  if ! legacy_route_kind="$(phase5_retry_observed_legacy_route_kind)"; then
    legacy_route_kind=invalid
  fi

  pause_producer_schedulers && verify_producer_scheduler_state PAUSED && schedulers_paused=true
  make_web_private
  verify_web_private && web_private=true
  phase5_retry_remove_private_web_invoker
  phase5_retry_remove_scheduler_control
  phase5_retry_remove_role_viewer
  phase5_retry_restore_preflight_logging_receipt_if_safe || true
  remove_execution_authority
  collect_service_accounts
  remove_service_account_user

  if [[ -f "${EVIDENCE_DIR}/route-touched" ]]; then
    configure_runtime_best_effort shadow && verify_runtime_configuration shadow && runtime_shadow=true
  else
    verify_runtime_configuration shadow && runtime_shadow=true
  fi

  # Never reopen a legacy writer unless every Runtime writer surface is already
  # proven inert.  On any pause/mode/privacy failure, preserve the all-disabled
  # maintenance fence and report rollback incomplete instead of risking two
  # production writer families.
  if [[ "${legacy_route_kind}" == "historic_active" &&
        "${schedulers_paused}" == "true" &&
        "${runtime_shadow}" == "true" &&
        "${web_private}" == "true" ]]; then
    if restore_legacy_workflows_observed; then
      legacy_restored=true
      if [[ -f "${EVIDENCE_DIR}/route-touched" ]]; then
        recovery_required=true
        if phase5_retry_dispatch_legacy_recovery_once; then
          recovery_complete=true
        fi
      else
        recovery_complete=true
      fi
    else
      disable_legacy_workflows &&
        verify_legacy_workflows_state disabled_manually &&
        legacy_maintenance_fence_preserved=true
    fi
  else
    disable_legacy_workflows &&
      verify_legacy_workflows_state disabled_manually &&
      legacy_maintenance_fence_preserved=true
  fi

  remove_execution_authority
  verify_execution_authority_removed && execution_authority_removed=true
  collect_service_accounts
  remove_service_account_user
  verify_service_account_user_removed && service_account_user_removed=true
  phase5_retry_remove_private_web_invoker
  phase5_retry_verify_private_web_invoker_removed && private_web_invoker_removed=true
  phase5_retry_remove_scheduler_control
  if phase5_retry_verify_scheduler_control_removed; then
    scheduler_control_removed=true
    if [[ -s "${PHASE5_RETRY_SCHEDULER_CONTROL_REMOVED_POLICY}" ]]; then
      scheduler_removed_policy_sha256="$(phase5_retry_file_sha256 \
        "${PHASE5_RETRY_SCHEDULER_CONTROL_REMOVED_POLICY}" 2>/dev/null || true)"
    fi
    if [[ -s "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" ]]; then
      scheduler_condition_sha256="$(phase5_retry_file_sha256 \
        "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" 2>/dev/null || true)"
    fi
    [[ "${scheduler_removed_policy_sha256}" =~ ^[0-9a-f]{64}$ ]] || scheduler_control_removed=false
  fi
  phase5_retry_remove_role_viewer
  if phase5_retry_verify_role_viewer_removed; then
    role_viewer_removed=true
    if [[ -s "${PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}" ]]; then
      role_viewer_removed_policy_sha256="$(phase5_retry_file_sha256 \
        "${PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}" 2>/dev/null || true)"
    fi
    if [[ -s "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" ]]; then
      role_viewer_condition_sha256="$(phase5_retry_file_sha256 \
        "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" 2>/dev/null || true)"
    fi
    [[ "${role_viewer_removed_policy_sha256}" =~ ^[0-9a-f]{64}$ ]] || role_viewer_removed=false
  fi
  verify_cloud_sql_private && cloud_sql_private=true
  verify_vault_scheduler_paused && vault_scheduler_paused=true

  jq -n \
    --arg schedulers_paused "${schedulers_paused}" \
    --arg web_private "${web_private}" \
    --arg runtime_shadow "${runtime_shadow}" \
    --arg legacy_restored "${legacy_restored}" \
    --arg recovery_required "${recovery_required}" \
    --arg recovery_complete "${recovery_complete}" \
    --arg legacy_maintenance_fence_preserved "${legacy_maintenance_fence_preserved}" \
    --arg execution_authority_removed "${execution_authority_removed}" \
    --arg service_account_user_removed "${service_account_user_removed}" \
    --arg private_web_invoker_removed "${private_web_invoker_removed}" \
    --arg scheduler_control_removed "${scheduler_control_removed}" \
    --arg scheduler_control_role "${PHASE5_RETRY_SCHEDULER_CONTROL_ROLE}" \
    --arg scheduler_control_member "${DEPLOYER_MEMBER}" \
    --arg scheduler_removed_policy_sha256 "${scheduler_removed_policy_sha256}" \
    --arg scheduler_condition_sha256 "${scheduler_condition_sha256}" \
    --arg role_viewer_removed "${role_viewer_removed}" \
    --arg role_viewer_role "${PHASE5_RETRY_ROLE_VIEWER_ROLE}" \
    --arg role_viewer_removed_policy_sha256 "${role_viewer_removed_policy_sha256}" \
    --arg role_viewer_condition_sha256 "${role_viewer_condition_sha256}" \
    --arg cloud_sql_private "${cloud_sql_private}" \
    --arg vault_scheduler_paused "${vault_scheduler_paused}" \
    --arg legacy_route_kind "${legacy_route_kind}" \
    '{schema_version:1,result:"phase5_failed_promotion_retry_rolled_back",
      runtime_schedulers_paused:($schedulers_paused == "true"),
      web_public:($web_private != "true"),
      runtime_mode:(if $runtime_shadow == "true" then "shadow" else "unverified" end),
      observed_legacy_route_kind:$legacy_route_kind,
      legacy_route_restored:($legacy_restored == "true"),
      legacy_maintenance_fence_preserved:($legacy_maintenance_fence_preserved == "true"),
      legacy_recovery_required:($recovery_required == "true"),
      legacy_recovery_action_complete:($recovery_complete == "true"),
      temporary_execution_authority_removed:($execution_authority_removed == "true"),
      temporary_service_account_user_removed:($service_account_user_removed == "true"),
      temporary_private_web_invoker_removed:($private_web_invoker_removed == "true"),
      temporary_scheduler_activation_authority_removed:($scheduler_control_removed == "true"),
      scheduler_activation_authority_cleanup:{role:$scheduler_control_role,
        member:$scheduler_control_member,physically_absent:($scheduler_control_removed == "true"),
        removed_policy_sha256:($scheduler_removed_policy_sha256 | select(length > 0) // null),
        condition_sha256:($scheduler_condition_sha256 | select(length > 0) // null)},
      temporary_role_viewer_authority_removed:($role_viewer_removed == "true"),
      role_viewer_authority_cleanup:{role:$role_viewer_role,
        member:$scheduler_control_member,physically_absent:($role_viewer_removed == "true"),
        removed_policy_sha256:($role_viewer_removed_policy_sha256 | select(length > 0) // null),
        condition_sha256:($role_viewer_condition_sha256 | select(length > 0) // null)},
      cloud_sql_private_only:($cloud_sql_private == "true"),
      vault_scheduler_state:(if $vault_scheduler_paused == "true" then "PAUSED" else "unverified" end)}' \
    > "${EVIDENCE_DIR}/retry-rollback.json"

  if [[ "${schedulers_paused}" == "true" && "${web_private}" == "true" &&
        "${runtime_shadow}" == "true" && "${legacy_restored}" == "true" &&
        "${recovery_complete}" == "true" &&
        "${execution_authority_removed}" == "true" &&
        "${service_account_user_removed}" == "true" &&
        "${private_web_invoker_removed}" == "true" &&
        "${scheduler_control_removed}" == "true" &&
        "${role_viewer_removed}" == "true" &&
        "${cloud_sql_private}" == "true" &&
        "${vault_scheduler_paused}" == "true" ]]; then
    touch "${EVIDENCE_DIR}/retry-rollback-complete"
    set -e
    return 0
  fi
  echo "The failed Phase 5 retry did not reach a fully verified rollback state." >&2
  set -e
  return 1
}
