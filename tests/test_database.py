import asyncio
import stat
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from psycopg import OperationalError
from psycopg.conninfo import conninfo_to_dict

from app.core.database import database_conninfo
from app.persistent import main, run_persistent
from scripts.prepare_local_db import prepare


def test_default_connection_uses_local_password_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INCIDENT_LAB_DATABASE_URL", raising=False)
    settings = conninfo_to_dict(database_conninfo())
    assert settings["host"] == "127.0.0.1"
    assert settings["port"] == "5433"
    assert settings["user"] == "incident_lab"
    assert "password" not in settings
    passfile = settings["passfile"]
    assert isinstance(passfile, str)
    assert passfile.endswith("/.local/pgpass")


def test_empty_database_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INCIDENT_LAB_DATABASE_URL", " ")
    with pytest.raises(ValueError, match="não pode ser vazia"):
        database_conninfo()


def test_local_credentials_are_not_overwritten(tmp_path: Path) -> None:
    directory = tmp_path / ".local"
    prepare(directory)
    original = {path.name: path.read_bytes() for path in directory.iterdir()}
    prepare(directory)
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == original
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "pgpass").stat().st_mode) == 0o600
    assert original["admin_password"] != original["app_password"]


def test_cli_does_not_expose_database_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "app.persistent.run_persistent", AsyncMock(side_effect=OperationalError("private detail"))
    )
    assert main(["init"]) == 1
    output = capsys.readouterr()
    assert "Erro no PostgreSQL" in output.err
    assert "private detail" not in output.err


def test_cli_requires_explicit_resume_decision() -> None:
    with pytest.raises(SystemExit) as error:
        main(["resume", str(uuid4())])
    assert error.value.code == 2


def test_invalid_thread_id_does_not_open_database(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = AsyncMock(side_effect=AssertionError("Não deve conectar"))
    monkeypatch.setattr("app.persistent.open_checkpointer", connect)
    with pytest.raises(ValueError):
        asyncio.run(run_persistent("show", thread_id="../invalid"))
    connect.assert_not_called()
