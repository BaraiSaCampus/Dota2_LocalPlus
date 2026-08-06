from __future__ import annotations

import sys
import os
import re
from pathlib import Path


CONFIG_NAME = "gamestate_integration_codex_economy.cfg"
CONFIG_TEXT = '''"Dota 2 Economy Overlay"
{
    "uri"           "http://127.0.0.1:3007"
    "timeout"       "5.0"
    "buffer"        "0.1"
    "throttle"      "0.1"
    "heartbeat"     "5.0"
    "data"
    {
        "provider"      "1"
        "map"           "1"
        "player"        "1"
        "hero"          "1"
        "abilities"     "0"
        "items"         "1"
        "buildings"     "0"
        "draft"         "0"
        "wearables"     "0"
    }
}
'''


def looks_like_dota_root(path: Path) -> bool:
    return (path / "game/dota").exists()


def local_dota_candidates() -> list[Path]:
    if getattr(sys, "frozen", False):
        script_dir = Path(sys.executable).resolve().parent
    else:
        script_dir = Path(__file__).resolve().parent
    candidates: list[Path] = []

    # Supports both layouts:
    # 1. Files copied directly into ".../dota 2 beta"
    # 2. Project folder placed under ".../dota 2 beta/Dota2_LocalPlus"
    for path in [script_dir, *script_dir.parents]:
        candidates.append(path)
        if path.parent != path:
            candidates.append(path.parent)

    return candidates


def steam_library_candidates() -> list[Path]:
    steam_roots = [
        Path("C:/Program Files (x86)/Steam"),
        Path("C:/Program Files/Steam"),
    ]
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        value = os.environ.get(variable)
        if value:
            steam_roots.append(Path(value) / "Steam")

    library_roots: list[Path] = []
    for steam_root in steam_roots:
        library_roots.append(steam_root)
        library_file = steam_root / "steamapps/libraryfolders.vdf"
        try:
            contents = library_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw_path in re.findall(r'"path"\s*"([^"]+)"', contents):
            library_roots.append(Path(raw_path.replace("\\\\", "\\")))

    for drive in "CDEFGHI":
        library_roots.append(Path(f"{drive}:/SteamLibrary"))
        library_roots.append(Path(f"{drive}:/Games/SteamLibrary"))

    seen: set[str] = set()
    candidates: list[Path] = []
    for root in library_roots:
        candidate = root / "steamapps/common/dota 2 beta"
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            candidates.append(candidate)
    return candidates


def candidate_dota_paths() -> list[Path]:
    seen: set[str] = set()
    candidates: list[Path] = []
    for path in [*local_dota_candidates(), *steam_library_candidates()]:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            candidates.append(path)
    return candidates


def find_dota_path() -> Path | None:
    for path in candidate_dota_paths():
        if looks_like_dota_root(path):
            return path
    return None


def choose_dota_path() -> Path | None:
    """Ask a non-technical user to select the Dota2 root folder when auto-detection fails."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showinfo(
        "Dota2 LocalPlus",
        "没有自动找到 Dota2。\n\n"
        "请在接下来打开的窗口中选择 Dota2 游戏根目录：\n"
        "...\\steamapps\\common\\dota 2 beta",
        parent=root,
    )
    selected = filedialog.askdirectory(title="选择 Dota2 游戏根目录", parent=root)
    root.destroy()
    if not selected:
        return None
    return Path(selected).expanduser().resolve()


def main() -> int:
    arguments = [argument for argument in sys.argv[1:] if argument != "--select"]
    allow_picker = "--select" in sys.argv[1:]
    if arguments:
        dota_path = Path(arguments[0]).expanduser().resolve()
    else:
        found = find_dota_path()
        dota_path = found
        if dota_path is None and allow_picker:
            dota_path = choose_dota_path()
        if dota_path is None:
            print("Could not find the Dota2 root folder.")
            print("If this tool folder is inside the Dota2 root, move it under:")
            print(r'  ...\steamapps\common\dota 2 beta\Dota2_LocalPlus')
            print("Or pass the Dota2 root path manually, for example:")
            print(r'  python .\install_gsi_config.py "D:\SteamLibrary\steamapps\common\dota 2 beta"')
            return 1

    if not looks_like_dota_root(dota_path):
        print(f"This path does not look like the Dota2 root folder: {dota_path}")
        return 1

    cfg_dir = dota_path / "game/dota/cfg/gamestate_integration"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / CONFIG_NAME
    cfg_file.write_text(CONFIG_TEXT, encoding="utf-8")

    print(f"Wrote GSI config: {cfg_file}")
    print("Restart Dota2. If there is still no data, add -gamestateintegration to Dota2 launch options.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
