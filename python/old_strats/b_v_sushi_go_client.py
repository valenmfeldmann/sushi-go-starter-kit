#!/usr/bin/env python3
"""
Sushi Go Client - Python Starter Kit

This client connects to the Sushi Go server and plays using a simple strategy.
Modify the `choose_card` method to implement your own AI!

Usage:
    python sushi_go_client.py <server_host> <server_port> <game_id> <player_name>

Example:
    python sushi_go_client.py localhost 7878 abc123 MyBot
"""

import random
import re
import socket
import sys
from dataclasses import dataclass
from typing import Optional

# Card names used by the protocol (now using full names instead of codes)
CARD_NAMES = {
    "Tempura": "Tempura",
    "Sashimi": "Sashimi",
    "Dumpling": "Dumpling",
    "Maki Roll (1)": "Maki Roll (1)",
    "Maki Roll (2)": "Maki Roll (2)",
    "Maki Roll (3)": "Maki Roll (3)",
    "Egg Nigiri": "Egg Nigiri",
    "Salmon Nigiri": "Salmon Nigiri",
    "Squid Nigiri": "Squid Nigiri",
    "Pudding": "Pudding",
    "Wasabi": "Wasabi",
    "Chopsticks": "Chopsticks",
}


@dataclass
class GameState:
    """Tracks the current state of the game."""

    game_id: str
    player_id: int
    hand: list[str]
    round: int = 1
    turn: int = 1
    played_cards: list[str] = None
    has_chopsticks: bool = False
    has_unused_wasabi: bool = False
    puddings: int = 0

    def __post_init__(self):
        if self.played_cards is None:
            self.played_cards = []


class SushiGoClient:
    """A client for playing Sushi Go."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.state: Optional[GameState] = None
        self._recv_buffer = ""

    def connect(self):
        """Connect to the server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._recv_buffer = ""
        print(f"Connected to {self.host}:{self.port}")

    def disconnect(self):
        """Disconnect from the server."""
        if self.sock:
            self.sock.close()
            self.sock = None

    def send(self, command: str):
        """Send a command to the server."""
        message = command + "\n"
        self.sock.sendall(message.encode("utf-8"))
        print(f">>> {command}")

    def receive(self) -> str:
        """Receive one line-delimited message from the server."""
        while True:
            if "\n" in self._recv_buffer:
                line, self._recv_buffer = self._recv_buffer.split("\n", 1)
                message = line.strip()
                print(f"<<< {message}")
                return message

            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Server closed connection")
            self._recv_buffer += chunk.decode("utf-8", errors="replace")

    def receive_until(self, predicate) -> str:
        """Read lines until one matches predicate."""
        while True:
            message = self.receive()
            if not message:
                continue
            if predicate(message):
                return message

    def join_game(self, game_id: str, player_name: str) -> bool:
        """Join a game."""
        self.send(f"JOIN {game_id} {player_name}")
        response = self.receive_until(
            lambda line: line.startswith("WELCOME") or line.startswith("ERROR")
        )

        if response.startswith("WELCOME"):
            parts = response.split()
            self.state = GameState(game_id=parts[1], player_id=int(parts[2]), hand=[])
            return True
        elif response.startswith("ERROR"):
            print(f"Failed to join: {response}")
            return False
        return False

    def signal_ready(self):
        """Signal that we're ready to start."""
        self.send("READY")
        return self.receive()

    def play_card(self, card_index: int):
        """Play a card by index."""
        self.send(f"PLAY {card_index}")
        return self.receive()

    def play_chopsticks(self, index1: int, index2: int):
        """Use chopsticks to play two cards."""
        self.send(f"CHOPSTICKS {index1} {index2}")
        return self.receive()

    def parse_hand(self, message: str):
        """Parse a HAND message and update state."""
        if message.startswith("HAND"):
            payload = message[len("HAND ") :]
            cards = []
            for match in re.finditer(r"(\d+):(.*?)(?=\s\d+:|$)", payload):
                cards.append(match.group(2).strip())
            if self.state:
                self.state.hand = cards
                # Update chopsticks/wasabi tracking based on played cards
                self.state.has_chopsticks = "Chopsticks" in self.state.played_cards
                self.state.has_unused_wasabi = any(
                    c == "Wasabi" for c in self.state.played_cards
                ) and not any(
                    c in ("Egg Nigiri", "Salmon Nigiri", "Squid Nigiri")
                    for c in self.state.played_cards
                )

    # Priority lists keyed by (round, hand_phase).
    # hand_phase is determined by turn number:
    #   "early"  → turns 1–3  (big hand, build foundations)
    #   "mid"    → turns 4–7  (hand thinning, commit to combos)
    #   "late"   → turns 8–10 (last cards, take sure points)
    PRIORITIES: dict[tuple[int, str], list[str]] = {
        # ── Round 1: lay foundations ────────────────────────────────────────
        (1, "early"): [
            "Sashimi",        # 10 pts per set of 3 – start early
            "Maki Roll (3)",  # chase maki majority
            "Maki Roll (2)",
            "Tempura",        # 5 pts per pair
            "Wasabi",         # set up future nigiri
            "Squid Nigiri",
            "Salmon Nigiri",
            "Dumpling",
            "Pudding",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
        (1, "mid"): [
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Tempura",        # complete pairs started in early
            "Sashimi",
            "Wasabi",
            "Squid Nigiri",
            "Salmon Nigiri",
            "Dumpling",
            "Pudding",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
        (1, "late"): [
            "Tempura",        # finish any open pair
            "Squid Nigiri",   # sure points over unfinished combos
            "Salmon Nigiri",
            "Sashimi",
            "Dumpling",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Pudding",
            "Wasabi",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
        # ── Round 2: push combos, shift toward nigiri ────────────────────────
        (2, "early"): [
            "Wasabi",         # grab wasabi before it's gone
            "Squid Nigiri",
            "Salmon Nigiri",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Tempura",
            "Sashimi",
            "Dumpling",
            "Pudding",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
        (2, "mid"): [
            "Squid Nigiri",
            "Salmon Nigiri",
            "Wasabi",
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
        (2, "late"): [
            "Squid Nigiri",
            "Salmon Nigiri",
            "Tempura",        # only worth it if one card away from a pair
            "Dumpling",
            "Pudding",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Sashimi",
            "Wasabi",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
        # ── Round 3: pudding delta is decisive; take sure points ─────────────
        (3, "early"): [
            "Pudding",        # pudding delta can swing ±6 pts
            "Wasabi",
            "Squid Nigiri",
            "Salmon Nigiri",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Tempura",
            "Sashimi",
            "Dumpling",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
        (3, "mid"): [
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
        (3, "late"): [
            "Pudding",
            "Squid Nigiri",
            "Salmon Nigiri",
            "Dumpling",
            "Tempura",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Sashimi",
            "Wasabi",
            "Egg Nigiri",
            "Maki Roll (1)",
            "Chopsticks",
        ],
    }

    def _hand_phase(self) -> str:
        """Return the phase of the current hand based on turn number."""
        turn = self.state.turn if self.state else 1
        if turn <= 3:
            return "early"
        if turn <= 7:
            return "mid"
        return "late"

    def choose_card(self, hand: list[str]) -> int:
        """
        Choose which card to play.

        Strategy adapts to both the current round (1–3) and the phase of the
        hand (early / mid / late) so that the bot builds the right combos at
        the right time and cashes in sure points as cards run out.

        Args:
            hand: List of card names in your current hand

        Returns:
            Index of the card to play (0-based)
        """
        # Always cash in wasabi immediately with the best available nigiri
        if self.state and self.state.has_unused_wasabi:
            for nigiri in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if nigiri in hand:
                    return hand.index(nigiri)

        # Select the priority list for the current round + hand phase
        round_num = self.state.round if self.state else 1
        phase = self._hand_phase()
        priority = self.PRIORITIES.get(
            (round_num, phase),
            self.PRIORITIES[(1, "early")],   # safe fallback
        )

        for card in priority:
            if card in hand:
                return hand.index(card)

        # Fallback: random
        return random.randint(0, len(hand) - 1)

    def handle_message(self, message: str):
        """Handle a message from the server."""
        if message.startswith("HAND"):
            self.parse_hand(message)
        elif message.startswith("ROUND_START"):
            parts = message.split()
            if self.state:
                self.state.round = int(parts[1])
                self.state.turn = 1
                self.state.played_cards = []
        elif message.startswith("PLAYED"):
            # Cards were revealed, next turn
            if self.state:
                self.state.turn += 1
        elif message.startswith("ROUND_END"):
            # Round ended
            if self.state:
                self.state.played_cards = []
        elif message.startswith("GAME_END"):
            print("Game over!")
            return False
        elif message.startswith("WAITING"):
            # Our move was accepted, waiting for others
            pass
        return True

    def play_turn(self):
        """Play a single turn."""
        if not self.state or not self.state.hand:
            return

        card_index = self.choose_card(self.state.hand)

        # Track the card we're about to play
        played_card = self.state.hand[card_index]

        response = self.play_card(card_index)

        if response.startswith("OK"):
            if self.state:
                self.state.played_cards.append(played_card)

    def run(self, game_id: str, player_name: str):
        """Main game loop."""
        try:
            self.connect()

            if not self.join_game(game_id, player_name):
                return

            # Signal ready
            response = self.signal_ready()

            # Main game loop
            running = True
            while running:
                # Check for incoming messages
                message = self.receive()
                running = self.handle_message(message)

                # If we received our hand, play a card
                if message.startswith("HAND") and self.state and self.state.hand:
                    self.play_turn()

        except KeyboardInterrupt:
            print("\nDisconnecting...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.disconnect()


def main():
    if len(sys.argv) != 3:
        print("Usage: python b_v_sushi_go_client.py <game_id> <player_name>")
        print("Example: python b_v_sushi_go_client.py abc123 MyBot")
        sys.exit(1)

    game_id = sys.argv[1]
    player_name = sys.argv[2]

    client = SushiGoClient("localhost", 7878)
    client.run(game_id, player_name)


if __name__ == "__main__":
    main()
