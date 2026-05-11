from __future__ import annotations

import sys
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
    roots = [
        Path("C:/Program Files (x86)/Steam"),
        Path("C:/Program Files/Steam"),
    ]

    for drive in "CDEFGHI":
        roots.append(Path(f"{drive}:/SteamLibrary"))
        roots.append(Path(f"{drive}:/Games/SteamLibrary"))

    return [root / "steamapps/common/dota 2 beta" for root in roots]


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


def main() -> int:
    if len(sys.argv) > 1:
        dota_path = Path(sys.argv[1]).expanduser().resolve()
    else:
        found = find_dota_path()
        if found is None:
            print("Could not find the Dota2 root folder.")
            print("If this tool folder is inside the Dota2 root, move it under:")
            print(r'  ...\steamapps\common\dota 2 beta\Dota2_LocalPlus')
            print("Or pass the Dota2 root path manually, for example:")
            print(r'  python .\install_gsi_config.py "D:\SteamLibrary\steamapps\common\dota 2 beta"')
            return 1
        dota_path = found

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
