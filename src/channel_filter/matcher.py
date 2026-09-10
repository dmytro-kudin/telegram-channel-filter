"""Aho-Corasick automaton build/rebuild/atomic-swap over eligible subscribers' keywords."""

from __future__ import annotations

import asyncio

import aiosqlite
import ahocorasick

ELIGIBLE_KEYWORDS_QUERY = """
SELECT k.substring, k.chat_id
FROM keywords k
JOIN subscribers s ON s.chat_id = k.chat_id
WHERE s.active = 1 AND s.blocked = 0
"""


def _build_automaton_sync(rows: list[tuple[str, int]]) -> ahocorasick.Automaton:
    automaton = ahocorasick.Automaton()
    grouped: dict[str, set[int]] = {}
    for substring, chat_id in rows:
        grouped.setdefault(substring, set()).add(chat_id)
    for substring, chat_ids in grouped.items():
        automaton.add_word(substring, (substring, frozenset(chat_ids)))
    automaton.make_automaton()
    return automaton


class AutomatonManager:
    """Holds a single automaton reference, atomically swapped on rebuild."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn
        self._automaton: ahocorasick.Automaton = ahocorasick.Automaton()
        self._lock = asyncio.Lock()

    async def build(self) -> None:
        await self.rebuild()

    async def rebuild(self) -> None:
        async with self._lock:
            cursor = await self._conn.execute(ELIGIBLE_KEYWORDS_QUERY)
            rows = await cursor.fetchall()
            self._automaton = await asyncio.to_thread(
                _build_automaton_sync, [(row[0], row[1]) for row in rows]
            )

    def find_matching_chat_ids(self, text: str) -> frozenset[int]:
        if len(self._automaton) == 0:
            return frozenset()
        lowered = text.lower()
        matched: set[int] = set()
        for _, (_, chat_ids) in self._automaton.iter(lowered):
            matched.update(chat_ids)
        return frozenset(matched)
