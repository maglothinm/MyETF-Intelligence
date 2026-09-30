# Funding and paid-service status (#250)

The existing dashboard now has a Funding & paid services overview card and an
expanded Operating costs & funding page. This is private operational metadata,
not investment evidence, a billing invoice, a payment integration or another
producer-state owner. No page load or refresh makes a paid provider request.

## What is known, estimated, or missing

OpenAI API funding is explicitly separate from ChatGPT/Codex account credits.
The configured API is used by PolitiTrack; funding ChatGPT does not replenish it.
A successful API request proves that request was accepted, not a credit balance.
A structured quota error means funding or a spend limit blocked the request;
ordinary rate limiting is displayed separately. Historical unscoped events never
masquerade as freshly verified current-account observations.

OpenAI's documented `/organization/costs` reports costs, not prepaid remaining
credit. This implementation does not scrape private dashboard endpoints or
browser-session credentials, request an admin key, or guess an account balance.
The owner records the remaining balance shown in the correct provider account
with an observation time; the top-up amount is not substituted for the balance.
Private records are labelled owner-reported, not provider-verified.

A local token-only remaining estimate is shown separately only with a fresh,
matching API configuration and complete priced observations after the balance
observation. Tools, unknown prices, unscoped attempts, stale balances or missing
usage withhold the estimate. Other applications, taxes, delayed reporting,
credit expiry and unobserved requests remain excluded even when it is calculable.
Unknown never means zero. Small nonzero token costs retain decimal precision.

## Counters, units and freshness

The page counts paid plans with recorded owner observations, unverified services
and services needing attention. Each service can record prepaid balance, plan
charge and renewal/expiration date. Dollars, provider credit units and request
allowances are distinct; they are not summed into an invented dollar total.
API balance units must be USD. Low thresholds are warnings only, not spending
controls. Balances older than 24 hours are stale. API observations older than two
hours are stale. Renewals or credit expiry within seven days are flagged.

The inventory covers the application's API/data/notification integrations,
GitHub development resources, separate ChatGPT, local-host household costs and
an optional owner-declared other service. Unknown subscription status does not
mean a paid plan exists. Free selected architecture is not account entitlement
or invoice verification. No cloud runtime or subscription is created.

## Privacy, authority and persistence

Use the existing PolitiTrack personal-review account sign-in. Funding APIs work
only at the exact configured loopback origin. Reads require a valid session;
writes additionally require same origin, the existing request header, bounded
JSON, expected account/revision and an idempotent request ID. A changed account
cannot silently overwrite another account's balance. No keys or payment details
are accepted. Browser rendering uses text nodes, not owner-provided HTML.

Owner observations append to `runtime_billing_observations` in the existing
PostgreSQL database. Complete per-account sequence/hash chains are verified on
read. Existing review rows, review revisions and producer snapshots are not
changed. The existing physical PostgreSQL backup includes this additive table.
An operator initializes only this table during the normal release boundary;
web requests do not initialize or rebaseline producer state.

The native usage journal remains `logs/api-usage.sqlite3`. New entries add only
a one-way configuration-scope digest, purpose and whitelisted HTTP/error codes.
No prompts, responses, API keys or raw exception messages are logged by billing.
The web process receives that digest, not the key. Existing journal rows remain
unchanged. The funding API reads operational observations directly, so a failed
AI snapshot cannot hide recent API attempts. The separate existing published
usage section retains its snapshot identity and may lag the operational view.

This change does not integrate the previously blocked quota-cooldown draft,
renew capabilities, weaken investment gates, enable notifications, or claim a
completed company dossier. Billing warnings are dashboard-only. No outside
notification delivery, automated purchase or account/plan change is performed.

## Vendor contracts checked September 30, 2026

- OpenAI Costs API: https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs
- Separate API and ChatGPT billing: https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform
- Prepaid API billing: https://help.openai.com/en/articles/8264644-setting-up-and-managing-prepaid-api-billing

Source tests and intercepted browser fixtures prove implementation behavior,
not actual provider balances. A real minimal API request after the owner's
corrected API funding returned HTTP 200 and a completed response on September 30
at 12:06:27 UTC, with 10 input and 5 output tokens. No balance amount was returned.
Native deployment, private metadata table initialization, live route/asset
verification and any newly published AI result must be reported separately.
