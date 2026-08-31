'use strict';
// Shared link rendering only; government retrieval is never performed here.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const modules = process.env.POLITITRACK_TEST_NODE_MODULES || path.resolve(__dirname, '../.remediation/ui-test-tools/node_modules');
const {JSDOM} = require(path.join(modules, 'jsdom'));
const source = fs.readFileSync(path.resolve(__dirname, '../scripts/dashboard_assets/common.js'), 'utf8');

function actions(row) {
  const dom = new JSDOM('<!doctype html><main></main>', {url:'https://polititrack.test/',runScripts:'outside-only'});
  dom.window.eval(source);
  const main=dom.window.document.querySelector('main');
  main.innerHTML=dom.window.PT.filingActions(row);
  const result={text:main.textContent,links:Array.from(main.querySelectorAll('a'),a=>({href:a.getAttribute('href'),text:a.textContent}))};
  dom.window.close();
  return result;
}

for (const resolution of ['conflict','ambiguous','unresolved']) {
  test(`a ${resolution} projection preserves Official Source but cannot use retained ID fallback`, () => {
    const result=actions({filing_key:'TEST-A',filing_id:'TEST-A',filing_resolution:resolution,source_url:'https://official.example.test/TEST-B.pdf'});
    assert.equal(result.links.length,1);
    assert.equal(result.links[0].href,'https://official.example.test/TEST-B.pdf');
    assert.match(result.links[0].text,/Official Source/);
    assert.doesNotMatch(result.text,/View Filing/);
    assert.match(result.text,/conflict|unavailable/);
  });
}

test('conflicting explicit IDs fail closed even without a projection marker', () => {
  const result=actions({filing_key:'TEST-A',filing_id:'TEST-B',source_url:'https://official.example.test/TEST-B.pdf'});
  assert.equal(result.links.length,1);
  assert.match(result.text,/identity conflict/);
  assert.doesNotMatch(result.text,/View Filing/);
});

test('a matched exact ID remains encoded and separate from its Official Source', () => {
  const result=actions({filing_key:'TEST-A:/x',filing_id:'TEST-A:/x',filing_resolution:'matched',source_url:'https://official.example.test/TEST-A.pdf'});
  assert.equal(result.links.length,2);
  assert.equal(new URL(result.links[0].href,'https://polititrack.test').searchParams.get('filing'),'TEST-A:/x');
  assert.equal(result.links[1].href,'https://official.example.test/TEST-A.pdf');
});

test('unprojected live rows and URL-only consumers remain compatible', () => {
  assert.equal(actions({filing_id:'TEST-live'}).links[0].href,'filing-vault.html?filing=TEST-live');
  const result=actions({source_url:'https://official.example.test/TEST-A.pdf',source:'house',report_id:'TEST-report'});
  const query=new URL(result.links[0].href,'https://polititrack.test').searchParams;
  assert.equal(query.get('url'),'https://official.example.test/TEST-A.pdf');
  assert.equal(query.get('source'),'house');
  assert.equal(query.get('report'),'TEST-report');
});
