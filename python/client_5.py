#!/usr/bin/env python3
"""
Client 5: Round-Adaptive Bot
Strategy: Shift priorities each round based on the scoring arc of the game.
- Round 1: Build toward long-payoff sets (Sashimi, Maki majority)
- Round 2: Pivot to nigiri + completing in-progress sets
- Round 3: Pudding matters for end-game delta, grab sure points fast
Also turn-aware: late in any round, abandon incomplete sets and take sure points.
"""

import random
import sys
from base_client import SushiGoClient, NIGIRI, MAKI


class RoundAdaptiveBot(SushiGoClient):
    ROUND_PRIORITIES = {
        1: [
            # Long-term combos: set up maki majority and sashimi
            "Sashimi",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Tempura",
            "Wasabi",
            "Squid Nigiri",
            "Salmon Nigiri",
            "Dumpling",
            "Egg Nigiri",
            "Pudding",
            "Maki Roll (1)",
            "Chopsticks",
        ],
        2: [
            # Shift to nigiri - complete any sets started in round 1
            "Wasabi",
            "Squid Nigiri",
            "Salmon Nigiri",
            "Tempura",
            "Sashimi",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Dumpling",
            "Pudding",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
        3: [
            # Pudding delta is critical; grab sure points, ignore long sets
            "Pudding",
            "Squid Nigiri",
            "Salmon Nigiri",
            "Wasabi",
            "Dumpling",
            "Maki Roll (3)",
            "Tempura",
            "Maki Roll (2)",
            "Sashimi",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
    }

    def choose_card(self, hand: list[str]) -> int:
        s = self.state

        # Always cash wasabi first regardless of round
        if s.has_unused_wasabi:
            for n in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if n in hand:
                    return hand.index(n)

        # Late in round: abandon half-finished sets, take sure points
        turns_left = 10 - s.turn
        if turns_left <= 2:
            # Complete a Tempura pair if one card away
            if s.count_played("Tempura") % 2 == 1 and "Tempura" in hand:
                return hand.index("Tempura")
            # Complete a Sashimi set if one card away
            if s.count_played("Sashimi") % 3 == 2 and "Sashimi" in hand:
                return hand.index("Sashimi")
            # Otherwise pivot to sure points
            for card in ["Squid Nigiri", "Salmon Nigiri", "Dumpling", "Pudding"]:
                if card in hand:
                    return hand.index(card)

        # Round-specific priority
        priority = self.ROUND_PRIORITIES.get(s.round, self.ROUND_PRIORITIES[2])
        for card in priority:
            if card in hand:
                return hand.index(card)

        return random.randint(0, len(hand) - 1)


def main():
    if len(sys.argv) != 3:
        print("Usage: python client_5.py <game_id> <player_name>")
        sys.exit(1)
    RoundAdaptiveBot().run(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()

