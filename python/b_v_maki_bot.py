#!/usr/bin/env python3
import sys
from sushi_go_client import SushiGoClient


class MakiBot(SushiGoClient):
    def choose_card(self, hand: list[str]) -> int:
        # High priority for Maki (3), then (2), then (1)
        maki_priority = [
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Maki Roll (1)",
            "Squid Nigiri",
            "Salmon Nigiri"
        ]

        # If we have wasabi, still try to use it for points
        if self.state and self.state.has_unused_wasabi:
            for nigiri in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if nigiri in hand:
                    return hand.index(nigiri)

        for card in maki_priority:
            if card in hand:
                return hand.index(card)

        # Fallback to the priority list in the base class
        return super().choose_card(hand)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(1)
    client = MakiBot(sys.argv[1], int(sys.argv[2]))
    client.run(sys.argv[3], sys.argv[4])