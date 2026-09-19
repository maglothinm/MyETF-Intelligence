/* Personal acknowledgement authority is the authenticated server, never a browser cache. */
(() => {
  "use strict";
  class PersonalReviews {
    constructor({fetcher = (...args) => fetch(...args), onChange = () => {}} = {}) {
      this.fetcher = fetcher; this.onChange = onChange; this.generation = 0; this.loading = null;
      this.state = {status:"loading", account:null, revision:0, acknowledged:[]};
    }
    async request(path, body) {
      const options = {credentials:"same-origin", cache:"no-store", headers:{Accept:"application/json"}};
      if (body !== undefined) Object.assign(options, {method:"POST", body:JSON.stringify(body),
        headers:{...options.headers, "Content-Type":"application/json", "X-PolitiTrack-Review-Request":"1"}});
      let response, value;
      try { response = await this.fetcher("api/reviews/" + path, options); value = await response.json(); }
      catch { throw Object.assign(new Error("Saved review status is unavailable. Try again shortly."), {code:"REVIEWS_UNAVAILABLE"}); }
      if (!response.ok) {
        const allowed = new Set(["SIGN_IN_REQUIRED","SIGN_IN_FAILED","SIGN_IN_LIMIT","INVALID_PASSWORD","INVALID_INVITATION",
          "ACCOUNT_CHANGED","REVIEW_CHANGED","REQUEST_CONFLICT","IMPORT_IDENTITY_MISMATCH","INVALID_IMPORT_TIME"]);
        const message = allowed.has(value?.code) && typeof value.message === "string" ? value.message.slice(0,250) : "Saved review status is unavailable. Try again shortly.";
        throw Object.assign(new Error(message), {code:value?.code || "REVIEWS_UNAVAILABLE", status:response.status});
      }
      return value;
    }
    accept(value) {
      if (value?.authenticated === false) {
        this.state = {status:"signed_out", account:null, revision:0, acknowledged:[]};
      } else {
        if (value?.authenticated !== true || value.version !== 1 || !value.account || typeof value.account.id !== "string"
            || typeof value.account.username !== "string" || !Number.isSafeInteger(value.revision) || value.revision < 0
            || !Array.isArray(value.acknowledged)) throw new Error("Saved review status is invalid. Try again shortly.");
        const identities = new Set();
        for (const record of value.acknowledged) {
          if (!record || typeof record.id !== "string" || !record.id || record.id.length > 500
              || !/^review-logical-v1:[0-9a-f]{32}$/.test(record.logical_review_id || "")
              || !Number.isFinite(Date.parse(record.acknowledged_at_utc)) || identities.has(record.logical_review_id))
            throw new Error("Saved review status is invalid. Try again shortly.");
          identities.add(record.logical_review_id);
        }
        if (this.state.account?.id === value.account.id && value.revision < this.state.revision) return;
        this.state = {status:"ready", account:{...value.account}, revision:value.revision,
          acknowledged:value.acknowledged.map(record => ({...record}))};
      }
      this.onChange(this.state);
    }
    async load() {
      if (this.loading) return this.loading;
      const generation = this.generation;
      const pending = (async () => {
        try { const value = await this.request("session"); if (generation === this.generation) this.accept(value); }
        catch (error) { if (generation === this.generation) { this.state = {...this.state,status:"unavailable"}; this.onChange(this.state); } }
        finally { if (this.loading === pending) this.loading = null; }
        return this.state;
      })();
      this.loading = pending;
      return this.loading;
    }
    async authenticate(body, activate = false) {
      const generation = ++this.generation;
      const value = await this.request(activate ? "activate" : "login", body);
      if (generation === this.generation) this.accept(value);
      return this.state;
    }
    async logout() {
      const generation = ++this.generation;
      const value = await this.request("logout", {});
      if (generation === this.generation) this.accept(value);
    }
    async save(reviewId, logicalId, acknowledged) {
      if (this.state.status !== "ready") throw Object.assign(new Error("Sign in to save your reviews."), {code:"SIGN_IN_REQUIRED"});
      const generation = ++this.generation;
      const body = {review_id:reviewId, logical_review_id:logicalId, acknowledged,
        expected_account_id:this.state.account.id, expected_revision:this.state.revision, request_id:crypto.randomUUID()};
      try { const value = await this.request("acknowledgements", body); if (generation === this.generation) this.accept(value); }
      catch (error) {
        if (generation === this.generation && error.code === "SIGN_IN_REQUIRED") this.accept({authenticated:false});
        if (generation === this.generation && ["ACCOUNT_CHANGED","REVIEW_CHANGED"].includes(error.code)) { this.loading=null; await this.load(); }
        throw error;
      }
    }
    async importLegacy(value) {
      if (this.state.status !== "ready") throw new Error("Sign in to import your previous acknowledgements.");
      const generation = ++this.generation;
      try {
        const result = await this.request("import", {...value, expected_account_id:this.state.account.id});
        if (generation === this.generation) this.accept(result);
        return result;
      } catch (error) {
        if (generation === this.generation && error.code === "SIGN_IN_REQUIRED") this.accept({authenticated:false});
        if (generation === this.generation && error.code === "ACCOUNT_CHANGED") { this.loading=null; await this.load(); }
        throw error;
      }
    }
  }
  globalThis.PolitiTrackPersonalReviews = PersonalReviews;
})();
