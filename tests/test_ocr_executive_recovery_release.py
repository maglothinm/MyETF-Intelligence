"""The approved failure exception cannot enable OCR or expand mutation scope."""
import copy
import importlib.util
from pathlib import Path

import pytest

from scripts import ocr_executive_recovery_release as repair
from scripts import ocr_senate_pdf_release as senate
from scripts import ocr_oge_pdf_repair_release as pdf
from test_ocr_release_controller import c, recovered, snapshot
from test_ocr_health_repair_release import repair_case as health_case
from test_ocr_oge_pdf_repair_release import repair_case as pdf_case, new_engine, BUILD as FIXTURE_BUILD
from test_ocr_senate_pdf_release import case as senate_case


def incident(recovered=False):
    heads = {n:dict(snapshot_id=n, generation=10, source_revision=repair.PREVIOUS_SOURCE,
                    producer_run_id=n) for n in c.PRODUCERS}
    rows = [dict(namespace=n, run_id=n, status='success', finished_at='2026-09-19T16:00:00Z') for n in c.PRODUCERS]
    detail = dict(source=repair.PREVIOUS_SOURCE, error_code='CalledProcessError', snapshot_id=None, ocr=None)
    report = dict(heads=heads, latest_production_runs=rows, executive_recovery_detail=detail,
                  observed_at='2026-09-19T16:00:00Z', accounts=[], history={}, acknowledgements={},
                  review_events={}, completed_run_history={}, immutable_notifications={},
                  notification_events={}, public_tables=[], result='PASS', read_only=True)
    if recovered:
        heads['executive'].update(snapshot_id='new-executive', generation=11, source_revision=repair.SOURCE)
        detail.update(source=repair.SOURCE, error_code='', snapshot_id='new-executive')
        report.update(baseline_preservation_verified=True, executive_ocr_unchanged=True)
    else:
        next(r for r in rows if r['namespace']=='executive')['status']='failure'
    return report


@pytest.fixture
def case(senate_case, monkeypatch):
    case = senate_case
    case.procedure.prepare(c, case.root, FIXTURE_BUILD)
    folder = case.root / repair.PREVIOUS_WORKSPACE
    state = dict(status='recovered_new_image_ocr_disabled', source=repair.PREVIOUS_SOURCE,
                 image=repair.PREVIOUS_IMAGE, schedules_restored=True,
                 steps={'recovery-preservation': {'execution':'polititrack-admin-preserved'}})
    c.save(folder/'ocr-deployment/journal.json', state)
    c.save(folder/'ocr-deployment/recovery-preservation-receipt.json', dict(result='PASS', read_only=True,
           baseline_preservation_verified=True, execution='polititrack-admin-preserved'))
    monkeypatch.setattr(repair, 'PREVIOUS_SHA', pdf.digest(folder/'ocr-deployment/journal.json'))
    def parent():
        spec=importlib.util.spec_from_file_location('fresh_pdf_procedure', Path(pdf.__file__))
        proc=importlib.util.module_from_spec(spec); spec.loader.exec_module(proc)
        proc.COMPLETED_SHA=pdf.COMPLETED_SHA
        proc.load_health_wrapper=pdf.load_health_wrapper
        return senate.configure_procedure(proc)
    case.parent=parent
    case.procedure=repair.configure_procedure(parent())
    for name in c.RESOURCES:
        case.cloud[name]=case.procedure.completed_target(c,case.root,name)
    case.cloud['build'].update(id=repair.BUILD, substitutions={'_SOURCE_REVISION':repair.SOURCE})
    case.cloud['build']['results']['images'][0]['digest']=repair.IMAGE.split('@')[1]
    case.cloud['registry']['image_summary']['digest']=repair.IMAGE.split('@')[1]
    case.calls.clear()
    return case


def release_for(case):
    case.procedure.prepare(c,case.root,repair.BUILD)
    workspace=case.root/repair.RECOVERY_WORKSPACE
    engine=new_engine(case)
    case.procedure.configure_engine(engine,c,case.root,workspace)
    return engine,engine.Release(workspace,engine.load_audit_module())


def test_five_attempts_preserved_and_only_executive_target_changes(case):
    sealed=case.procedure.sealed_predecessors(c,case.root)
    assert sum(n.endswith('journal.json') for n in sealed)==5
    engine,release=release_for(case)
    for name in c.RESOURCES:
        if name=='polititrack-executive':
            target=release.target(name,True)  # even this cannot enable OCR
            assert c.container(target,name)['image']==repair.IMAGE
            assert {e['name']:e.get('value') for e in c.container(target,name)['env']}['RUNTIME_SOURCE_OCR_ENABLED']=='false'
        else:
            assert release.target(name,True)==release.original[name]
            with pytest.raises(engine.Stop,match='only Executive'):
                release.update(name)
    with pytest.raises(engine.Stop,match='only Executive'):
        release.update('polititrack-executive',True)
    assert case.procedure.sealed_predecessors(c,case.root)==sealed
    assert not (release.folder/'baseline-receipt.json').exists()


@pytest.mark.parametrize('namespace',c.PRODUCERS)
def test_incident_rejects_unfinished_or_unrelated_failure(namespace):
    report=incident()
    row=next(r for r in report['latest_production_runs'] if r['namespace']==namespace)
    row['status']='running' if namespace=='executive' else 'failure'
    with pytest.raises(c.Stop,match='Unrelated or unfinished'):
        repair.validate_incident(c,report)


@pytest.mark.parametrize('change',[{'source':'other'},{'error_code':'other'},{'snapshot_id':'unexpected'},
                                    {'ocr':{'enabled':True,'stage':'skipped'}}])
def test_incident_rejects_different_executive_failure(change):
    report=incident(); report['executive_recovery_detail'].update(change)
    with pytest.raises(c.Stop,match='reviewed OCR-disabled failure'):
        repair.validate_incident(c,report)


@pytest.mark.parametrize('change',['preservation','ocr','source','other_head','old_generation','wrong_run'])
def test_recovery_acceptance_cannot_certify_unproven_success(change):
    report=incident(True)
    if change=='preservation': report['baseline_preservation_verified']=False
    if change=='ocr': report['executive_recovery_detail']['ocr']={'enabled':True}
    if change=='source': report['executive_recovery_detail']['source']='wrong'
    if change=='other_head': report['heads']['ai']['snapshot_id']='unexpected'
    if change=='old_generation': report['heads']['executive']['generation']=10
    if change=='wrong_run': report['heads']['executive']['producer_run_id']='old'
    with pytest.raises(c.Stop):
        repair.validate_incident(c,report,recovered=True,baseline=incident())


def test_recovery_success_and_resumption_never_dispatch_another_producer(case,monkeypatch):
    engine,release=release_for(case)
    calls=[]
    monkeypatch.setattr(release,'preflight',lambda:release.state.update(status='ready'))
    monkeypatch.setattr(release,'active',lambda **kw:None)
    monkeypatch.setattr(release,'pause',lambda:release.state.update(status='maintenance',paused=['polititrack-'+n for n in c.PRODUCERS]))
    monkeypatch.setattr(release,'drain',lambda **kw:None)
    monkeypatch.setattr(release,'scheduler_rows',lambda label:{'polititrack-'+n:{'state':'PAUSED'} for n in c.PRODUCERS})
    monkeypatch.setattr(release,'verify_resources',lambda **kw:None)
    monkeypatch.setattr(release,'update',lambda name,*a,**kw:calls.append(('update',name,kw)))
    def audit(key,**kw):
        assert kw['old_image'] is True
        report=incident(key=='incident-acceptance')
        c.save(release.folder/(key+'-receipt.json'),report)
        return report
    monkeypatch.setattr(release,'audit',audit)
    monkeypatch.setattr(release,'compact_baseline',lambda x:x)
    # The retained fixture audit has no accounts; use matching inventory for this flow.
    monkeypatch.setattr(engine,'load',lambda path: {'accounts':[]} if str(path).endswith('state-audit/receipt.json') else c.load(path))
    monkeypatch.setattr(release,'execute',lambda key,job,args,**kw:calls.append(('execute',job,args,kw)))
    monkeypatch.setattr(release,'resume_schedules',lambda:release.state.update(schedules_restored=True))
    release.run()
    assert release.state['status']=='complete' and release.state['ocr_activation_performed'] is False
    assert [x[1] for x in calls]==['polititrack-executive','polititrack-executive']
    assert calls[1][2]==['-m','runtime_v2','run','executive'] and calls[1][3]['expected_image']==repair.IMAGE
    before=copy.deepcopy(calls); release.run(); assert calls==before
    release.state['status']='incident_installed_ocr_disabled'
    release.run(); assert calls==before  # resume schedule restoration only


def test_activation_seals_completed_incident_and_keeps_normal_gate(case,monkeypatch):
    engine,release=release_for(case)
    baseline,receipt=incident(),incident(True)
    receipt['execution']='polititrack-admin-accepted'
    c.save(release.folder/'incident-baseline-receipt.json',baseline)
    c.save(release.folder/'incident-acceptance-receipt.json',receipt)
    release.state.update(status='complete',approval=repair.APPROVAL,executive_recovery_verified=True,
        ocr_activation_performed=False,schedules_restored=True,steps={'incident-acceptance':{'execution':receipt['execution']}})
    release.persist()
    sha=pdf.digest(release.path)
    proc=repair.configure_procedure(case.parent(),activation=True,incident_sha=sha)
    for name in c.RESOURCES: case.cloud[name]=proc.completed_target(c,case.root,name)
    proc.prepare(c,case.root,repair.BUILD)
    folder=case.root/repair.ACTIVATION_WORKSPACE
    assert sum(n.endswith('journal.json') for n in c.load(folder/'predecessors.json'))==6
    normal=new_engine(case); proc.configure_engine(normal,c,case.root,folder)
    assert normal.Release.run.__code__.co_code==c.Release.run.__code__.co_code
    assert normal.AUDIT_EXTRA==c.AUDIT_EXTRA
    assert not (folder/'ocr-deployment').exists()
    # A completed incident cannot be edited after the activation preparation.
    release.path.write_bytes(release.path.read_bytes()+b'\n')
    with pytest.raises(c.Stop,match='incident journal differs'):
        proc.configure_engine(new_engine(case),c,case.root,folder)


def test_old_build_and_changed_fifth_journal_are_rejected_before_cloud_reads(case):
    with pytest.raises(c.Stop,match='reviewed tested build'):
        case.procedure.prepare(c,case.root,FIXTURE_BUILD)
    path=case.root/repair.PREVIOUS_WORKSPACE/'ocr-deployment/journal.json'
    path.write_bytes(path.read_bytes()+b'\n')
    before=snapshot(case.root)
    with pytest.raises(c.Stop,match='fifth closed journal changed'):
        case.procedure.prepare(c,case.root,repair.BUILD)
    assert not case.calls and snapshot(case.root)==before


@pytest.mark.parametrize('submitted',[False,True])
def test_failed_incident_restores_schedules_without_touching_other_resources(case,monkeypatch,submitted):
    engine,release=release_for(case)
    release.state.update(status='incident_installed_ocr_disabled',paused=['polititrack-executive'],
                         producer_submission_started=submitted)
    c.save(release.folder/'incident-baseline-receipt.json',incident())
    calls=[]
    monkeypatch.setattr(release,'drain',lambda **kw:calls.append('drain'))
    monkeypatch.setattr(release,'verify_resources',lambda **kw:calls.append('verify'))
    monkeypatch.setattr(release,'audit',lambda key,**kw:calls.append((key,kw)))
    monkeypatch.setattr(release,'update',lambda name,**kw:calls.append((name,kw)))
    monkeypatch.setattr(release,'resume_schedules',lambda:release.state.update(schedules_restored=True))
    release.recover()
    assert release.state['status']=='recovered_executive_ocr_disabled'
    assert release.state['schedules_restored'] is True
    assert calls[:2]==['drain','verify']
    assert calls[-1]==('polititrack-executive',{} if submitted else {'restore':True})
    if submitted:
        assert calls[2][0]=='incident-recovery-preservation' and calls[2][1]['old_image'] is True
    assert c.closed(release.state)


def test_actual_pinned_procedure_loads_and_activation_requires_exact_sha():
    assert repair.configure_procedure(repair.load_procedure()).SOURCE==repair.SOURCE
    for activation,sha in ((True,None),(False,'a'*64),(True,'wrong')):
        with pytest.raises(RuntimeError,match='exact completed incident'):
            repair.configure_procedure(repair.load_procedure(),activation=activation,incident_sha=sha)
