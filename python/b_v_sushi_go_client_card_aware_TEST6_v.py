#!/usr/bin/env python3
import re
import socket
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class GameState:
    game_id: str
    player_id: int
    hand: list[str]
    player_name: str = ""
    round: int = 1
    turn: int = 1
    played_cards: list[str] = None
    opponent_cards: dict = None

    def __post_init__(self):
        if self.played_cards is None: self.played_cards = []
        if self.opponent_cards is None: self.opponent_cards = {}

    def opponent_total(self, card: str) -> int:
        return sum(cards.count(card) for cards in self.opponent_cards.values())


class SushiGoClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.state: Optional[GameState] = None
        self._recv_buffer = ""

        # Base Priorities (used when no tactical override is triggered)
        self.PRIORITIES = {
            (1, "early"): ["Squid Nigiri", "Wasabi", "Salmon Nigiri", "Tempura", "Maki Roll (3)", "Dumpling", "Pudding",
                           "Sashimi"],
            (2, "early"): ["Squid Nigiri", "Wasabi", "Salmon Nigiri", "Pudding", "Maki Roll (3)", "Tempura", "Dumpling",
                           "Sashimi"],
            (3, "early"): ["Pudding", "Squid Nigiri", "Wasabi", "Salmon Nigiri", "Maki Roll (3)", "Tempura", "Dumpling",
                           "Sashimi"]
        }

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def send(self, command: str):
        self.sock.sendall((command + "\n").encode("utf-8"))

    def receive(self) -> str:
        while "\n" not in self._recv_buffer:
            chunk = self.sock.recv(4096)
            if not chunk: raise ConnectionError("Server closed connection")
            self._recv_buffer += chunk.decode("utf-8", errors="replace")
        line, self._recv_buffer = self._recv_buffer.split("\n", 1)
        return line.strip()

    def handle_message(self, message: str):
        if message.startswith("HAND"):
            payload = message[len("HAND "):]
            cards = [m.group(2).strip() for m in re.finditer(r"(\d+):(.*?)(?=\s\d+:|$)", payload)]
            if self.state: self.state.hand = cards
        elif message.startswith("ROUND_START"):
            if self.state:
                self.state.round = int(message.split()[1])
                self.state.turn = 1
                self.state.played_cards = []
                self.state.opponent_cards = {}
        elif message.startswith("PLAYED"):
            payload = message[7:]
            for seg in payload.split("; "):
                if ":" in seg:
                    name, cards_str = seg.split(":", 1)
                    if self.state and name.strip() != self.state.player_name:
                        cards = [c.strip() for c in cards_str.split(",") if c.strip()]
                        # Overwrite or extend opponent tracking
                        self.state.opponent_cards[name.strip()] = cards
            if self.state: self.state.turn += 1
        elif message.startswith("GAME_END"):
            print(f"FINAL_RESULT: {message}")
            return False
        return True

    def choose_card(self, hand: list[str]) -> int:
        # 1. TACTICAL OVERRIDE: Hate Drafting
        # If an opponent is one card away from a high-value set (Sashimi or Tempura), steal it.
        for opponent, cards in self.state.opponent_cards.items():
            if cards.count("Sashimi") % 3 == 2 and "Sashimi" in hand:
                return hand.index("Sashimi")
            if cards.count("Tempura") % 2 == 1 and "Tempura" in hand:
                return hand.index("Tempura")

        # 2. TACTICAL OVERRIDE: Self-Completion
        if self.state.played_cards.count("Sashimi") % 3 == 2 and "Sashimi" in hand:
            return hand.index("Sashimi")
        if self.state.played_cards.count("Tempura") % 2 == 1 and "Tempura" in hand:
            return hand.index("Tempura")

        # 3. Wasabi Synergy
        if "Wasabi" in self.state.played_cards and not any(
                n in self.state.played_cards[-1:] for n in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]):
            for n in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if n in hand: return hand.index(n)

        # 4. Fallback to Dynamic Priority
        phase = "early" if self.state.turn <= 3 else "mid" if self.state.turn <= 7 else "late"
        priority = list(self.PRIORITIES.get((self.state.round, "early"), self.PRIORITIES[(1, "early")]))

        # 5. TACTICAL OVERRIDE: Avoid contested Sashimi
        # If opponents are already hoarding Sashimi, it's too risky to start now.
        if self.state.opponent_total("Sashimi") > 2 and self.state.played_cards.count("Sashimi") == 0:
            if "Sashimi" in priority: priority.remove("Sashimi")

        # Select best available
        for card in priority:
            if card in hand: return hand.index(card)

        # Ultimate fallback
        return 0

    def run(self, game_id: str, player_name: str):
        self.connect()
        self.send(f"JOIN {game_id} {player_name}")
        running = True
        while running:
            message = self.receive()
            if message.startswith("WELCOME"):
                parts = message.split()
                self.state = GameState(game_id=parts[1], player_id=int(parts[2]), hand=[], player_name=player_name)
                self.send("READY")
            running = self.handle_message(message)
            if message.startswith("HAND") and self.state and self.state.hand:
                idx = self.choose_card(self.state.hand)
                played_card = self.state.hand[idx]
                self.send(f"PLAY {idx}")
                self.state.played_cards.append(played_card)



if __name__ == "__main__":
    import sys
    # Safety check: ensures all 4 arguments required by the benchmark are present
    if len(sys.argv) < 5:
        print("Usage: python script.py <host> <port> <game_id> <player_name>")
        sys.exit(1)

    # Unpack arguments provided by the benchmarker
    host = sys.argv[1]
    port = int(sys.argv[2])
    gid = sys.argv[3]
    name = sys.argv[4]

    # Initialize and run the adaptive tactician
    client = SushiGoClient(host, port)
    client.run(gid, name)