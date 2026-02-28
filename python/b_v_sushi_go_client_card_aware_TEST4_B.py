#!/usr/bin/env python3
# Strategy: PUDDING SNIPER — lock down pudding first every round, then go nigiri
import random
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

        self.PRIORITIES = {
            (1, "early"): [
                "Pudding",
                "Squid Nigiri",
                "Wasabi",
                "Salmon Nigiri",
                "Sashimi",
                "Tempura",
                "Maki Roll (3)",
                "Dumpling",
                "Maki Roll (2)",
                "Egg Nigiri",
                "Maki Roll (1)",
                "Chopsticks",
            ],
            (1, "mid"): [
                "Pudding",
                "Squid Nigiri",
                "Wasabi",
                "Salmon Nigiri",
                "Tempura",
                "Sashimi",
                "Maki Roll (3)",
                "Dumpling",
                "Maki Roll (2)",
                "Egg Nigiri",
                "Maki Roll (1)",
                "Chopsticks",
            ],
            (1, "late"): [
                "Pudding",
                "Squid Nigiri",
                "Salmon Nigiri",
                "Tempura",
                "Sashimi",
                "Maki Roll (3)",
                "Dumpling",
                "Maki Roll (2)",
                "Wasabi",
                "Egg Nigiri",
                "Maki Roll (1)",
                "Chopsticks",
            ],
            (2, "early"): [
                "Pudding",
                "Squid Nigiri",
                "Wasabi",
                "Salmon Nigiri",
                "Maki Roll (3)",
                "Tempura",
                "Sashimi",
                "Dumpling",
                "Maki Roll (2)",
                "Egg Nigiri",
                "Maki Roll (1)",
                "Chopsticks",
            ],
            (2, "mid"): [
                "Pudding",
                "Squid Nigiri",
                "Salmon Nigiri",
                "Wasabi",
                "Maki Roll (3)",
                "Tempura",
                "Sashimi",
                "Dumpling",
                "Maki Roll (2)",
                "Egg Nigiri",
                "Maki Roll (1)",
                "Chopsticks",
            ],
            (2, "late"): [
                "Pudding",
                "Squid Nigiri",
                "Salmon Nigiri",
                "Maki Roll (3)",
                "Tempura",
                "Dumpling",
                "Maki Roll (2)",
                "Sashimi",
                "Wasabi",
                "Egg Nigiri",
                "Maki Roll (1)",
                "Chopsticks",
            ],
            (3, "early"): [
                "Pudding",
                "Squid Nigiri",
                "Wasabi",
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
                "Maki Roll (3)",
                "Wasabi",
                "Dumpling",
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
                "Maki Roll (3)",
                "Tempura",
                "Maki Roll (2)",
                "Sashimi",
                "Wasabi",
                "Egg Nigiri",
                "Maki Roll (1)",
                "Chopsticks",
            ],
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
                        self.state.opponent_cards.setdefault(name.strip(), []).extend(cards)
            if self.state: self.state.turn += 1
        elif message.startswith("GAME_END"):
            print(f"FINAL_RESULT: {message}")
            return False
        return True

    def choose_card(self, hand: list[str]) -> int:
        phase = "early" if self.state.turn <= 3 else "mid" if self.state.turn <= 7 else "late"
        priority = list(self.PRIORITIES.get((self.state.round, phase), self.PRIORITIES[(1, "early")]))

        if any(c == "Wasabi" for c in self.state.played_cards) and not any(
                c in ("Egg Nigiri", "Salmon Nigiri", "Squid Nigiri") for c in self.state.played_cards):
            for n in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if n in hand:
                    priority.insert(0, priority.pop(priority.index(n)))
                    break

        if phase in ("mid", "late"):
            if self.state.played_cards.count("Sashimi") % 3 == 2 and "Sashimi" in hand:
                priority.insert(0, priority.pop(priority.index("Sashimi")))
            elif self.state.played_cards.count("Tempura") % 2 == 1 and "Tempura" in hand:
                priority.insert(0, priority.pop(priority.index("Tempura")))

        for card in priority:
            if card in hand: return hand.index(card)
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
    if len(sys.argv) != 5:
        print("Usage: python script.py <host> <port> <game_id> <player_name>")
        sys.exit(1)

    host, port, gid, name = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    client = SushiGoClient(host, port)
    client.run(gid, name)

