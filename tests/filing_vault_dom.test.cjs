'use strict';

// All network responses are TEST fixtures. JSDOM establishes DOM behavior only;
// it does not establish PDF.js rendering, mobile layout, browser CSP or touch behavior.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const modules = process.env.POLITITRACK_TEST_NODE_MODULES || path.resolve(__dirname, '../.remediation/ui-test-tools/node_modules');
const {JSDOM, VirtualConsole} = require(path.join(modules, 'jsdom'));
const axe = require(path.join(modules, 'axe-core'));
const root = path.resolve(__dirname, '..');
const build = process.env.POLITITRACK_TEST_BUILD || path.join(root, 'scripts/dashboard_assets');
const clone = value => JSON.parse(JSON.stringify(value));
const pause = () => new Promise(resolve => setTimeout(resolve, 5));
const response = (body, status = 200, headers = {}) => ({
  ok: status >= 200 && status < 300, status,
  headers: new Headers(headers),
  json: async () => clone(body),
  blob: async () => body instanceof Blob ? body : new Blob([body], {type: 'application/pdf'})
});

function row(id = 'TEST-house-42', changes = {}) {
  return {
    filing_id: id, external_filing_id: 'TEST-report-42', filer_name: 'TEST Fixture Filer',
    filing_type: 'Periodic Transaction Report', source: 'house',
    filing_date: '2026-08-01', retrieved_at: '2026-08-10T12:00:00Z',
    expires_at: '2026-09-09T12:00:00Z', last_validated_at: '2026-08-31T10:00:00Z',
    cache_status: 'CACHED', status: 'CURRENT',
    official_source_url: 'https://official.example.test/reports/TEST-42',
    versions: [{document_version: 1, retrieved_at: '2026-08-10T12:00:00Z', cache_status: 'CACHED', sha256: 'a'.repeat(64)}],
    ...changes
  };
}
async function waitFor(predicate, message = 'fixture settled') {
  const started = Date.now();
  while (!predicate()) {
    if (Date.now() - started > 2500) throw new Error('Timed out: ' + message);
    await pause();
  }
}
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

async function vault(options = {}) {
  const rows = clone(options.rows || [row()]);
  const requests = [], errors = [], created = [], revoked = [], pdfRenders = [];
  let acknowledged = options.acknowledged !== false;
  let dialogOpens = 0;
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', error => errors.push(error.message));
  const dom = new JSDOM(fs.readFileSync(path.join(build, 'filing-vault.html'), 'utf8'), {
    url: 'https://dashboard.example.test/PolitiTrack/filing-vault.html' + (options.query || ''),
    runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole
  });
  const {window} = dom;
  const doc = window.document;
  window.Blob = Blob;
  window.Headers = Headers;
  window.URL.createObjectURL = blob => { const url = 'blob:TEST-' + (created.length + 1); created.push({url, blob}); return url; };
  window.URL.revokeObjectURL = url => revoked.push(url);
  window.PTFilingPdf = {
    async render(bytes, container, renderOptions = {}) {
      const rendering = {bytes: Array.from(bytes), container, destroyed: false, signal: renderOptions.signal};
      pdfRenders.push(rendering);
      if (options.pdfRenderer) return options.pdfRenderer(bytes, container, rendering, window, renderOptions);
      const canvas = doc.createElement('canvas');
      canvas.width = 700; canvas.height = 980;
      canvas.setAttribute('aria-label', 'TEST PDF page 1');
      canvas.textContent = 'TEST locally rendered original filing page';
      container.append(canvas);
      return {destroy() { rendering.destroyed = true; canvas.remove(); }};
    }
  };
  window.HTMLElement.prototype.scrollIntoView = function () {};
  window.HTMLDialogElement.prototype.showModal = function () { this.open = true; dialogOpens++; };
  window.HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new window.Event('close')); };
  window.addEventListener('error', event => errors.push(event.error?.message || event.message));
  window.addEventListener('unhandledrejection', event => errors.push(String(event.reason)));
  if (options.storedToken) window.localStorage.setItem('polititrack.filing-ack.v1', options.storedToken);
  window.fetch = async (value, fetchOptions = {}) => {
    const url = new URL(String(value), window.location.href);
    const request = {url: url.href, path: url.pathname, query: url.search, method: fetchOptions.method || 'GET', options: fetchOptions};
    requests.push(request);
    if (options.handler) {
      const intercepted = await options.handler(request, {rows, response, window});
      if (intercepted !== undefined) return intercepted;
    }
    if (url.pathname.endsWith('/data/filing-vault-config.json')) return response(options.config || {});
    if (url.pathname.endsWith('/data/filing-resources.json')) return response({filings: options.catalog || rows});
    if (!url.pathname.startsWith('/api/')) throw new Error('Unexpected TEST network request: ' + url.href);
    if (url.pathname === '/api/filings') return response({filings: rows});
    if (url.pathname === '/api/filing-acknowledgements') {
      if (request.method === 'POST') { acknowledged = true; return response({token: 'TEST-ack-token'}); }
      return response({acknowledged, version: 'TEST-notice-v1', policy_version: 'TEST-policy-v1', text: 'TEST statutory use notice'});
    }
    const match = url.pathname.match(/^\/api\/filings\/(.+?)(\/document|\/refresh)?$/);
    if (!match) throw new Error('Unexpected TEST API route: ' + url.pathname);
    const id = decodeURIComponent(match[1]);
    const filing = rows.find(item => item.filing_id === id);
    if (!filing) return response({message: 'The exact TEST filing is unavailable.', code: 'NOT_FOUND'}, 404);
    if (match[2] === '/document') return response(new Blob(['%PDF-1.7 TEST original filing bytes'], {type: 'application/pdf'}));
    return response({filing});
  };
  const code = fs.readFileSync(path.join(build, 'filing-vault.js'), 'utf8');
  if (!code.includes('window.PT =')) window.eval(fs.readFileSync(path.join(root, 'scripts/dashboard_assets/common.js'), 'utf8'));
  window.eval(code);
  const env = {
    dom, window, doc, rows, requests, errors, created, revoked, pdfRenders,
    dialogOpens: () => dialogOpens,
    click: id => doc.getElementById(id).click(),
    documentCalls: () => requests.filter(item => item.path.endsWith('/document')),
    metadataCalls: () => requests.filter(item => /^\/api\/filings\/[^?]+$/.test(item.path) && !/\/(document|refresh)$/.test(item.path)),
    open: async id => {
      const button = [...doc.querySelectorAll('[data-open-filing]')].find(item => item.dataset.openFiling === id);
      assert.ok(button, 'The exact TEST filing must appear in the inventory');
      button.click();
    },
    settleDocument: async () => waitFor(() => !doc.getElementById('filing-download').hidden && /cached copy|TEST warning/.test(doc.getElementById('filing-message').textContent), 'document rendered and metadata refreshed'),
    close: () => dom.window.close()
  };
  await waitFor(() => !/Connecting/.test(doc.getElementById('vault-runtime').textContent), 'inventory loaded');
  return env;
}

test('exact filing IDs are URL encoded and only that original PDF is displayed/downloaded', async t => {
  const filing = row('TEST:house:report/42');
  const env = await vault({rows: [filing], query: '?filing=' + encodeURIComponent(filing.filing_id)});
  t.after(env.close);
  await env.settleDocument();
  assert.deepEqual(env.documentCalls().map(item => item.path), ['/api/filings/TEST%3Ahouse%3Areport%2F42/document']);
  assert.equal(env.doc.querySelector('#filing-document iframe'), null);
  assert.ok(env.doc.querySelector('#filing-document canvas'));
  assert.equal(env.pdfRenders.length, 1);
  assert.equal(Buffer.from(env.pdfRenders[0].bytes).toString(), '%PDF-1.7 TEST original filing bytes');
  assert.equal(env.doc.getElementById('filing-official').href, filing.official_source_url);
  assert.match(env.doc.getElementById('filing-download').download, /^filing-TEST_house_report_42\.pdf$/);
  assert.equal(await env.created[0].blob.text(), '%PDF-1.7 TEST original filing bytes');
  assert.equal(env.doc.activeElement.id, 'filing-title');
  assert.deepEqual(env.errors, []);
});

test('acknowledgement gates retrieval, records exact policy once, and persists for cached reopens', async t => {
  const env = await vault({acknowledged: false});
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await waitFor(() => env.doc.getElementById('filing-acknowledgement').open, 'notice opened');
  assert.equal(env.documentCalls().length, 0);
  assert.equal(env.doc.getElementById('filing-ack-text').textContent, 'TEST statutory use notice');
  env.click('filing-ack-accept');
  await env.settleDocument();
  const posts = env.requests.filter(item => item.path === '/api/filing-acknowledgements' && item.method === 'POST');
  assert.equal(posts.length, 1);
  assert.deepEqual(JSON.parse(posts[0].options.body), {accepted: true, version: 'TEST-notice-v1', policy_version: 'TEST-policy-v1'});
  assert.equal(env.documentCalls()[0].options.headers.Authorization, 'Bearer TEST-ack-token');
  assert.equal(env.window.localStorage.getItem('polititrack.filing-ack.v1'), 'TEST-ack-token');
  env.click('filing-close');
  assert.equal(env.pdfRenders[0].destroyed, true, 'closing frees the local PDF renderer');
  await env.open(env.rows[0].filing_id);
  await env.settleDocument();
  assert.equal(env.dialogOpens(), 1);
  assert.equal(env.requests.filter(item => item.path === '/api/filing-acknowledgements' && item.method === 'POST').length, 1);
  assert.equal(env.documentCalls().length, 2);
  assert.ok(env.revoked.includes('blob:TEST-1'));
});

test('cancelled acknowledgement never fetches bytes and retains Official Source', async t => {
  const env = await vault({acknowledged: false});
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await waitFor(() => env.doc.getElementById('filing-acknowledgement').open);
  env.click('filing-ack-cancel');
  await waitFor(() => /cancelled/.test(env.doc.getElementById('filing-message').textContent));
  assert.equal(env.documentCalls().length, 0);
  assert.equal(env.doc.getElementById('filing-official').href, env.rows[0].official_source_url);
  assert.equal(env.doc.getElementById('filing-download').hidden, true);
});

test('request-only OGE reports explain the access failure without substituting another document', async t => {
  const env = await vault({
    rows: [row('TEST-oge-request', {source: 'oge', status: 'ACCESS_REQUIRED', retrieved_at: null, official_source_url: 'https://official.example.test/oge/TEST-request'})],
    handler: request => request.path.endsWith('/document') ? response({code: 'SOURCE_ACCESS_REQUIRED', message: 'TEST: This OGE report requires a government Form 201 request.'}, 403) : undefined
  });
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await waitFor(() => !env.doc.getElementById('filing-retry').hidden);
  assert.match(env.doc.getElementById('filing-message').textContent, /Form 201 request/);
  assert.equal(env.doc.getElementById('filing-source').textContent, 'OGE');
  assert.equal(env.created.length, 0);
  assert.equal(env.doc.getElementById('filing-official').href, env.rows[0].official_source_url);
  assert.equal(env.doc.getElementById('filing-download').hidden, true);
  assert.ok(env.requests.every(item => !item.url.includes('/oge/TEST-request')));
});

test('expired unavailable documents expose Retry and Official Source; retry is an explicit user action', async t => {
  let expired = true;
  const env = await vault({
    rows: [row('TEST-expired', {cache_status: 'EXPIRED', status: 'ARCHIVED'})],
    handler: request => request.path.endsWith('/document') && expired ? response({code: 'SOURCE_UNAVAILABLE', message: 'TEST: Cached copy expired; official source is temporarily unavailable.'}, 503) : undefined
  });
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await waitFor(() => !env.doc.getElementById('filing-retry').hidden);
  assert.match(env.doc.getElementById('filing-message').textContent, /expired.*temporarily unavailable/);
  assert.equal(env.doc.getElementById('filing-official').hidden, false);
  assert.equal(env.documentCalls().length, 1);
  assert.equal(env.created.length, 0);
  expired = false;
  env.click('filing-retry');
  await env.settleDocument();
  assert.equal(env.documentCalls().length, 2);
});

test('hostile metadata and archived HTML are rendered as text without executable markup', async t => {
  const attack = '<img src=x onerror="window.TEST_PWNED=true">';
  const html = '<html><body><h1>TEST Original</h1><script>window.TEST_PWNED=true</script><form>FORM HIDDEN</form><p>&lt;original content&gt;</p><img src="https://bad.example.test/collect" onerror="window.TEST_PWNED=true"></body></html>';
  const env = await vault({
    rows: [row('TEST-hostile', {filer_name: attack, filing_type: '<svg onload="window.TEST_PWNED=true">', versions: [{document_version: attack, sha256: attack}]})],
    handler: request => request.path.endsWith('/document') ? response(new Blob([html], {type: 'text/html'})) : undefined
  });
  t.after(env.close);
  assert.equal(env.doc.querySelector('#vault-list img'), null);
  await env.open(env.rows[0].filing_id);
  await env.settleDocument();
  assert.equal(env.doc.getElementById('filing-title').textContent, attack);
  assert.equal(env.doc.querySelector('#filing-history img'), null);
  assert.equal(env.doc.querySelector('#filing-document script,#filing-document img,#filing-document form'), null);
  assert.match(env.doc.querySelector('#filing-document pre').textContent, /TEST Original.*<original content>/s);
  assert.doesNotMatch(env.doc.querySelector('#filing-document pre').textContent, /TEST_PWNED|FORM HIDDEN/);
  assert.equal(env.window.TEST_PWNED, undefined);
  assert.equal(await env.created[0].blob.text(), html, 'download remains the original archived response');
  assert.equal(env.requests.some(item => item.url.includes('bad.example.test')), false);
  assert.equal(env.pdfRenders.length, 0, 'HTML uses a text projection, not the PDF renderer');
});

test('local PDF renderer rejection is explicit while the original download remains available', async t => {
  const env = await vault({pdfRenderer: async () => { throw new Error('TEST local PDF renderer rejected this document'); }});
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await waitFor(() => !env.doc.getElementById('filing-retry').hidden);
  assert.match(env.doc.getElementById('filing-message').textContent, /TEST local PDF renderer rejected/);
  assert.equal(env.doc.querySelector('#filing-document canvas'), null);
  assert.equal(env.doc.getElementById('filing-download').hidden, false);
  assert.equal(await env.created[0].blob.text(), '%PDF-1.7 TEST original filing bytes');
  assert.equal(env.doc.getElementById('filing-official').href, env.rows[0].official_source_url);
});

test('a supplied arbitrary source URL is never fetched or substituted', async t => {
  const env = await vault({query: '?url=' + encodeURIComponent('https://attacker.example.test/private.pdf')});
  t.after(env.close);
  await waitFor(() => /could not be uniquely resolved/.test(env.doc.getElementById('vault-runtime').textContent));
  assert.equal(env.documentCalls().length, 0);
  assert.equal(env.metadataCalls().length, 0);
  assert.equal(env.requests.some(item => item.url.includes('attacker.example.test')), false);
});

test('a retained URL resolves only when its source/report match uniquely', async t => {
  const original = row('TEST-house-a');
  const alternate = row('TEST-senate-b', {source: 'senate', external_filing_id: 'TEST-report-b'});
  const env = await vault({rows: [original, alternate], query: '?url=' + encodeURIComponent(original.official_source_url)});
  t.after(env.close);
  await waitFor(() => /could not be uniquely resolved/.test(env.doc.getElementById('vault-runtime').textContent));
  assert.equal(env.documentCalls().length, 0);
});

test('slow metadata for an old selection cannot replace the newly selected filing', async t => {
  const old = deferred();
  const first = row('TEST-old');
  const newest = row('TEST-new', {filer_name: 'TEST Newest Filer', external_filing_id: 'TEST-new-report'});
  const env = await vault({
    rows: [first, newest],
    handler: request => request.path === '/api/filings/TEST-old' ? old.promise : undefined
  });
  t.after(env.close);
  await env.open(first.filing_id);
  await waitFor(() => env.requests.some(item => item.path === '/api/filings/TEST-old'));
  await env.open(newest.filing_id);
  await env.settleDocument();
  old.resolve(response({filing: first}));
  await pause();
  assert.equal(env.doc.getElementById('filing-title').textContent, 'TEST Newest Filer');
  assert.deepEqual(env.documentCalls().map(item => item.path), ['/api/filings/TEST-new/document']);
});

test('closing the viewer while acknowledgement loads never opens an obsolete consent dialog', async t => {
  const notice = deferred();
  const env = await vault({
    acknowledged: false,
    handler: request => request.path === '/api/filing-acknowledgements' ? notice.promise : undefined
  });
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await waitFor(() => env.requests.some(item => item.path === '/api/filing-acknowledgements'));
  env.click('filing-close');
  notice.resolve(response({acknowledged: false, version: 'TEST-v1', policy_version: 'TEST-policy-v1', text: 'TEST obsolete notice'}));
  await pause();
  assert.equal(env.doc.getElementById('vault-viewer').hidden, true);
  assert.equal(env.doc.getElementById('filing-acknowledgement').open, false);
  assert.equal(env.documentCalls().length, 0);
});

test('slow old document bytes cannot overwrite the newest viewer or create a stray blob URL', async t => {
  const old = deferred();
  const first = row('TEST-old-bytes');
  const newest = row('TEST-new-bytes', {filer_name: 'TEST New Bytes'});
  const env = await vault({
    rows: [first, newest],
    handler: request => request.path === '/api/filings/TEST-old-bytes/document' ? old.promise : undefined
  });
  t.after(env.close);
  await env.open(first.filing_id);
  await waitFor(() => env.documentCalls().length === 1);
  await env.open(newest.filing_id);
  await env.settleDocument();
  old.resolve(response(new Blob(['%PDF TEST stale bytes'], {type: 'application/pdf'})));
  await pause();
  assert.equal(env.doc.getElementById('filing-title').textContent, 'TEST New Bytes');
  assert.equal(env.created.length, 1);
  assert.equal(await env.created[0].blob.text(), '%PDF-1.7 TEST original filing bytes');
});

test('a slow obsolete PDF render is aborted and destroyed without replacing the newest pages', async t => {
  const oldRender = deferred();
  let renderCount = 0;
  const env = await vault({
    rows: [row('TEST-render-old'), row('TEST-render-new', {filer_name: 'TEST New Render'})],
    pdfRenderer: async (_bytes, container, rendering, window) => {
      const sequence = ++renderCount;
      if (sequence === 1) await oldRender.promise;
      const canvas = window.document.createElement('canvas');
      canvas.textContent = sequence === 1 ? 'TEST old page' : 'TEST newest page';
      container.append(canvas);
      return {destroy() { rendering.destroyed = true; canvas.remove(); }};
    }
  });
  t.after(env.close);
  await env.open('TEST-render-old');
  await waitFor(() => env.pdfRenders.length === 1);
  await env.open('TEST-render-new');
  await env.settleDocument();
  assert.equal(env.pdfRenders[0].signal.aborted, true);
  oldRender.resolve();
  await waitFor(() => env.pdfRenders[0].destroyed);
  assert.equal(env.doc.getElementById('filing-title').textContent, 'TEST New Render');
  assert.equal(env.doc.querySelectorAll('#filing-document canvas').length, 1);
  assert.equal(env.doc.querySelector('#filing-document canvas').textContent, 'TEST newest page');
});

test('metadata with a mismatched ID fails closed before requesting a different filing', async t => {
  const first = row('TEST-requested');
  const wrong = row('TEST-wrong', {filer_name: 'TEST Wrong Filer'});
  const env = await vault({
    rows: [first, wrong],
    handler: request => request.path === '/api/filings/TEST-requested' ? response({filing: wrong}) : undefined
  });
  t.after(env.close);
  await env.open(first.filing_id);
  await waitFor(() => !env.doc.getElementById('filing-retry').hidden || env.documentCalls().length > 0);
  assert.equal(env.documentCalls().length, 0, 'never follow a substituted filing ID from metadata');
  assert.match(env.doc.getElementById('filing-message').textContent, /match|identity|exact filing|different filing ID/i);
  assert.equal(env.doc.getElementById('filing-official').href, first.official_source_url);
});

test('refresh with a mismatched ID never opens the substituted document', async t => {
  const first = row('TEST-refresh-requested');
  const wrong = row('TEST-refresh-wrong', {filer_name: 'TEST Wrong Refresh'});
  const env = await vault({
    rows: [first, wrong],
    handler: request => request.path === '/api/filings/TEST-refresh-requested/refresh' ? response({filing: wrong}) : undefined
  });
  t.after(env.close);
  await env.open(first.filing_id);
  await env.settleDocument();
  env.click('filing-refresh');
  await waitFor(() => !env.doc.getElementById('filing-retry').hidden || env.documentCalls().length > 1);
  assert.equal(env.documentCalls().length, 1, 'refresh may not change the original filing identity');
  assert.match(env.doc.getElementById('filing-message').textContent, /match|identity|exact filing|different filing ID/i);
});

test('TEST/simulated rows never retrieve documents or obtain a production acknowledgement', async t => {
  const env = await vault({rows: [row('TEST-synthetic', {is_synthetic_test: true})], acknowledged: false});
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await waitFor(() => /TEST \/ SIMULATED/.test(env.doc.getElementById('filing-message').textContent));
  assert.equal(env.documentCalls().length, 0);
  assert.equal(env.requests.filter(item => item.path === '/api/filing-acknowledgements').length, 0);
  assert.equal(env.doc.getElementById('filing-download').hidden, true);
});

test('an unavailable API leaves only retained catalog evidence and government source links', async t => {
  const env = await vault({handler: request => request.path === '/api/filings' ? response({message: 'TEST unavailable'}, 503) : undefined});
  t.after(env.close);
  assert.match(env.doc.getElementById('vault-runtime').textContent, /No cached-copy availability is claimed/);
  await env.open(env.rows[0].filing_id);
  await waitFor(() => !env.doc.getElementById('filing-retry').hidden);
  assert.equal(env.documentCalls().length, 0);
  assert.equal(env.doc.getElementById('filing-download').hidden, true);
  assert.equal(env.doc.getElementById('filing-official').href, env.rows[0].official_source_url);
});

test('source filters and pagination preserve exact retained filing identities', async t => {
  const rows = Array.from({length: 35}, (_, index) => row('TEST-page-' + String(index).padStart(2, '0'), {source: index === 34 ? 'senate' : 'house'}));
  const env = await vault({rows});
  t.after(env.close);
  assert.equal(env.doc.querySelectorAll('[data-open-filing]').length, 30);
  env.click('vault-next');
  assert.equal(env.doc.querySelectorAll('[data-open-filing]').length, 5);
  env.doc.getElementById('vault-source').value = 'senate';
  env.doc.getElementById('vault-source').dispatchEvent(new env.window.Event('change'));
  assert.equal(env.doc.querySelectorAll('[data-open-filing]').length, 1);
  assert.equal(env.doc.querySelector('[data-open-filing]').dataset.openFiling, 'TEST-page-34');
  assert.equal(env.doc.getElementById('vault-page').textContent, 'Page 1 of 1');
});

test('configured origin changes only API requests, with omitted cookies and no-store responses', async t => {
  const env = await vault({config: {api_origin: 'https://vault-api.example.test'}, storedToken: 'TEST-saved-token'});
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await env.settleDocument();
  for (const request of env.requests.filter(item => item.path.startsWith('/api/'))) {
    assert.equal(new URL(request.url).origin, 'https://vault-api.example.test');
    assert.equal(request.options.credentials, 'omit');
    assert.equal(request.options.cache, 'no-store');
    assert.equal(request.options.headers.Authorization, 'Bearer TEST-saved-token');
  }
  assert.equal(env.requests.filter(item => item.path.includes('/data/')).every(item => new URL(item.url).origin === 'https://dashboard.example.test'), true);
});

test('all server pages are loaded before presenting a complete inventory', async t => {
  const rows = Array.from({length: 205}, (_, index) => row('TEST-server-page-' + String(index).padStart(3, '0')));
  const env = await vault({
    rows, catalog: [],
    handler: request => {
      if (request.path !== '/api/filings') return undefined;
      const offset = Number(new URLSearchParams(request.query).get('offset') || 0);
      return response({filings: rows.slice(offset, offset + 200), total: rows.length, limit: 200, offset});
    }
  });
  t.after(env.close);
  assert.match(env.doc.getElementById('vault-count').textContent, /^205 filings/);
  assert.deepEqual(env.requests.filter(item => item.path === '/api/filings').map(item => new URLSearchParams(item.query).get('offset')), ['0', '200']);
  env.doc.getElementById('vault-search').value = 'TEST-server-page-204';
  env.doc.getElementById('vault-search').dispatchEvent(new env.window.Event('input'));
  assert.equal(env.doc.querySelector('[data-open-filing]').dataset.openFiling, 'TEST-server-page-204');
});

test('inconsistent server pagination never claims a partially retrieved live inventory', async t => {
  const retained = row('TEST-retained-catalog');
  const env = await vault({
    catalog: [retained],
    handler: request => {
      if (request.path !== '/api/filings') return undefined;
      const offset = Number(new URLSearchParams(request.query).get('offset') || 0);
      return response({filings: offset ? [] : [row('TEST-live-first')], total: 201, limit: 200, offset});
    }
  });
  t.after(env.close);
  assert.match(env.doc.getElementById('vault-runtime').textContent, /No cached-copy availability is claimed/);
  assert.deepEqual([...env.doc.querySelectorAll('[data-open-filing]')].map(item => item.dataset.openFiling), [retained.filing_id]);
  assert.match(env.doc.getElementById('vault-count').textContent, /cache status unverified/);
});

test('mobile download, semantic controls and fixture accessibility remain available', async t => {
  const env = await vault();
  t.after(env.close);
  await env.open(env.rows[0].filing_id);
  await env.settleDocument();
  assert.match(env.doc.querySelector('meta[name="viewport"]').content, /width=device-width/);
  assert.equal(env.doc.getElementById('filing-download').hidden, false);
  assert.ok(env.doc.querySelector('#filing-document canvas'));
  assert.equal(env.doc.getElementById('filing-message').getAttribute('aria-live'), 'polite');
  assert.equal(env.doc.getElementById('filing-official').rel, 'noopener noreferrer');
  assert.ok(env.doc.querySelector('label input#vault-search'));
  assert.ok(env.doc.querySelector('label select#vault-source'));
  env.window.eval(axe.source);
  const results = await env.window.axe.run(env.doc, {
    rules: {'color-contrast': {enabled: false}},
    runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}
  });
  assert.deepEqual(clone(results.violations.filter(item => ['serious', 'critical'].includes(item.impact)).map(item => ({id: item.id, nodes: item.nodes.map(node => node.target)}))), []);
});
