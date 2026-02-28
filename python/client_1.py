#!/usr/bin/env python3
"""
Client 1: Completion Bot
Strategy: Always try to finish what you started.
- If you have 1 Tempura, grab the 2nd (a lone Tempura is worth 0)
- If you have 1-2 Sashimi, keep building toward the set of 3 (0 pts without it)
- Dumplings scale (1,3,6,10,15) so always grab more if you already have some
- Wasabi+nigiri combos whenever possible
"""

import random
import sys
from base_client import SushiGoClient, NIGIRI, MAKI


class CompletionBot(SushiGoClient):
    def choose_card(self, hand: list[str]) -> int:
        s = self.state

        # Always cash in wasabi with the best available nigiri
        if s.has_unused_wasabi:
            for n in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if n in hand:
                    return hand.index(n)

        # A lone Tempura is worthless - desperately complete the pair
        if s.count_played("Tempura") % 2 == 1 and "Tempura" in hand:
            return hand.index("Tempura")

        # A partial Sashimi set is worthless - keep building toward 3
        sashimi_so_far = s.count_played("Sashimi") % 3
        if sashimi_so_far > 0 and "Sashimi" in hand:
            return hand.index("Sashimi")

        # Dumplings compound - always add to an existing run
        if s.count_played("Dumpling") > 0 and "Dumpling" in hand:
            return hand.index("Dumpling")

        # Start new high-value sets or grab best singles
        priority = [
            "Wasabi",         # set up a nigiri multiplier
            "Squid Nigiri",   # 3 pts, 9 with wasabi
            "Salmon Nigiri",  # 2 pts, 6 with wasabi
            "Sashimi",        # start a set (10 pts for 3)
            "Tempura",        # start a pair (5 pts)
            "Dumpling",       # start a run
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Egg Nigiri",
            "Pudding",
            "Maki Roll (1)",
            "Chopsticks",
        ]
        for card in priority:
            if card in hand:
                return hand.index(card)

        return random.randint(0, len(hand) - 1)


def main():
    if len(sys.argv) != 3:
        print("Usage: python client_1.py <game_id> <player_name>")
        sys.exit(1)
    CompletionBot().run(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()

