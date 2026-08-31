import {dispatchCollector, DispatchError, TARGETS} from "../dispatch.mjs";

// Intentionally no fetch handler: neither a public trigger nor a browser timer.
export default {
  async scheduled(controller, env) {
    const branch = Object.keys(TARGETS).find(key => TARGETS[key].cron === controller.cron);
    if (!branch) throw new Error("Unrecognized PolitiTrack cron configuration");
    try {
      const outcome = await dispatchCollector({
        branch, repository: env.GITHUB_REPOSITORY,
        token: env.GITHUB_DISPATCH_TOKEN, enabled: env.SCHEDULER_ENABLED,
      });
      console.log(JSON.stringify(outcome));
    } catch (error) {
      console.error(JSON.stringify({branch, status: "dispatch_failed",
        code: error instanceof DispatchError ? error.code : "scheduler_error"}));
      throw new Error("PolitiTrack scheduler dispatch failed; review sanitized execution logs");
    }
  },
};
