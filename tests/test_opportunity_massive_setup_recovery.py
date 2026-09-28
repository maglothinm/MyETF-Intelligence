"""Setup recovery tests use fake responses, never real credentials or services."""
import json
from types import SimpleNamespace
import pytest
from test_opportunity_massive import client,Response
from scripts.opportunity_common import DataUnavailable
from scripts import opportunity_massive_setup as setup


def test_http_diagnostic_redacts_secret_and_keeps_endpoint(tmp_path):
    key='TEST-NOT-A-REAL-KEY'
    c=client(tmp_path,[Response({'status':'ERROR','message':'invalid date; '+key+' apiKey=SECOND-SECRET https://example.test/?key=SECRET'},400)])
    with pytest.raises(DataUnavailable,match='400'):
        c.metadata('TEST')
    text=json.dumps(c.last_error)
    assert key not in text and 'SECOND-SECRET' not in text and 'key=SECRET' not in text
    assert c.last_error['path']=='/v3/reference/tickers/TEST'
    assert 'invalid date' in c.last_error['message']


def test_latest_metadata_omits_optional_date(tmp_path):
    c=client(tmp_path,[{'status':'OK','results':{'ticker':'TEST','market':'stocks','locale':'us','composite_figi':'TESTFIGI','share_class_figi':'TESTCLASS','currency_name':'USD'}}])
    c.metadata('TEST')
    assert c.session.calls[0][1]['params'] is None


def test_failed_probe_retains_private_key_and_diagnostic(tmp_path,monkeypatch):
    private=tmp_path/'private.json';out=tmp_path/'probe'
    monkeypatch.setattr(setup,'getpass',lambda _: 'TEST-OWNER-KEY')
    def create(path,key):
        path.write_text(json.dumps({'provider':'massive','plan':'stocks_basic_free','api_key':key}))
    monkeypatch.setattr(setup,'private_key_file',create)
    class Fake:
        def __init__(self,*a,**kw):
            assert private.exists()
            self.last_error={'path':'/v3/reference/tickers/MSFT','http_status':400,'message':'invalid date'}
            self.last_request={}
        def metadata(self,ticker):raise DataUnavailable('massive_http_400')
    monkeypatch.setattr(setup,'MassiveHistory',Fake)
    assert setup.main(['--key-file',str(private),'--output',str(out),'--pacing-path',str(tmp_path/'pacing')])==2
    receipt=json.loads((out/'massive-probe.json').read_text())
    assert receipt['success'] is False and receipt['credential_file_saved'] is True
    assert receipt['stage']=='latest_security_metadata'
    assert 'TEST-OWNER-KEY' not in json.dumps(receipt)
    assert private.exists()
