from pathlib import Path

import pytest
from conftest import chat_request, make_image_bytes

from bladesight.meta import (
    MetaConfigError,
    MetaSettings,
    StubProvider,
    build_client,
)
from bladesight.meta.__main__ import main

SECRET = "sk-super-secret-value"


def test_status_reports_set_or_missing_never_values() -> None:
    settings = MetaSettings.from_env(
        {
            "META_API_KEY": SECRET,
            "META_API_BASE_URL": "https://x.test",
            "META_SPEND_LIMIT_USD": "0.1",
        }
    )
    status = settings.status()
    assert status["META_API_KEY"] == "set"
    assert status["META_API_BASE_URL"] == "set"
    assert status["BASETEN_API_KEY"] == "missing"
    assert status["META_SPEND_LIMIT_USD"] == "0.10"
    assert SECRET not in repr(settings)
    assert SECRET not in str(status)
    assert SECRET not in settings.model_dump_json()


def test_defaults() -> None:
    settings = MetaSettings.from_env({})
    assert settings.spend_limit_usd == 0.50
    assert settings.mode == "replay"
    assert settings.meta_api_key is None
    assert settings.meta_api_base_url == "https://api.meta.ai"
    assert settings.status()["META_API_BASE_URL"] == "default"
    assert settings.baseten_base_url == "https://inference.baseten.co/v1"
    assert settings.baseten_spend_limit_usd == 10.00
    assert settings.chat_model == "muse-spark-1.3"
    assert settings.sam_model == "sam-3.1"


def test_model_ids_and_base_url_can_be_overridden_without_code_changes() -> None:
    settings = MetaSettings.from_env(
        {
            "META_CHAT_MODEL": "muse-spark-1.2",
            "META_SAM_MODEL": "sam-3.1-x",
            "META_API_BASE_URL": "https://other.test/v1",
        }
    )
    assert (settings.chat_model, settings.sam_model) == ("muse-spark-1.2", "sam-3.1-x")
    assert settings.meta_api_base_url == "https://other.test/v1"


@pytest.mark.parametrize(
    "env",
    [
        {"META_SPEND_LIMIT_USD": "abc"},
        {"META_SPEND_LIMIT_USD": "-1"},
        {"META_SPEND_LIMIT_USD": "nan"},
        {"BASETEN_SPEND_LIMIT_USD": "-0.01"},
        {"BASETEN_SPEND_LIMIT_USD": "ten"},
        {"BLADESIGHT_MODE": "yolo"},
    ],
)
def test_invalid_values_are_config_errors(env: dict[str, str]) -> None:
    with pytest.raises(MetaConfigError):
        MetaSettings.from_env(env)


def test_dotenv_is_parsed_in_process_and_real_env_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / "test.env"
    dotenv.write_text(f"META_API_KEY={SECRET}\nMETA_SPEND_LIMIT_USD=0.25\n", encoding="utf-8")
    monkeypatch.setenv("META_SPEND_LIMIT_USD", "0.05")
    monkeypatch.delenv("META_API_KEY", raising=False)

    settings = MetaSettings.from_env(dotenv_path=dotenv)

    assert settings.meta_api_key is not None
    assert settings.meta_api_key.get_secret_value() == SECRET
    assert settings.spend_limit_usd == 0.05


def test_live_mode_fails_fast_without_credentials() -> None:
    live = {"BLADESIGHT_MODE": "live"}
    with pytest.raises(MetaConfigError) as info:
        build_client(MetaSettings.from_env(live), provider="meta")
    assert "missing" in str(info.value)
    with pytest.raises(MetaConfigError):
        build_client(MetaSettings.from_env(live), provider="baseten")


def test_replay_mode_is_cache_only_and_live_mode_is_not() -> None:
    base = {"META_API_KEY": "k"}  # the base URL defaults to https://api.meta.ai
    assert build_client(MetaSettings.from_env(base)).cache_only is True
    live = MetaSettings.from_env(base | {"BLADESIGHT_MODE": "live"})
    client = build_client(live)
    assert client.cache_only is False
    assert client.spend.limit_usd == 0.50


def test_stub_client_is_uncapped_unless_asked_and_has_no_network() -> None:
    settings = MetaSettings.from_env({"META_SPEND_LIMIT_USD": "0"})
    stub = StubProvider()
    client = build_client(settings, provider="stub", stub=stub)
    client.chat(chat_request())
    assert stub.call_count == 1
    assert client.records[0].source == "stub"


def test_cli_status_prints_set_or_missing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # never pick up the real .env
    monkeypatch.setenv("META_API_KEY", SECRET)
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)

    assert main(["status"]) == 0

    out = capsys.readouterr().out
    assert "META_API_KEY=set" in out
    assert "BASETEN_API_KEY=missing" in out
    assert SECRET not in out


def test_cli_stub_chat_and_segment(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    image = tmp_path / "tile.png"
    image.write_bytes(make_image_bytes())

    assert main(["chat", "--provider", "stub", "--prompt", "hi"]) == 0
    assert "source=stub" in capsys.readouterr().out
    assert main(["segment", "--provider", "stub", "--image", str(image), "--concept", "crack"]) == 0
    assert "concept=crack" in capsys.readouterr().out


def test_cli_live_without_key_fails_cleanly(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BLADESIGHT_MODE", "live")
    assert main(["chat", "--prompt", "hi"]) == 1
    assert "missing" in capsys.readouterr().err


def test_cli_replay_without_key_reports_a_cache_miss_not_a_missing_key(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # replay is the default mode
    assert main(["chat", "--prompt", "hi"]) == 1
    err = capsys.readouterr().err
    assert "not cached" in err
    assert "BLADESIGHT_MODE=live" in err


def test_cli_refuses_the_heldout_split(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    heldout = tmp_path / "data" / "heldout"
    heldout.mkdir(parents=True)
    (heldout / "x.png").write_bytes(make_image_bytes())
    with pytest.raises(SystemExit):
        main(["segment", "--provider", "stub", "--image", str(heldout / "x.png"), "--concept", "c"])


def test_baseten_settings_and_separate_caps_come_from_the_environment() -> None:
    settings = MetaSettings.from_env(
        {
            "BASETEN_API_KEY": SECRET,
            "BASETEN_BASE_URL": "https://bt.test/v1",
            "BASETEN_SPEND_LIMIT_USD": "3.5",
            "META_SPEND_LIMIT_USD": "0.1",
        }
    )
    status = settings.status()
    assert (status["BASETEN_API_KEY"], status["BASETEN_BASE_URL"]) == ("set", "set")
    assert status["BASETEN_SPEND_LIMIT_USD"] == "3.50"
    assert SECRET not in str(status)

    meta = build_client(settings.model_copy(update={"meta_api_key": settings.baseten_api_key}))
    baseten = build_client(settings, provider="baseten")
    assert meta.spend.limit_usd == 0.1 and meta.spend.provider == "meta"
    assert baseten.spend.limit_usd == 3.5 and baseten.spend.provider == "baseten"
    # both read the same on-disk log, so each cap is cumulative across runs
    assert meta.spend.log_path == baseten.spend.log_path == settings.spend_log_path


def test_baseten_retries_more_slowly_than_meta_for_its_low_default_rate_limit() -> None:
    settings = MetaSettings.from_env({"BASETEN_API_KEY": SECRET, "META_API_KEY": SECRET})
    assert build_client(settings, provider="baseten").retry.base_delay > (
        build_client(settings, provider="meta").retry.base_delay
    )


def test_spend_log_and_cache_do_not_depend_on_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = MetaSettings.from_env({})  # defaults, not the test fixture's overrides
    assert settings.spend_log_path.is_absolute()
    assert settings.spend_log_path.parts[-2:] == (".spend", "spend_log.jsonl")
    assert (settings.spend_log_path.parent.parent / "pyproject.toml").is_file()
    assert tmp_path not in settings.spend_log_path.parents
