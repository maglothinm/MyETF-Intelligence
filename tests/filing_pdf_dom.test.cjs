'use strict';
// Unit tests replace only the local PDF.js import with a deterministic engine.
// Actual PDF decoding, CSP and visual output require the separate browser check.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const modules = process.env.POLITITRACK_TEST_NODE_MODULES || path.resolve(__dirname, '../.remediation/ui-test-tools/node_modules');
const {JSDOM} = require(path.join(modules, 'jsdom'));
const source = fs.readFileSync(path.resolve(__dirname, '../scripts/dashboard_assets/filing-pdf.js'), 'utf8');
const tick = () => new Promise(resolve => setTimeout(resolve, 20));
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return {promise, resolve, reject}; };

function fixture(options = {}) {
  const dom = new JSDOM('<!doctype html><div id="viewer"></div>', {url:'https://polititrack.test/filing-vault.html', runScripts:'outside-only'});
  const {window} = dom;
  const state = {width:320, workers:[], loads:[], renders:[], observers:[], destroyed:0, pages:options.pages || 1};
  Object.defineProperty(window.HTMLElement.prototype, 'clientWidth', {get:() => state.width});
  Object.defineProperty(window, 'devicePixelRatio', {value:3});
  window.HTMLCanvasElement.prototype.getContext = () => ({});
  window.HTMLElement.prototype.getBoundingClientRect = function () {
    const label = this.getAttribute('aria-label') || this.parentElement?.getAttribute('aria-label') || '';
    const number = Number((/Page (\d+)/.exec(label) || [0,1])[1]);
    return {top:(number-1)*400, bottom:number*400, width:state.width, height:400};
  };
  window.Worker = class {
    constructor(url, config) { this.url=url; this.config=config; state.workers.push(this); }
    terminate() { this.terminated=true; }
  };
  window.IntersectionObserver = class {
    constructor(callback) { this.callback=callback; this.targets=[]; state.observers.push(this); }
    observe(target) { this.targets.push(target); }
    disconnect() { this.disconnected=true; }
    show(targets, visible=true) { this.callback(targets.map(target => ({target,isIntersecting:visible}))); }
  };
  window.ResizeObserver = class { constructor(callback){state.resize=callback;} observe(){} disconnect(){state.resizeDisconnected=true;} };
  const pdf = {
    numPages:state.pages,
    getPage:async number => ({
      getViewport:({scale}) => ({width:612*scale,height:792*scale}),
      render:config => {
        const gate = number === 1 && options.firstPage;
        const task = {promise:gate ? gate.promise : Promise.resolve(), cancel(){this.cancelled=true;}};
        state.renders.push({number,config,task}); return task;
      },
      getTextContent:async () => ({items:[{str:'<script>untrusted filing text</script>',hasEOL:true}]}),
      cleanup(){state.cleaned=(state.cleaned || 0)+1;},
    }),
  };
  window.__pdfjsFixture = {
    version:options.version || '6.3.289',
    PDFWorker:class { destroy(){state.pdfWorkerDestroyed=true;} },
    getDocument:config => {
      state.loads.push(config);
      return {promise:options.loading ? options.loading.promise : Promise.resolve(pdf), destroy(){state.destroyed++;}};
    },
  };
  assert.equal(source.split('import(moduleUrl.href)').length, 2);
  window.eval(source.replace('import(moduleUrl.href)', 'Promise.resolve(window.__pdfjsFixture)'));
  const container = window.document.getElementById('viewer');
  const bytes = new window.Uint8Array([37,80,68,70,45,49]);
  return {window,container,bytes,state,pdf,close:() => window.close()};
}

test('renderer resolves only after first page, keeps original bytes, and uses only local assets', async () => {
  const firstPage=deferred(), env=fixture({firstPage});
  let ready=false;
  const pending=env.window.PTFilingPdf.render(env.bytes,env.container).then(value => {ready=true; return value;});
  await tick();
  assert.equal(ready,false);
  assert.equal(env.container.getAttribute('aria-busy'),'true');
  firstPage.resolve();
  const handle=await pending;
  assert.equal(handle.pageCount,1);
  assert.equal(env.container.hasAttribute('aria-busy'),false);
  const settings=env.state.loads[0];
  assert.notEqual(settings.data,env.bytes);
  assert.deepEqual(Array.from(settings.data),Array.from(env.bytes));
  assert.equal(settings.url,undefined);
  assert.equal(settings.enableXfa,false);
  assert.equal(settings.isEvalSupported,false);
  for (const key of ['cMapUrl','standardFontDataUrl','wasmUrl','iccUrl']) assert.match(settings[key],/^https:\/\/polititrack\.test\/assets\/vendor\/pdfjs\//);
  assert.match(env.state.workers[0].url,/pdf\.worker\.mjs\?v=6\.3\.289$/);
  const canvas=env.container.querySelector('canvas');
  assert.ok(canvas.width * canvas.height <= 4*1024*1024);
  assert.equal(canvas.style.width,'100%');
  assert.equal(env.container.querySelector('iframe'),null);
  handle.destroy();env.close();
});

test('lazy pages bound canvases and discard offscreen pixels', async () => {
  const env=fixture({pages:8});
  const handle=await env.window.PTFilingPdf.render(env.bytes,env.container);
  assert.equal(env.state.renders.length,1);
  const observer=env.state.observers[0];
  assert.equal(observer.targets.length,8);
  observer.show(observer.targets);
  await tick();await tick();
  assert.ok(env.container.querySelectorAll('canvas').length <= 4);
  const canvases=Array.from(env.container.querySelectorAll('canvas'));
  observer.show(observer.targets,false);
  await tick();
  assert.equal(env.container.querySelectorAll('canvas').length,0);
  assert.ok(canvases.every(canvas => canvas.width===0 && canvas.height===0));
  handle.destroy();env.close();
});

test('extracted text stays plain text and is released with its page', async () => {
  const env=fixture();const handle=await env.window.PTFilingPdf.render(env.bytes,env.container);
  const details=env.container.querySelector('details');details.open=true;
  await tick();
  assert.match(env.container.querySelector('.pt-pdf-extracted').textContent,/<script>/);
  assert.equal(env.container.querySelector('script'),null);
  env.state.observers[0].show(env.state.observers[0].targets,false);
  assert.equal(details.open,false);
  assert.equal(env.container.querySelector('.pt-pdf-extracted').textContent,'');
  handle.destroy();env.close();
});

test('abort during load terminates worker and cannot populate a stale viewer', async () => {
  const loading=deferred(),env=fixture({loading}),controller=new env.window.AbortController();
  const pending=env.window.PTFilingPdf.render(env.bytes,env.container,{signal:controller.signal});
  await tick();controller.abort();
  await assert.rejects(pending,error => error.name==='AbortError');
  assert.ok(env.state.workers[0].terminated);
  assert.equal(env.state.destroyed,1);
  loading.resolve(env.pdf);await tick();
  assert.equal(env.container.children.length,0);
  env.close();
});

test('destroy releases canvases, worker and observers and is idempotent', async () => {
  const env=fixture();const handle=await env.window.PTFilingPdf.render(env.bytes,env.container);
  const canvas=env.container.querySelector('canvas');handle.destroy();handle.destroy();
  assert.equal(canvas.width,0);assert.equal(canvas.height,0);
  assert.equal(env.container.children.length,0);
  assert.ok(env.state.workers[0].terminated);
  assert.ok(env.state.observers[0].disconnected);
  assert.ok(env.state.resizeDisconnected);
  assert.equal(env.state.destroyed,1);env.close();
});

test('oversized page count and version mismatch have visible errors with download guidance', async () => {
  for (const options of [{pages:301},{version:'wrong'}]) {
    const env=fixture(options);
    await assert.rejects(env.window.PTFilingPdf.render(env.bytes,env.container));
    assert.ok(env.container.querySelector('[role="alert"]'));
    assert.equal(env.container.querySelector('canvas'),null);
    if(options.pages) assert.match(env.container.textContent,/301 pages.*300-page limit.*Download/);
    env.close();
  }
});

test('vendored source files match manifest hashes and exclude scripting engines and PDFs', () => {
  const root=path.resolve(__dirname,'../scripts/dashboard_assets/vendor/pdfjs');
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'MANIFEST.json'),'utf8'));
  assert.equal(manifest.version,'6.3.289');
  assert.equal(manifest.files.length,201);
  for (const file of manifest.files) {
    assert.doesNotMatch(file.path,/\.pdf$|quickjs|sandbox/i);
    const body=fs.readFileSync(path.join(root,file.path));
    assert.equal(body.length,file.bytes);
    assert.equal(crypto.createHash('sha256').update(body).digest('hex'),file.sha256);
  }
});
