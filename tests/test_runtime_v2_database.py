import pytest

from runtime_v2 import database


class _Connector:
    def __init__(self):
        self.calls = []

    def connect(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return object()


def test_cloud_sql_private_ip_is_explicit(monkeypatch):
    from google.cloud.sql.connector import IPTypes

    connector = _Connector()
    monkeypatch.setattr(database, "_cloud_connector", lambda: connector)

    database.connect(
        {
            "INSTANCE_CONNECTION_NAME": "project:region:instance",
            "DB_NAME": "polititrack",
            "DB_USER": "polititrack_runtime",
            "DB_PASSWORD": "secret",
            "PRIVATE_IP": "true",
        }
    )

    _args, kwargs = connector.calls[-1]
    assert kwargs["ip_type"] == IPTypes.PRIVATE
    assert kwargs["enable_iam_auth"] is False


def test_cloud_sql_public_ip_is_not_selected_when_private_requested(monkeypatch):
    from google.cloud.sql.connector import IPTypes

    connector = _Connector()
    monkeypatch.setattr(database, "_cloud_connector", lambda: connector)

    database.connect(
        {
            "INSTANCE_CONNECTION_NAME": "project:region:instance",
            "DB_NAME": "polititrack",
            "DB_USER": "service-account@project.iam",
            "PRIVATE_IP": "1",
        }
    )

    _args, kwargs = connector.calls[-1]
    assert kwargs["ip_type"] == IPTypes.PRIVATE
    assert kwargs["enable_iam_auth"] is True


def test_cloud_sql_private_ip_rejects_ambiguous_values():
    with pytest.raises(database.DatabaseConfigurationError, match="PRIVATE_IP"):
        database._use_private_ip({"PRIVATE_IP": "sometimes"})
