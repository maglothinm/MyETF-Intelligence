"""Isolated browser acceptance fixture; never connects to live source/intake APIs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    assets=ROOT/'scripts/dashboard_assets'
    with sync_playwright() as tool:
        browser=tool.chromium.launch(executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1280,'height':900})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        rows=[{'page':1 if index<4 else 2,'row':index+1 if index<4 else 1,'asset':'TEST School District Bond',
               'owner':'','transaction_type':'Purchase','transaction_date':'2026-07-30',
               'notification_date':'2026-08-19','amount':'$15,001 - $50,000','issues':['asset_text_needs_review']} for index in range(5)]
        upload={'upload_id':'test-upload','filing_key':'house:test','sha256':'a'*64,'status':'needs_review',
                'page_count':2,'created_at':'2026-09-17T14:00:00Z','result':{'rows':rows,'problems':[],'filer_matches':True}}
        status={'account_id':'test-owner','uploads':[upload],'coverage':{'complete':2,'needs_review':1,'pending':8}}
        # Pure in-memory browser fixture: no network origin, proxy bypass,
        # credential or external endpoint is involved.
        page.set_content('<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><main><h1>TEST source OCR</h1><div id="actions"></div></main></body></html>')
        page.evaluate("""fixture => {
          window.ocrFixture=fixture; window.ocrRequests=[];
          window.fetch=async (url, options={}) => {
            if(url==='/api/source-ocr/status')return new Response(JSON.stringify(window.ocrFixture),{status:200,headers:{'Content-Type':'application/json'}});
            if(url==='/api/source-ocr/confirm') {
              window.ocrRequests.push({data:JSON.parse(options.body),headers:options.headers});
              window.ocrFixture.uploads[0].status='approved';
              return new Response(JSON.stringify({status:'approved'}),{status:202,headers:{'Content-Type':'application/json'}});
            }
            throw new Error('Unexpected TEST API call: '+url);
          };
        }""",status)
        page.add_style_tag(content=(assets/'styles.css').read_text())
        page.add_script_tag(content=(assets/'common.js').read_text())
        page.add_script_tag(content=(assets/'source-ocr.js').read_text())
        page.evaluate("document.getElementById('actions').innerHTML=PT.sourceOcrActions({filing_key:'house:test',ocr_status:'needs_review',ocr_page_count:2,ocr_completed_pages:2})")
        page.get_by_role('button',name='Upload source / OCR',exact=True).click()
        page.get_by_role('button',name='Review extracted rows').click()
        assert page.locator('[data-ocr-row]').count()==5
        page.screenshot(path=str(args.output/'source-ocr-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(args.output/'source-ocr-mobile.png'),full_page=True)
        page.locator('[data-ocr-row="0"] [data-field="asset"]').fill('Corrected TEST municipal bond')
        page.locator('#source-ocr-confirmed').check()
        page.get_by_role('button',name='Confirm corrections for PolitiTrack').click()
        page.wait_for_function("document.querySelector('#source-ocr-message').textContent.includes('Corrections confirmed')")
        requests=page.evaluate('window.ocrRequests')
        assert len(requests)==1 and requests[0]['data']['rows'][0]['asset']=='Corrected TEST municipal bond'
        assert requests[0]['headers']['X-PolitiTrack-Account']=='test-owner'
        assert len(requests[0]['data']['rows'])==5 and requests[0]['data']['rows'][4]['page']==2
        # Exercise the actual Operations health renderer separately from the
        # correction modal. Collection success must not hide deferred OCR cleanup.
        health = {"health": {"branches": [{"branch": "legislative", "status": "success", "errors": [], "timeline": [],
            "last_success_utc": "2026-09-17T20:00:00Z", "expected_interval_minutes": 30,
            "stale_after_minutes": 90, "latest_conclusion": "success", "latest_run_success": True,
            "source_ocr": {"enabled": True, "required": True, "status": "failure", "activity": "degraded",
                "stage": "complete", "detail": "TEST: collection succeeded; OCR file cleanup is deferred.",
                "started_at": "2026-09-17T19:59:00Z", "heartbeat_at": "2026-09-17T20:00:00Z",
                "finished_at": "2026-09-17T20:00:00Z", "documents_attempted": 5, "documents_completed": 4,
                "pages_completed": 8, "pages_expected": 8, "extractions_reused": 1, "transactions_appended": 5,
                "ready_remaining": 23, "unobserved_remaining": 19, "review_remaining": 3, "access_remaining": 2,
                "retry_remaining": 1, "cleanup_status": "deferred", "intake_status": "ok", "cleanup_error_code": "TESTCleanupError"}}]}}
        page.evaluate("document.body.innerHTML='<main style=\"max-width:900px;margin:auto;padding:16px\"><h1>TEST Operations health</h1><div id=\"health-fixture\"></div></main>'")
        page.evaluate("model => document.getElementById('health-fixture').innerHTML=PT.healthCards(model,true)", health)
        assert page.locator('[data-ocr-health="legislative"] .status.failure').count() == 1
        assert page.locator('[data-collector-health="legislative"] > header .status.success').count() == 1
        assert page.locator('[data-ocr-health="legislative"]').get_by_text('Last healthy OCR pass', exact=True).count() == 1
        assert page.locator('[data-collector-health="legislative"]').get_by_text('Last successful collection', exact=True).count() == 1
        for width, height in ((1280, 900), (390, 844)):
            page.set_viewport_size({"width": width, "height": height})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Operations health clips horizontally"
            page.screenshot(path=str(args.output/f"source-ocr-health-{width}.png"), full_page=True)
        assert not errors,errors
        (args.output/'browser-result.json').write_text(json.dumps({'result':'passed','rows_reviewed':5,'viewports':[1280,390],'requests':1,'health_checks':'collector_success_and_ocr_failure_separate; no_horizontal_clipping','browser_errors':errors},indent=2))
        browser.close()

if __name__=='__main__':main()
