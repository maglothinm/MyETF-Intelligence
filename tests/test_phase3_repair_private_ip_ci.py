from pathlib import Path


def test_private_ip_repair_ci_runs_gate_tests_and_repository_contract() -> None:
    text = Path('.github/workflows/phase3_repair_private_ip_tests.yml').read_text(encoding='utf-8')
    assert 'pull_request:' in text
    assert 'tests/test_phase3_repair_private_ip_and_accept.py' in text
    assert 'tests/test_phase3_current_state_acceptance.py' in text
    assert 'tests/test_phase3_harvest_current_status.py' in text
    assert 'bash verify.sh' in text
