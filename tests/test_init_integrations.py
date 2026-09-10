"""Tests for issue tracker and Slack messaging prompts in px0 init."""

from unittest.mock import patch

from px0 import cli, credentials as creds_mod, store as store_mod


def test_prompt_issue_tracker_linear(tmp_path):
    store_mod.init(tmp_path, starter_content=False)

    with patch("px0.ui.select", return_value=0), \
         patch("px0.ui.prompt", return_value="lin_api_key_12345"):
        cli._prompt_issue_tracker(tmp_path)

    creds = creds_mod.load(tmp_path)
    assert creds.get("linear", {}).get("api_key") == "lin_api_key_12345"


def test_prompt_issue_tracker_github(tmp_path):
    store_mod.init(tmp_path, starter_content=False)

    with patch("px0.ui.select", return_value=1), \
         patch("px0.ui.prompt", return_value="ghp_pat_token_67890"):
        cli._prompt_issue_tracker(tmp_path)

    creds = creds_mod.load(tmp_path)
    assert creds.get("github", {}).get("token") == "ghp_pat_token_67890"


def test_prompt_issue_tracker_skip(tmp_path):
    store_mod.init(tmp_path, starter_content=False)

    with patch("px0.ui.select", return_value=2):
        cli._prompt_issue_tracker(tmp_path)

    creds = creds_mod.load(tmp_path)
    assert "linear" not in creds
    assert "github" not in creds


def test_prompt_issue_tracker_eoferror(tmp_path):
    store_mod.init(tmp_path, starter_content=False)

    with patch("px0.ui.select", side_effect=EOFError):
        cli._prompt_issue_tracker(tmp_path)

    creds = creds_mod.load(tmp_path)
    assert "linear" not in creds
    assert "github" not in creds


def test_prompt_slack_messaging_yes(tmp_path):
    store_mod.init(tmp_path, starter_content=False)

    with patch("px0.ui.prompt", side_effect=["y", "xoxb-slack-token-abc"]):
        cli._prompt_slack_messaging(tmp_path)

    creds = creds_mod.load(tmp_path)
    assert creds.get("slack", {}).get("token") == "xoxb-slack-token-abc"


def test_prompt_slack_messaging_no(tmp_path):
    store_mod.init(tmp_path, starter_content=False)

    with patch("px0.ui.prompt", return_value="n"):
        cli._prompt_slack_messaging(tmp_path)

    creds = creds_mod.load(tmp_path)
    assert "slack" not in creds


def test_prompt_slack_messaging_eoferror(tmp_path):
    store_mod.init(tmp_path, starter_content=False)

    with patch("px0.ui.prompt", side_effect=EOFError):
        cli._prompt_slack_messaging(tmp_path)

    creds = creds_mod.load(tmp_path)
    assert "slack" not in creds
