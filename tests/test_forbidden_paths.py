import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_forbidden_paths",
    Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "check_forbidden_paths.py",
)
assert _spec and _spec.loader
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def test_blocks_data_images_and_secrets() -> None:
    assert hook.is_forbidden("data/dev/tile_001.jpg")
    assert hook.is_forbidden("src/bladesight/sample.png")
    assert hook.is_forbidden(".env")
    assert hook.is_forbidden(".env.local")
    assert hook.is_forbidden("eval/heldout/ids.txt")
    assert hook.is_forbidden("weights/yolo.pt")
    assert hook.is_forbidden("docs/evidence/crop_fn_01.png")


def test_allows_code_docs_and_small_ui_assets() -> None:
    assert hook.is_forbidden("src/bladesight/meta/client.py") is None
    assert hook.is_forbidden(".env.example") is None
    assert hook.is_forbidden("web/public/favicon.svg") is None
    assert hook.is_forbidden("docs/evidence/threshold_curve.svg") is None
    assert hook.is_forbidden("eval/heldout_manifest.sha256") is None


def test_main_exit_code() -> None:
    assert hook.main(["README.md"]) == 0
    assert hook.main(["data/x.csv"]) == 1
