"""Owner-run free Massive key setup and read-only capability probe.

No account creation, payment, activation flags, notifications or portfolio writes.
The API key is entered without echo; it is never a command-line argument or log.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from getpass import getpass
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.opportunity_common import DataUnavailable, load_rules, utc, write_json
from scripts.opportunity_massive import MassiveHistory, SharedPacer
from scripts.opportunity_providers import RequestBudget


def private_key_file(path: Path, key: str):
    """Create a new owner/SYSTEM/admin-only credential file; never overwrite a key."""
    if path.exists():
        raise ValueError('Credential path already exists; no file was overwritten.')
    path.parent.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        import win32api,win32con,win32file,win32security,pywintypes
        token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
        try:owner=win32security.GetTokenInformation(token,win32security.TokenUser)[0]
        finally:token.Close()
        acl=win32security.ACL()
        for sid in (owner,win32security.CreateWellKnownSid(win32security.WinLocalSystemSid,None),win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid,None)):
            acl.AddAccessAllowedAce(win32security.ACL_REVISION,win32con.GENERIC_ALL,sid)
        sd=win32security.SECURITY_DESCRIPTOR();sd.SetSecurityDescriptorDacl(1,acl,0)
        sd.SetSecurityDescriptorControl(win32security.SE_DACL_PROTECTED,win32security.SE_DACL_PROTECTED)
        sa=pywintypes.SECURITY_ATTRIBUTES();sa.SECURITY_DESCRIPTOR=sd
        handle=win32file.CreateFile(str(path),win32con.GENERIC_WRITE,0,sa,win32con.CREATE_NEW,win32con.FILE_ATTRIBUTE_NORMAL,None)
        try:win32file.WriteFile(handle,json.dumps({'provider':'massive','plan':'stocks_basic_free','api_key':key}).encode())
        finally:handle.Close()
    else:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump({'provider':'massive','plan':'stocks_basic_free','api_key':key},f)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New isolated probe directory, outside app/config/production state.')
    parser.add_argument('--pacing-path',type=Path,required=True,help='Shared PolitiTrack Massive pacing DB; never inside a source snapshot.')
    parser.add_argument('--symbol',default='MSFT')
    args=parser.parse_args(argv)
    source_root=Path(__file__).resolve().parents[1]
    if args.key_file.resolve().is_relative_to(source_root) or args.output.resolve().is_relative_to(source_root):
        parser.error('Credentials and probe outputs must remain outside the source checkout.')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Use a new empty probe output directory.')
    args.output.mkdir(parents=True,exist_ok=True)
    existing=args.key_file.exists()
    env={'MASSIVE_RATE_LIMIT_PATH':str(args.pacing_path)}
    if existing:
        env['MASSIVE_API_KEY_FILE']=str(args.key_file)
    else:
        print('Use a free Massive Stocks Basic account. No card, subscription or paid upgrade will be requested by this helper.')
        key=getpass('Paste the Massive API key (hidden): ').strip()
        env['MASSIVE_API_KEY']=key
    clock=lambda:datetime.now(timezone.utc)
    config=SimpleNamespace(ai_dir=args.output/'derived-cache',request_timeout=(10,45))
    rules=load_rules(mode='off');rules['massive_requests_per_run']=8
    receipt={'observed_at':utc(clock()),'scope':'Read-only Massive free-data probe; not production activation or Finnhub entitlement verification.',
        'mode':'isolated_probe','symbol':args.symbol,'success':False,'subscription_purchased':False,'capability_flags_written':False}
    try:
        client=MassiveHistory(config,rules,clock,RequestBudget(8),environment=env)
        metadata=client.metadata(args.symbol,clock().date().isoformat())
        if metadata['type']!='CS' or metadata['active'] is not True or metadata['primary_exchange'] not in ('XNYS','XNAS'):
            raise DataUnavailable('probe_requires_active_US_common_stock')
        row={'ticker':args.symbol,'security_id':metadata['composite_figi'],'share_class':metadata['share_class_figi'],'currency':'USD'}
        history=client.history(row,clock())
        receipt.update(success=True,metadata=metadata,bar_count=len(history['bars']),
            history_start=history['bars'][0]['date'],history_end=history['bars'][-1]['date'],
            basis=history['basis'],session_scope=history['history_session_scope'],
            split_count=sum(a['kind']=='split' for a in history['adjustment_events']),
            dividend_count=sum(a['kind']=='dividend' for a in history['adjustment_events']),
            requests=client.requests,provider_pages=history['source_pages'])
        if not existing:
            private_key_file(args.key_file,key)
        receipt['credential_file_saved']=True
    except DataUnavailable as exc:
        receipt['reason']=str(exc)
    except Exception as exc:
        receipt['success']=False
        receipt['reason']='local_setup_failed:'+type(exc).__name__
    write_json(args.output/'massive-probe.json',receipt)
    print(json.dumps(receipt,indent=2))
    if not receipt['success']:
        return 2
    print('Free data response verified for this symbol. Production remains unchanged; source identities, Finnhub capability and normal release acceptance are still required.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
