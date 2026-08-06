from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_item_name(name: str) -> str:
    name = name.strip()
    if name.startswith("item_"):
        name = name[5:]
    return name


def extract_item_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, dict):
        item_name = value.get("name")
        if isinstance(item_name, str) and item_name and item_name != "empty":
            names.append(normalize_item_name(item_name))
        for child in value.values():
            names.extend(extract_item_names(child))
    elif isinstance(value, list):
        for child in value:
            names.extend(extract_item_names(child))
    return names


@dataclass
class EconomyState:
    connected: bool = False
    updated_at: float = 0.0
    game_time: int = 0
    map_state: str = "unknown"
    gold: int = 0
    reliable_gold: int = 0
    unreliable_gold: int = 0
    item_value: int = 0
    net_worth: int = 0
    unknown_items: list[str] = field(default_factory=list)
    gpm: int = 0
    xpm: int = 0

    def update_from_payload(self, payload: dict[str, Any], item_prices: dict[str, int]) -> None:
        now = time.time()
        player = payload.get("player") or {}
        map_data = payload.get("map") or {}

        self.connected = True
        self.updated_at = now
        self.game_time = as_int(map_data.get("clock_time"), self.game_time)
        self.map_state = str(map_data.get("game_state") or self.map_state)
        self.gold = as_int(player.get("gold"), self.gold)
        self.reliable_gold = as_int(player.get("gold_reliable"), self.reliable_gold)
        self.unreliable_gold = as_int(player.get("gold_unreliable"), self.unreliable_gold)
        self.gpm = as_int(player.get("gpm"), self.gpm)
        self.xpm = as_int(player.get("xpm"), self.xpm)

        item_names = extract_item_names(payload.get("items") or {})
        self.item_value = sum(item_prices.get(name, 0) for name in item_names)
        self.unknown_items = sorted({name for name in item_names if name not in item_prices})
        self.net_worth = self.gold + self.item_value


class LatestPayload:
    """A thread-safe, single-slot buffer for the most recent GSI update."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: dict[str, Any] | None = None

    def publish(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._payload = payload

    def consume(self) -> dict[str, Any] | None:
        with self._lock:
            payload = self._payload
            self._payload = None
            return payload


def is_valid_gsi_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in ("map", "player", "hero", "items"):
        value = payload.get(key)
        if value is not None and not isinstance(value, dict):
            return False
    return True
