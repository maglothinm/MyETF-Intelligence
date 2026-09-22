/* Evidence-first presentation only: never changes profiles, scores or history. */
window.PTEdgeEvidence = (() => {
  "use strict";
  const count = value => Number.isSafeInteger(value) && value >= 0 ? value : null;
  const sample = p => count(p.sample_count ?? p.observation_count);
  const unavailable = new Set(["insufficient_data", "unavailable", "error", "disabled", "neutral"]);
  const assessable = p => sample(p) !== null && sample(p) > 0 &&
    (p.minimum_sample_met === true || p.minimum_sample_met !== false && sample(p) >= 3) &&
    !unavailable.has(p.status) && typeof p.edge_score === "number" && Number.isFinite(p.edge_score);
  const valid = edge => edge && edge.profile_inventory_available !== false && Array.isArray(edge.investors) &&
    edge.investors.every(p => p && typeof p === "object" && !Array.isArray(p));
  const number = value => count(value) === null ? "Unavailable" : value.toLocaleString();
  function reason(p, index, edge) {
    const n = sample(p);
    let text = n === null ? "Completed-observation count unavailable." :
      `Building history — insufficient completed observations (n = ${number(n)}).`;
    if (p.status === "error") text = "Profile assessment failed; retained history is preserved.";
    else if (p.status === "disabled") text = "Profile assessment is disabled.";
    else if (["unavailable", "neutral"].includes(p.status)) text = "Profile assessment is unavailable; no measured neutral result is implied.";
    else if (n > 0 && (p.minimum_sample_met === true || p.minimum_sample_met !== false && n >= 3) && p.status !== "insufficient_data") text = "Calculated Edge is unavailable despite recorded observations.";
    const progress = edge?.backfill_progress;
    const reasons = window.PTBackfill?.valid(progress) && Array.isArray(progress.details) ?
      [...new Set(progress.details.filter(r => r?.profile_index === index && r.category !== "completed" && typeof r.reason === "string").map(r => r.reason))] : [];
    if (reasons.length) return `${text} Recorded pending reasons: ${reasons.slice(0, 3).join(" ")}${reasons.length > 3 ? " More reasons in Processing details." : ""}`;
    return `${text} ${count(p.backfill_pending_trade_count) === 0 ? "No pending observations are reported for this profile." : "Specific pending-work reason is unavailable in this publication."}`;
  }
  function summary(edge) {
    if (!valid(edge)) return {ready: [], building: [], heading: "Investor Edge data unavailable", assessment: "Profile inventory could not be verified. No zero-count or completeness assumption is made.", pending: "Pending observations unavailable.", progress: "Last actual advancement unavailable."};
    const rows = edge.investors.map((p, index) => ({p, index}));
    const ready = rows.filter(({p}) => assessable(p)), building = rows.filter(({p}) => !assessable(p));
    let assessment = !rows.length ? "No investor profiles are currently published." : !ready.length ?
      "No assessable profiles yet. Building-history records are retained below, but cannot support an Investor Edge assessment." :
      `${number(ready.length)} assessable profiles. Zero and negative measured results are retained; assessment eligibility does not imply a favorable result.`;
    const complete = count(edge.completed_profile_count);
    assessment += complete === 0 ? " No fully complete profiles yet." : complete === null ?
      " Fully complete profile count unavailable." : ` Fully complete profiles: ${number(complete)}.`;
    const pending = count(edge.backfill_pending_observation_count);
    const pendingText = pending === null ? "Pending observations unavailable." : pending === 0 ?
      "No pending observations in retained history. This does not establish complete filing coverage." : `${number(pending)} pending observations in retained history.`;
    const b = edge.backfill_progress, stamp = window.PTBackfill?.valid(b) ? b.last_advancement_at : null;
    const progress = `Last actual advancement across the published population: ${typeof stamp === "string" && Number.isFinite(Date.parse(stamp)) ? new Date(stamp).toLocaleString() : "Unavailable"}. Individual profile progress times are not recorded; maintenance dates are not substituted.`;
    return {ready, building, heading: `${number(ready.length)} assessable profiles`, assessment, pending: pendingText, progress};
  }
  function renderSummary(edge) {
    const s = summary(edge);
    for (const [id, text] of [["edge-assessment-summary", s.assessment], ["edge-pending-summary", s.pending], ["edge-building-progress", s.progress]]) {
      const node = document.getElementById(id); if (node) node.textContent = text;
    }
    const heading = document.getElementById("edge-building-summary");
    if (heading) heading.textContent = valid(edge) ? `Building history — ${number(s.building.length)} profiles not yet assessable` : "Building history — inventory unavailable";
    return s;
  }
  function attachStandalone() {
    const data = document.getElementById("edge-evidence-data");
    if (!data) return;
    let edge; try { edge = JSON.parse(data.textContent); } catch { edge = null; }
    renderSummary(edge);
    for (const node of document.querySelectorAll("[data-edge-reason]")) {
      const index = Number(node.dataset.edgeReason), p = edge?.investors?.[index];
      node.textContent = p ? reason(p, index, edge) : "Profile reason unavailable.";
    }
  }
  return {count, sample, assessable, valid, reason, summary, renderSummary, attachStandalone};
})();
window.PTEdgeEvidence.renderRoot = function(edge) {
  const E = window.PTEdgeEvidence, {el, esc, number, fact} = PT;
  if (!E.valid(edge)) edge = null;
  const metadata = edge || {}, profiles = edge?.investors || [], s = E.renderSummary(edge);
  const stats = [["published_profile_count", "Profiles"], ["completed_profile_count", "Complete"], ["building_profile_count", "Building"], ["historical_transaction_count", "Historical trades"], ["backfill_processed_this_run", "Processed this run"], ["backfill_pending_observation_count", "Pending observations"]];
  el("edge-bootstrap-status").textContent = "Historical backfill status unavailable";
  el("edge-bootstrap-status").className = "status unknown";
  el("edge-bootstrap-counts").innerHTML = stats.map(([key, label]) => fact(label, number(key === "published_profile_count" && E.count(metadata[key]) === null && edge ? profiles.length : E.count(metadata[key])))).join("");
  el("edge-bootstrap-coverage").textContent = `Eligible purchases: ${number(E.count(metadata.eligible_purchase_count))} · Eligible filer / owner identities: ${number(E.count(metadata.unique_investor_identity_count))} · Legislative trades: ${number(E.count(metadata.branch_transaction_counts?.legislative))} · Executive trades: ${number(E.count(metadata.branch_transaction_counts?.executive))}`;
  el("edge-bootstrap-budget").textContent = `Observation budget per run: ${number(E.count(metadata.backfill_limit_per_run))} · Market requests this run: ${number(E.count(metadata.network_requests_this_run))}. Complete profiles meet the sample minimum and have no pending observations. Retained history does not establish complete filing coverage.`;
  if (window.PTBackfill) PTBackfill.render(el("edge-backfill-detail"), metadata.backfill_progress);
  el("edge-history-label").textContent = s.heading;
  el("edge-history-note").textContent = edge ? "Profiles meeting the existing sample minimum with a calculated Edge. Pending horizons and confidence remain visible. All retained profiles and trade details remain available below." : "Profile inventory could not refresh. Missing results are not zero performance.";
  el("edge-profile-body").innerHTML = s.ready.length ? s.ready.map(({p}) => {
    const pending = E.count(p.backfill_pending_trade_count);
    const state = pending === null ? "Assessment available; pending count unavailable" : pending > 0 ? "Assessment available; historical work pending" : "Sufficient completed observations";
    return `<tr><td><strong>${esc(p.filer || "Unknown filer")}</strong><small>${esc(p.owner || "Unknown owner")}</small></td><td>${esc(number(E.sample(p)))}</td><td>${esc(state)}</td><td>${esc(number(pending))}</td><td>${esc(number(p.edge_score))}</td><td>${esc(p.confidence_label || "Unavailable")}</td></tr>`;
  }).join("") : `<tr><td colspan="6" class="empty">${edge ? "No assessable profiles yet. Expand Building history for retained profiles and reasons." : "Profile inventory unavailable."}</td></tr>`;
  el("edge-building-body").innerHTML = s.building.length ? s.building.map(({p, index}) =>
    `<tr><td><strong>${esc(p.filer || "Unknown filer")}</strong><small>${esc(p.owner || "Unknown owner")}</small></td><td>${esc(number(E.sample(p)))}</td><td>${esc(E.reason(p, index, edge))}</td><td>${esc(number(E.count(p.backfill_pending_trade_count)))}</td><td><a href="investor-edge.html#investor-${index}-details">Inspect history</a></td></tr>`
  ).join("") : `<tr><td colspan="5" class="empty">${edge ? "No profiles awaiting assessment in this publication." : "Building-history inventory unavailable."}</td></tr>`;
};
