"""Keep the full release gates while tolerating only the observed status-read error."""
import hashlib
from types import SimpleNamespace

import pytest

from scripts import ocr_activation_read_recovery_release as continuation
from scripts import ocr_executive_recovery_release as repair
from scripts import ocr_oge_pdf_repair_release as pdf
from test_ocr_release_controller import c, snapshot, recovered
from test_ocr_oge_pdf_repair_release import new_engine
from test_ocr_executive_recovery_release import (
    case as executive_case, release_for, incident, health_case, pdf_case, senate_case)

TOKEN_ERROR = 'ERROR: UNAUTHENTICATED: Request had invalid authentication credentials.\n  reason: ACCESS_TOKEN_TYPE_UNSUPPORTED\n'
OBSERVE = ('run','jobs','executions','describe','polititrack-executive-tested','--region='+c.REGION)


@pytest.fixture
def case(executive_case, monkeypatch):
    case = executive_case
    engine, release = release_for(case)
    baseline, receipt = incident(), incident(True)
    receipt['execution'] = 'polititrack-admin-accepted'
    c.save(release.folder/'incident-baseline-receipt.json', baseline)
    c.save(release.folder/'incident-acceptance-receipt.json', receipt)
    release.state.update(status='complete', approval=repair.APPROVAL, executive_recovery_verified=True,
        ocr_activation_performed=False, schedules_restored=True,
        steps={'incident-acceptance':{'execution':receipt['execution']}})
    release.persist()
    sha = pdf.digest(release.path)
    monkeypatch.setattr(continuation, 'INCIDENT_SHA', sha)
    prior = repair.configure_procedure(case.parent(), activation=True, incident_sha=sha)
    for name in c.RESOURCES:
        case.cloud[name] = prior.completed_target(c, case.root, name)
    prior.prepare(c, case.root, repair.BUILD)
    folder = case.root/continuation.PREVIOUS_WORKSPACE/'ocr-deployment'
    state = dict(status='recovered_new_image_ocr_disabled', source=repair.SOURCE, image=repair.IMAGE,
        schedules_restored=True, installation_verified=True, activation_verified=True,
        producer_submission_started=True, last_error=continuation.READ_ERROR,
        steps={'recovery-preservation':{'execution':'polititrack-admin-preserved'}})
    c.save(folder/'journal.json', state)
    c.save(folder/'recovery-preservation-receipt.json', dict(result='PASS', read_only=True,
        baseline_preservation_verified=True, execution='polititrack-admin-preserved'))
    (folder/'cloud').mkdir()
    (folder/'cloud/observe-executive-1.stderr.txt').write_text(TOKEN_ERROR)
    monkeypatch.setattr(repair, 'load_procedure', case.parent)
    case.procedure = continuation.configure_procedure(repair, predecessor_sha=pdf.digest(folder/'journal.json'))
    for name in c.RESOURCES:
        case.cloud[name] = case.procedure.completed_target(c, case.root, name)
    case.calls.clear()
    return case


def test_seven_attempts_sealed_and_all_original_acceptance_gates_unchanged(case):
    before = case.procedure.sealed_predecessors(c, case.root)
    assert sum(n.endswith('journal.json') for n in before) == 7
    case.procedure.prepare(c, case.root, repair.BUILD)
    workspace = case.root/continuation.WORKSPACE_NAME
    engine = new_engine(case)
    case.procedure.configure_engine(engine,c,case.root,workspace)
    for method in ('run','execute','audit','recover','update','verify_live'):
        assert getattr(engine.Release,method).__code__.co_code == getattr(c.Release,method).__code__.co_code
    assert engine.AUDIT_EXTRA == c.AUDIT_EXTRA
    assert not (workspace/'ocr-deployment').exists()
    assert case.procedure.sealed_predecessors(c,case.root) == before
    for name in c.RESOURCES:
        target = case.procedure.completed_target(c,case.root,name)
        assert c.container(target,name)['image'] == repair.IMAGE
        if name in c.OCR_RESOURCES:
            assert {e['name']:e.get('value') for e in c.container(target,name)['env']}['RUNTIME_SOURCE_OCR_ENABLED']=='false'


@pytest.mark.parametrize('change', [dict(status='enabled_verifying'), dict(schedules_restored=False),
    dict(acceptance_verified=True), dict(recovery_error='error'), dict(last_error='different'),
    dict(source='other'), dict(installation_verified=False)])
def test_unreviewed_recovery_cannot_continue(case,monkeypatch,change):
    path=case.root/continuation.PREVIOUS_WORKSPACE/'ocr-deployment/journal.json'
    state=c.load(path); state.update(change); c.save(path,state)
    case.procedure=continuation.configure_procedure(repair,predecessor_sha=pdf.digest(path))
    before=snapshot(case.root)
    with pytest.raises(c.Stop,match='reviewed observation recovery'):
        case.procedure.prepare(c,case.root,repair.BUILD)
    assert snapshot(case.root)==before and not case.calls


def test_changed_seventh_evidence_blocks_persistence(case):
    case.procedure.prepare(c,case.root,repair.BUILD)
    workspace=case.root/continuation.WORKSPACE_NAME
    engine=new_engine(case);case.procedure.configure_engine(engine,c,case.root,workspace)
    release=engine.Release(workspace,engine.load_audit_module())
    path=case.root/continuation.PREVIOUS_WORKSPACE/'ocr-deployment/cloud/observe-executive-1.stderr.txt'
    path.write_text(TOKEN_ERROR+'changed\n')
    before=release.path.read_bytes()
    with pytest.raises(c.Stop,match='evidence changed'):
        release.persist()
    assert release.path.read_bytes()==before


@pytest.fixture
def reader(tmp_path,monkeypatch):
    calls=[]; sleeps=[]; answers=[]
    class Original:
        def __init__(self):
            self.folder=tmp_path; self.state={}; self.saved=0
        def persist(self): self.saved+=1
        def gcloud(self,label,*args,timeout=180):
            calls.append((label,args,timeout))
            answer=answers.pop(0)
            if isinstance(answer,Exception): raise answer
            if isinstance(answer,str):
                path=self.folder/'cloud'/(label+'.stderr.txt');path.parent.mkdir(exist_ok=True)
                path.write_text(answer)
                raise c.Stop('read failed')
            return answer
    engine=SimpleNamespace(Release=Original,Stop=c.Stop,REGION=c.REGION,timestamp=lambda:'now')
    continuation.install_read_retry(engine)
    monkeypatch.setattr(continuation.time,'sleep',sleeps.append)
    return SimpleNamespace(release=engine.Release(),calls=calls,sleeps=sleeps,answers=answers)


def test_retry_exact_read_three_times_without_losing_any_diagnostic(reader):
    reader.answers[:]=[TOKEN_ERROR,TOKEN_ERROR,{'success':True},{'success':True}]
    assert reader.release.gcloud('observe-executive-1',*OBSERVE)=={'success':True}
    assert reader.sleeps==[2,5] and len(reader.calls)==3
    assert all(args==OBSERVE for _,args,_ in reader.calls)
    events=reader.release.state['observation_read_retries']
    assert len(events)==2 and all(e['retry_planned'] for e in events)
    for event in events:
        p=reader.release.folder/event['diagnostic']
        assert p.read_text()==TOKEN_ERROR and hashlib.sha256(p.read_bytes()).hexdigest()==event['diagnostic_sha256']
    reader.release.gcloud('observe-executive-1',*OBSERVE)
    assert len({label for label,_,_ in reader.calls})==4
    assert all((reader.release.folder/e['diagnostic']).read_text()==TOKEN_ERROR for e in events)


def test_repeated_rejection_stops_after_three_reads(reader):
    reader.answers[:]=[TOKEN_ERROR]*3
    with pytest.raises(c.Stop):reader.release.gcloud('observe-executive-1',*OBSERVE)
    assert len(reader.calls)==3 and reader.sleeps==[2,5]
    assert reader.release.state['observation_read_retries'][-1]['retry_planned'] is False


@pytest.mark.parametrize('args', [
    ('run','jobs','execute','polititrack-executive'),
    ('run','jobs','update','polititrack-executive'),
    ('scheduler','jobs','resume','polititrack-executive'),
    ('run','jobs','executions','describe','unknown-job','--region='+c.REGION),
    (*OBSERVE,'--other-flag'),
])
def test_mutations_and_other_reads_are_never_retried(reader,args):
    reader.answers[:]=[TOKEN_ERROR]
    with pytest.raises(c.Stop):reader.release.gcloud('observe-executive-1',*args)
    assert len(reader.calls)==1 and not reader.sleeps and not reader.release.state


@pytest.mark.parametrize('error', [
    'PERMISSION_DENIED: denied\nreason: ACCESS_TOKEN_TYPE_UNSUPPORTED\n',
    'UNAUTHENTICATED: credentials expired\nreason: ACCESS_TOKEN_EXPIRED\n',
    'UNAUTHENTICATED: unsupported\nreason: OTHER\n',
    'UNAVAILABLE: service unavailable',
    c.Waiting('timed out'),
])
def test_unrecognized_errors_and_timeouts_keep_original_stop_behavior(reader,error):
    reader.answers[:]=[error]
    with pytest.raises((c.Stop,c.Waiting)):reader.release.gcloud('observe-executive-1',*OBSERVE)
    assert len(reader.calls)==1 and not reader.sleeps and not reader.release.state


def test_failed_job_response_is_returned_unchanged_for_normal_failure_gate(reader):
    result={'status':{'conditions':[{'type':'Completed','status':'False'}]}}
    reader.answers[:]=[result]
    assert reader.release.gcloud('observe-executive-1',*OBSERVE) is result
    assert len(reader.calls)==1 and not reader.sleeps


def test_actual_pinned_procedure_loads_without_cloud_side_effects():
    assert continuation.configure_procedure(continuation.load_procedure(),predecessor_sha='0'*64).SOURCE==repair.SOURCE
    for value in (None,'wrong','A'*64):
        with pytest.raises(RuntimeError,match='exact completed'):
            continuation.configure_procedure(repair,predecessor_sha=value)


def test_wrong_closed_hash_stops_before_cloud_reads(case):
    case.procedure=continuation.configure_procedure(repair,predecessor_sha='0'*64)
    before=snapshot(case.root)
    with pytest.raises(c.Stop,match='seventh closed journal changed'):
        case.procedure.prepare(c,case.root,repair.BUILD)
    assert snapshot(case.root)==before and not case.calls
