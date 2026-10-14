import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from deepwick_spec.ansi import runs
from deepwick_spec.check_port import check_port
from deepwick_spec.palette import load_palette
from deepwick_spec.tui import capture, tmux_available

REPO = Path(__file__).resolve().parents[1]
PALETTE = load_palette()
C = PALETTE.colors


def isolated_env(tmp_path, **extra):
    dirs = {"HOME": tmp_path / "home"}
    for kind in ("CONFIG", "DATA", "STATE", "CACHE"):
        dirs[f"XDG_{kind}_HOME"] = tmp_path / kind.lower()
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    env = {key: str(path) for key, path in dirs.items()}
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    env.update({key: str(value) for key, value in extra.items()})
    return env


THEME = REPO / "deepwick.toml"
COLORS = {
    "AlertInfo": "cyan", "AlertWarn": "yellow", "AlertError": "red", "Annotation": "muted", "Base": "foreground",
    "Guidance": "comment", "Important": "blue", "Title": "blue", "Muted": "muted",
    "SyntaxCommand": "yellow", "SyntaxFlag": "lightBlue", "SyntaxString": "orange", "SyntaxVariable": "lightBlue",
    "SyntaxOperator": "foreground", "SyntaxComment": "comment",
}


def theme():
    assert THEME.is_file(), "deepwick.toml missing"
    return tomllib.loads(THEME.read_text(encoding="utf-8"))


def test_name():
    assert theme()["theme"] == {"name": "deepwick"}


def test_colors():
    assert theme()["colors"] == {key: C[color] for key, color in COLORS.items()}


def atuin_env(tmp_path):
    env = isolated_env(tmp_path)
    config = Path(env["XDG_CONFIG_HOME"]) / "atuin"
    (config / "themes").mkdir(parents=True)
    shutil.copy(THEME, config / "themes" / "deepwick.toml")
    data = Path(env["XDG_DATA_HOME"]) / "atuin"
    data.mkdir(parents=True)
    (config / "config.toml").write_text(
        f'db_path = "{data / "history.db"}"\n'
        f'record_store_path = "{data / "records.db"}"\n'
        f'key_path = "{data / "key"}"\n'
        'auto_sync = false\n'
        'update_check = false\n'
        'sync_address = "http://127.0.0.1:9"\n'
        "[logs]\nenabled = false\n"
        "[daemon]\nenabled = false\n"
        '[theme]\nname = "deepwick"\n'
    )
    env["ATUIN_CONFIG_DIR"] = str(config)
    run_env = {**os.environ, **env}
    env["ATUIN_SESSION"] = subprocess.run(["atuin", "uuid"], env=run_env, capture_output=True, text=True, check=True).stdout.strip()
    run_env = {**os.environ, **env}
    for command, code in (("git status", 0), ("ls -l ~/src", 0), ('grep -r "deepwick" .', 1)):
        hid = subprocess.run(["atuin", "history", "start", "--", command], env=run_env, capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["atuin", "history", "end", "--exit", str(code), "--duration", "1500000000", hid], env=run_env, check=True, capture_output=True)
    return env


@pytest.mark.skipif(not (tmux_available() and shutil.which("atuin")), reason="requires tmux and atuin")
def test_atuin_search_uses_theme(tmp_path):
    text = capture("atuin search -i", atuin_env(tmp_path), size=(110, 20), wait_for="git status")
    fgs = {s["fg"] for _, s in runs(text)}
    assert {C["foreground"].lower(), C["blue"].lower(), C["cyan"].lower(), C["red"].lower(), C["muted"].lower()} <= fgs


def test_port_conventions():
    assert check_port(REPO, PALETTE.allowed_hex()) == []
