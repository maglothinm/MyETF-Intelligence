"""Generate isolated TEST-only root/standalone previews and browser evidence.

No collectors, providers, production state, credentials or external calls are
used. Browser traffic is restricted to the local fixture server.
"""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_trade_dashboard import build_payload, build_site, load_branch
from scripts.investor_edge import build_dashboard_addon
from scripts.investor_edge_progress import CATEGORIES


def build_preview(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    ai=output.parent/'fixture-ai'; ai.mkdir(exist_ok=True)
    now=datetime.now(timezone.utc).isoformat()
    categories=['ready','queued','awaiting_maturity','awaiting_retry','missing_data','blocked']
    reasons=['cached_work_ready','unattempted','outcome_not_mature','daily_attempt_limit','prices_missing_or_stale','no_market_credentials']
    counts={key: categories.count(key) for key in CATEGORIES}; counts['completed']=12
    profiles=[{'investor_key':f'test-{i}|self','filer':f'TEST Investor {i+1}','owner':'Self','sample_count':0,'minimum_sample_met':False,'status':'insufficient_data','confidence_label':'Low','backfill_pending_trade_count':1} for i in range(len(categories))]
    progress={'schema_version':1,'as_of_date':now[:10],'counts':counts,'total_observations':sum(counts.values()),'status':'blocked','last_successful_run_at':now,'last_advancement_at':now,'advanced_in_last_run':4,'completed_in_last_run':2,'stalled_successful_runs':0,'evidence_stale':False,'stale_after_minutes':75,'next_retry_at':None,'next_scheduled_run_at':None,'eta':None,'details_truncated':False,'detail_total':len(categories),'details':[{'category':category,'reason_code':reasons[i],'investor':profile['filer'],'owner':'Self','ticker':f'TEST{i}','profile_index':i,'trade_id':f'TEST-{i}','missing_outcome_count':3} for i,(category,profile) in enumerate(zip(categories,profiles))]}
    metadata={'generated_utc':now,'investors':profiles,'backfill_progress':progress,'published_profile_count':len(profiles),'completed_profile_count':0,'building_profile_count':len(profiles),'historical_transaction_count':18,'eligible_purchase_count':18,'unique_investor_identity_count':len(profiles),'backfill_processed_this_run':4,'backfill_pending_observation_count':6,'backfill_limit_per_run':30,'network_requests_this_run':4,'branch_transaction_counts':{'legislative':18,'executive':0}}
    (ai/'investor-edge-leaderboard.json').write_text(json.dumps(metadata),encoding='utf-8')
    payload=build_payload(load_branch(None,'legislative'),load_branch(None,'executive'),repository_url='https://example.test/TEST-fixture')
    build_site(payload,output)
    build_dashboard_addon(ai,output)


def capture(output: Path, evidence: Path) -> None:
    from playwright.sync_api import sync_playwright
    evidence.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(output)))
    Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    errors=[]; checks=[]
    try:
        with sync_playwright() as driver:
            browser=driver.chromium.launch()
            for width in [1280,700,390]:
                for route in ['/#investor-edge','/investor-edge.html']:
                    page=browser.new_page(viewport={'width':width,'height':900})
                    page.route('**/*',lambda request: request.continue_() if request.request.url.startswith(origin+'/') else request.abort())
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(origin+route)
                    page.locator('#edge-backfill-detail .edge-progress-panel').wait_for()
                    page.locator('.edge-progress-details summary').click()
                    page.locator('#backfill-state-filter').select_option('missing_data')
                    assert page.locator('tr[data-backfill-category]:visible').count()==1
                    page.locator('#backfill-state-filter').select_option('all')
                    assert page.locator('tr[data-backfill-category]:visible').count()==6
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    name=('root' if route.startswith('/#') else 'standalone')+f'-{width}'
                    page.locator('#edge-backfill-detail').screenshot(path=str(evidence/f'{name}.png'))
                    checks.append({'view':name,'responsive':True,'filters':True})
                    page.close()
            browser.close()
    finally:
        server.shutdown(); server.server_close()
    assert not errors,errors
    (evidence/'browser-acceptance.json').write_text(json.dumps({'fixture':'TEST only; no production data','checks':checks,'errors':errors},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--screenshots',type=Path)
    args=parser.parse_args();build_preview(args.output)
    if args.screenshots:capture(args.output,args.screenshots)
