"""The day-0 starter workflows: what `store.init()` seeds by default, and
what `px0 init` does with them once they exist -- see px0/starters.py."""

import pytest

from px0 import (cli, connect as connect_mod, starters, store as store_mod,
                 tools as tools_mod, workflow as workflow_mod)


def test_store_init_seeds_three_read_only_starters(tmp_path):
    home = tmp_path / "store"
    created = store_mod.init(home)

    all_wfs = workflow_mod.load_all(home)
    assert set(all_wfs) == {"github-review-queue", "linear-my-issues", "slack-recent-activity"}
    for wf_id, wf in all_wfs.items():
        # validate() already enforces every input is read-only and every
        # tools[] entry exists; this just names the property the whole
        # day-0 promise depends on -- nothing pre-baked ever writes.
        assert not workflow_mod.validate(wf, home), f"{wf_id} failed to validate"
        for t in wf.tools:
            spec = tools_mod.resolve(t, home)
            assert spec is not None and not spec.is_write, f"{wf_id} offers a write tool: {t}"
        assert wf.output.get("target") == "inbox"
    assert any("workflows/github-review-queue.md" in line for line in created)


def test_store_init_can_skip_starter_content(tmp_path):
    home = tmp_path / "store"
    store_mod.init(home, starter_content=False)

    assert workflow_mod.load_all(home) == {}
    from px0 import catalogue
    assert catalogue.load_cached(home) == {}


def test_connect_starter_apps_skips_entirely_with_no_composio_key(tmp_path, capsys):
    home = tmp_path / "store"
    store_mod.init(home)
    before = (home / "workflows" / "github-review-queue.md").read_text()

    cli._connect_starter_apps(home)

    after = (home / "workflows" / "github-review-queue.md").read_text()
    assert before == after
    assert "skipping app connections" in capsys.readouterr().out


def test_connect_starter_apps_disables_a_declined_app(tmp_path, monkeypatch, fake_composio):
    home = tmp_path / "store"
    store_mod.init(home)
    connect_mod.setup_composio(home, "cmp_testkey")
    monkeypatch.setattr("builtins.input", lambda *_a: "n")

    cli._connect_starter_apps(home)

    wf = workflow_mod.parse(home / "workflows" / "github-review-queue.md")
    assert wf.enabled is False


def test_connect_starter_apps_runs_the_workflow_once_connected(tmp_path, monkeypatch, fake_composio):
    home = tmp_path / "store"
    store_mod.init(home)
    connect_mod.setup_composio(home, "cmp_testkey")
    monkeypatch.setattr("builtins.input", lambda *_a: "y")

    calls = []

    def fake_run(home, config, workflow_id, trigger="manual"):
        calls.append(workflow_id)
        return {"output": {"text": "nothing waiting on you"}}

    from px0 import runner
    monkeypatch.setattr(runner, "run", fake_run)

    cli._connect_starter_apps(home)

    assert calls == ["github-review-queue", "linear-my-issues", "slack-recent-activity"]
    wf = workflow_mod.parse(home / "workflows" / "github-review-queue.md")
    assert wf.enabled is True
