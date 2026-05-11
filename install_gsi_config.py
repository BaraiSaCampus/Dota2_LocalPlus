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


def candidate_dota_paths() -> list[Path]:
    roots = [
        Path("C:/Program Files (x86)/Steam"),
        Path("C:/Program Files/Steam"),
    ]

    for drive in "CDEFGHI":
        roots.append(Path(f"{drive}:/SteamLibrary"))
        roots.append(Path(f"{drive}:/Games/SteamLibrary"))

    return [root / "steamapps/common/dota 2 beta" for root in roots]


def find_dota_path() -> Path | None:
    for path in candidate_dota_paths():
        if (path / "game/dota").exists():
            return path
    return None


def main() -> int:
    if len(sys.argv) > 1:
        dota_path = Path(sys.argv[1]).expanduser()
    else:
        found = find_dota_path()
        if found is None:
            print("未找到 Dota2 安装目录。请把 Dota2 根目录作为参数传入。")
            print(r'示例: python .\install_gsi_config.py "D:\SteamLibrary\steamapps\common\dota 2 beta"')
            return 1
        dota_path = found

    cfg_dir = dota_path / "game/dota/cfg/gamestate_integration"
    if not (dota_path / "game/dota").exists():
        print(f"路径不像 Dota2 根目录: {dota_path}")
        return 1

    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / CONFIG_NAME
    cfg_file.write_text(CONFIG_TEXT, encoding="utf-8")

    print(f"已写入: {cfg_file}")
    print("请重启 Dota2。若无数据，请在启动项加入 -gamestateintegration。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

