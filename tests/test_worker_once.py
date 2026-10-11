import json

import pytest

import worker_once as cli


@pytest.fixture
def configured(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    job_root = tmp_path / "jobs"
    monkeypatch.setattr(cli, "require_container_pid1", lambda: None)
    argv = ["--job-root", str(job_root), "--data-root", str(data)]
    return job_root, data, argv


def test_non_pid1_launch_is_rejected_before_database(
    tmp_path, monkeypatch, capsys
):
    job_root = tmp_path / "jobs"
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setattr(cli.os, "getpid", lambda: 123)
    assert cli.main(["--job-root", str(job_root)]) == 2
    assert not job_root.exists()
    assert "PID 1" in capsys.readouterr().err


def test_pid1_gate_accepts_linux_pid1(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setattr(cli.os, "getpid", lambda: 1)
    cli.require_container_pid1()


def test_pid1_gate_rejects_other_platform(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "unsupported")
    monkeypatch.setattr(cli.os, "getpid", lambda: 1)
    with pytest.raises(cli.LaunchContractError):
        cli.require_container_pid1()


@pytest.mark.parametrize("extra", [
    ["--timeout", "0"],
    ["--timeout", "nan"],
    ["--timeout", "inf"],
    ["--grace", "-1"],
    ["--max-queued", "0"],
    ["--max-queued", "1.5"],
])
def test_invalid_configuration_does_not_create_database(configured, extra):
    job_root, data, argv = configured
    with pytest.raises(SystemExit) as exc:
        cli.main(argv + extra)
    assert exc.value.code == 2
    assert not job_root.exists()


def test_missing_data_does_not_create_database(configured):
    job_root, data, argv = configured
    data.rmdir()
    assert cli.main(argv) == 2
    assert not job_root.exists()


def test_symlink_job_root_is_rejected(configured):
    job_root, data, argv = configured
    target = job_root.parent / "target"
    target.mkdir()
    job_root.symlink_to(target, target_is_directory=True)
    assert cli.main(argv) == 2
    assert list(target.iterdir()) == []


def test_empty_queue_reports_idle(configured, capsys):
    job_root, data, argv = configured
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"state": "idle"}
    assert (job_root / "state" / "jobs.sqlite3").exists()


@pytest.mark.parametrize("state,code,exit_code", [
    ("completed", None, 0),
    ("failed", "RENDER_FAILED", 1),
])
def test_result_output_is_allowlisted(
    configured, monkeypatch, capsys, state, code, exit_code
):
    job_root, data, argv = configured
    captured = {}

    def fake_run_one(store, **kwargs):
        captured.update(kwargs)
        return {
            "job_id": "a" * 32,
            "state": state,
            "error_code": code,
            "request": {"private": "settings"},
            "diagnostic": "PRIVATE_DIAGNOSTIC",
        }

    monkeypatch.setattr(cli, "run_one", fake_run_one)
    assert cli.main(argv + ["--timeout", "42", "--grace", "0.2"]) == exit_code
    assert json.loads(capsys.readouterr().out) == {
        "job_id": "a" * 32, "state": state, "error_code": code,
    }
    assert captured["workspace_root"] == job_root / "private"
    assert captured["published_root"] == job_root / "published"
    assert captured["cache_root"] == job_root / "cache"
    assert captured["data_root"] == data
    assert captured["timeout"] == 42
    assert captured["grace"] == 0.2
    assert "renderer" not in captured


def test_competing_owner_returns_temporary_failure(
    configured, monkeypatch, capsys
):
    job_root, data, argv = configured

    def occupied(*args, **kwargs):
        raise cli.WorkerAlreadyRunning("private diagnostic")

    monkeypatch.setattr(cli, "run_one", occupied)
    assert cli.main(argv) == 75
    assert "private diagnostic" not in capsys.readouterr().err


def test_unexpected_failure_propagates(configured, monkeypatch):
    job_root, data, argv = configured

    def unavailable(*args, **kwargs):
        raise OSError("simulated infrastructure failure")

    monkeypatch.setattr(cli, "run_one", unavailable)
    with pytest.raises(OSError, match="infrastructure failure"):
        cli.main(argv)
