#!/usr/bin/env python3
"""
Client 3: Denier Bot
Strategy: Watch what opponents are collecting via PLAYED messages and take cards
they need before they can complete sets.
- If an opponent has 1 Tempura, grab Tempura to strand their pair
- If an opponent has 1-2 Sashimi, block them from completing the set
- If an opponent is stacking maki rolls, take the Maki Roll (3)s first
- Own fallback: nigiri + wasabi for solid guaranteed points
"""

import random
import sys
from base_client import SushiGoClient, NIGIRI, MAKI


class DenierBot(SushiGoClient):
    def _opponent_counts(self, card: str) -> list[int]:
        """Returns count of card per opponent this round."""
        return [cards.count(card) for cards in self.state.opponent_cards.values()]

    def choose_card(self, hand: list[str]) -> int:
        s = self.state

        # Always cash wasabi with best nigiri
        if s.has_unused_wasabi:
            for n in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if n in hand:
                    return hand.index(n)

        # --- Denial logic (only meaningful when we have opponent data) ---
        if s.opponent_cards:
            # Block Tempura: opponent has 1 (needs exactly 1 more to score 5)
            tempura_counts = self._opponent_counts("Tempura")
            if any(c % 2 == 1 for c in tempura_counts) and "Tempura" in hand:
                return hand.index("Tempura")

            # Block Sashimi: opponent has 1 or 2 (needs more to score 10, currently 0)
            sashimi_counts = self._opponent_counts("Sashimi")
            if any(0 < c % 3 < 3 for c in sashimi_counts) and "Sashimi" in hand:
                return hand.index("Sashimi")

            # Block maki: take the big maki if an opponent is aggressively stacking
            opp_maki_totals = [
                sum(cards.count(m) * (3 if m == "Maki Roll (3)" else 2 if m == "Maki Roll (2)" else 1)
                    for m in MAKI for cards in [v])
                for v in s.opponent_cards.values()
            ]
            if any(t >= 4 for t in opp_maki_totals) and "Maki Roll (3)" in hand:
                return hand.index("Maki Roll (3)")

        # --- Own strategy fallback ---
        # Start a Tempura pair if we don't have one going
        if s.count_played("Tempura") % 2 == 1 and "Tempura" in hand:
            return hand.index("Tempura")

        priority = [
            "Squid Nigiri",
            "Salmon Nigiri",
            "Wasabi",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Tempura",
            "Dumpling",
            "Sashimi",
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
        print("Usage: python client_3.py <game_id> <player_name>")
        sys.exit(1)
    DenierBot().run(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()

