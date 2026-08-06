from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import economy_core
import install_gsi_config


class EconomyOverlayCoreTests(unittest.TestCase):
    def test_extract_item_names_normalizes_nested_gsi_items(self) -> None:
        items = {
            "slot0": {"name": "item_blink"},
            "slot1": {"name": "empty"},
            "stash0": {"name": "item_tango"},
        }
        self.assertEqual(economy_core.extract_item_names(items), ["blink", "tango"])

    def test_economy_state_calculates_net_worth_and_unknown_items(self) -> None:
        state = economy_core.EconomyState()
        state.update_from_payload(
            {
                "map": {"clock_time": 90, "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"},
                "player": {"gold": 500, "gold_reliable": 300, "gold_unreliable": 200, "gpm": 400, "xpm": 500},
                "hero": {"name": "npc_dota_hero_axe", "level": 8},
                "items": {"slot0": {"name": "item_blink"}, "slot1": {"name": "item_unknown"}},
            },
            {"blink": 2250},
        )
        self.assertEqual(state.net_worth, 2750)
        self.assertEqual(state.unknown_items, ["unknown"])

    def test_latest_payload_discards_stale_updates(self) -> None:
        buffer = economy_core.LatestPayload()
        buffer.publish({"map": {"clock_time": 1}})
        buffer.publish({"map": {"clock_time": 2}})
        self.assertEqual(buffer.consume(), {"map": {"clock_time": 2}})
        self.assertIsNone(buffer.consume())

    def test_payload_validation_rejects_invalid_shapes(self) -> None:
        self.assertTrue(economy_core.is_valid_gsi_payload({"map": {}, "player": {}, "items": {}}))
        self.assertFalse(economy_core.is_valid_gsi_payload([]))
        self.assertFalse(economy_core.is_valid_gsi_payload({"map": "not-an-object"}))


class GSIConfigTests(unittest.TestCase):
    def test_looks_like_dota_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(install_gsi_config.looks_like_dota_root(root))
            (root / "game/dota").mkdir(parents=True)
            self.assertTrue(install_gsi_config.looks_like_dota_root(root))

    def test_select_option_uses_folder_picker_after_auto_detection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "game/dota").mkdir(parents=True)
            with patch.object(install_gsi_config, "find_dota_path", return_value=None), \
                patch.object(install_gsi_config, "choose_dota_path", return_value=root), \
                patch("sys.argv", ["install_gsi_config.py", "--select"]):
                self.assertEqual(install_gsi_config.main(), 0)
            self.assertTrue(
                (root / "game/dota/cfg/gamestate_integration/gamestate_integration_codex_economy.cfg").exists()
            )


if __name__ == "__main__":
    unittest.main()
