#!/usr/bin/env python3
"""
Client 2: Maki Rush Bot
Strategy: Commit hard to winning the maki majority bonus.
- Always prioritize Maki Roll (3) > (2) > (1)
- If wasabi lands in hand, use it on the next nigiri (free points)
- Late in the round (few cards left), if maki is already locked in, pivot to nigiri
- Chopsticks are ignored - pass them along, they slow down the maki plan
"""

import random
import sys
from base_client import SushiGoClient, NIGIRI, MAKI


class MakiRushBot(SushiGoClient):
    def _my_maki_count(self) -> int:
        s = self.state
        return (
            s.count_played("Maki Roll (3)") * 3
            + s.count_played("Maki Roll (2)") * 2
            + s.count_played("Maki Roll (1)") * 1
        )

    def choose_card(self, hand: list[str]) -> int:
        s = self.state

        # Always cash wasabi immediately
        if s.has_unused_wasabi:
            for n in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if n in hand:
                    return hand.index(n)

        # Late in round: if we've already stacked maki, switch to sure nigiri points
        turns_left = 10 - s.turn
        if turns_left <= 2 and self._my_maki_count() >= 6:
            for n in ["Squid Nigiri", "Salmon Nigiri"]:
                if n in hand:
                    return hand.index(n)

        # Core strategy: maki above all else
        priority = [
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Squid Nigiri",   # best fallback when no maki
            "Salmon Nigiri",
            "Wasabi",         # set up future nigiri
            "Maki Roll (1)",
            "Tempura",
            "Dumpling",
            "Sashimi",
            "Egg Nigiri",
            "Pudding",
            "Chopsticks",     # last resort - pass it on
        ]
        for card in priority:
            if card in hand:
                return hand.index(card)

        return random.randint(0, len(hand) - 1)


def main():
    if len(sys.argv) != 3:
        print("Usage: python client_2.py <game_id> <player_name>")
        sys.exit(1)
    MakiRushBot().run(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()

