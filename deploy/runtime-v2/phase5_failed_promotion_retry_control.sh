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
PHASE5_RETRY_PHASE4_RUN_ID="33979432233"
PHASE5_RETRY_LEGACY_AI_RUN_ID="33980946687"
PHASE5_RETRY_DASHBOARD_RUN_ID="33974683885"
PHASE5_RETRY_RECOVERY_RUN_IDS=(33981311523 33981312757)
PHASE5_RETRY_FROZEN_SUCCESSOR_RUN_IDS=(33987160591 33987130349)

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
    --arg legacy_ai_run "${PHASE5_RETRY_LEGACY_AI_RUN_ID}" \
    --arg recovery_legislative "${PHASE5_RETRY_RECOVERY_RUN_IDS[0]}" \
    --arg recovery_executive "${PHASE5_RETRY_RECOVERY_RUN_IDS[1]}" \
    --argjson successor_legislative "${PHASE5_RETRY_FROZEN_SUCCESSOR_RUN_IDS[0]}" \
    --argjson successor_executive "${PHASE5_RETRY_FROZEN_SUCCESSOR_RUN_IDS[1]}" \
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
    'legislative|.frozen_legacy_successors[0]|.frozen_legacy_successors[0].artifact|legislative_trade_tracker_v2.yml'
    'executive|.frozen_legacy_successors[1]|.frozen_legacy_successors[1].artifact|executive_trade_tracker.yml'
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

phase5_retry_verify_current_base_authority_absent() {
  local job policy_file project_policy
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
  gcloud projects get-iam-policy "${PROJECT_ID}" --format=json \
    > "${project_policy}" || return 1
  jq -e --arg member "${DEPLOYER_MEMBER}" \
    'type == "object" and
     ([.bindings[]? | select(.role == "roles/logging.admin") | .members[]?] |
      any(. == $member) | not)' "${project_policy}" >/dev/null || {
      echo "Temporary logging.admin authority is already present." >&2
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
  verify_service_account_user_removed || return 1
  phase5_retry_verify_private_web_invoker_removed || return 1
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

phase5_retry_enable_exact_producer_schedulers_last() {
  [[ "${#PRODUCER_SCHEDULERS[@]}" == "4" ]] || {
    echo "The retry may enable exactly four producer schedulers." >&2
    return 1
  }
  [[ "${PRODUCER_SCHEDULERS[*]}" == \
     "polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard" ]] || {
    echo "The producer scheduler inventory differs from the authorized four." >&2
    return 1
  }
  resume_producer_schedulers || return 1
  verify_producer_scheduler_state ENABLED || return 1
  touch "${EVIDENCE_DIR}/producer-schedulers-enabled-last"
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
  local cloud_sql_private=false vault_scheduler_paused=false legacy_route_kind=invalid
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
  phase5_retry_restore_preflight_logging_receipt_if_safe || true
  remove_execution_authority
  collect_service_accounts
  remove_service_account_user

  if [[ -f "${EVIDENCE_DIR}/route-touched" ]]; then
    configure_runtime_best_effort shadow && verify_runtime_configuration shadow && runtime_shadow=true
    if [[ "${legacy_route_kind}" == "historic_active" ]] &&
       restore_legacy_workflows_observed; then
      legacy_restored=true
      recovery_required=true
      if phase5_retry_dispatch_legacy_recovery_once; then
        recovery_complete=true
      fi
    fi
  else
    verify_runtime_configuration shadow && runtime_shadow=true
    if [[ "${legacy_route_kind}" == "historic_active" ]] &&
       restore_legacy_workflows_observed; then
      legacy_restored=true
      recovery_complete=true
    fi
  fi

  remove_execution_authority
  verify_execution_authority_removed && execution_authority_removed=true
  collect_service_accounts
  remove_service_account_user
  verify_service_account_user_removed && service_account_user_removed=true
  phase5_retry_remove_private_web_invoker
  phase5_retry_verify_private_web_invoker_removed && private_web_invoker_removed=true
  verify_cloud_sql_private && cloud_sql_private=true
  verify_vault_scheduler_paused && vault_scheduler_paused=true

  jq -n \
    --arg schedulers_paused "${schedulers_paused}" \
    --arg web_private "${web_private}" \
    --arg runtime_shadow "${runtime_shadow}" \
    --arg legacy_restored "${legacy_restored}" \
    --arg recovery_required "${recovery_required}" \
    --arg recovery_complete "${recovery_complete}" \
    --arg execution_authority_removed "${execution_authority_removed}" \
    --arg service_account_user_removed "${service_account_user_removed}" \
    --arg private_web_invoker_removed "${private_web_invoker_removed}" \
    --arg cloud_sql_private "${cloud_sql_private}" \
    --arg vault_scheduler_paused "${vault_scheduler_paused}" \
    --arg legacy_route_kind "${legacy_route_kind}" \
    '{schema_version:1,result:"phase5_failed_promotion_retry_rolled_back",
      runtime_schedulers_paused:($schedulers_paused == "true"),
      web_public:($web_private != "true"),
      runtime_mode:(if $runtime_shadow == "true" then "shadow" else "unverified" end),
      observed_legacy_route_kind:$legacy_route_kind,
      legacy_route_restored:($legacy_restored == "true"),
      legacy_recovery_required:($recovery_required == "true"),
      legacy_recovery_action_complete:($recovery_complete == "true"),
      temporary_execution_authority_removed:($execution_authority_removed == "true"),
      temporary_service_account_user_removed:($service_account_user_removed == "true"),
      temporary_private_web_invoker_removed:($private_web_invoker_removed == "true"),
      cloud_sql_private_only:($cloud_sql_private == "true"),
      vault_scheduler_state:(if $vault_scheduler_paused == "true" then "PAUSED" else "unverified" end)}' \
    > "${EVIDENCE_DIR}/retry-rollback.json"

  if [[ "${schedulers_paused}" == "true" && "${web_private}" == "true" &&
        "${runtime_shadow}" == "true" && "${legacy_restored}" == "true" &&
        "${recovery_complete}" == "true" &&
        "${execution_authority_removed}" == "true" &&
        "${service_account_user_removed}" == "true" &&
        "${private_web_invoker_removed}" == "true" &&
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
