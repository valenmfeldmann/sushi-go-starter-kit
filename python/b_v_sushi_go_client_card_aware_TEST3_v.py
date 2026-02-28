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
    # SOPHISTICATION: Tracks which cards have been seen in circulation
    seen_in_round: list[str] = None

    def __post_init__(self):
        if self.played_cards is None: self.played_cards = []
        if self.opponent_cards is None: self.opponent_cards = {}
        if self.seen_in_round is None: self.seen_in_round = []


class SushiGoClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.state: Optional[GameState] = None
        self._recv_buffer = ""

        # BASE PRIORITIES: Optimized for Points-Per-Card (PPC)
        self.PRIORITIES = {
            (1, "early"): ["Wasabi", "Squid Nigiri", "Tempura", "Sashimi", "Salmon Nigiri", "Maki Roll (3)",
                           "Dumpling"],
            (2, "early"): ["Pudding", "Wasabi", "Squid Nigiri", "Tempura", "Salmon Nigiri", "Maki Roll (3)"],
            (3, "early"): ["Pudding", "Squid Nigiri", "Wasabi", "Salmon Nigiri", "Tempura", "Sashimi"]
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
            if self.state:
                self.state.hand = cards
                # RECORD MEMORY: Track what cards are currently in this hand
                self.state.seen_in_round.extend(cards)
        elif message.startswith("ROUND_START"):
            if self.state:
                self.state.round = int(message.split()[1])
                self.state.turn = 1
                self.state.played_cards = []
                self.state.seen_in_round = []
        elif message.startswith("PLAYED"):
            # TRACKING OPPONENTS: Essential for "Hate Drafting" logic
            payload = message[7:]
            for seg in payload.split("; "):
                if ":" in seg:
                    name, cards_str = seg.split(":", 1)
                    if self.state and name.strip() != self.state.player_name:
                        cards = [c.strip() for c in cards_str.split(",") if c.strip()]
                        self.state.opponent_cards[name.strip()] = cards
            if self.state: self.state.turn += 1
        elif message.startswith("GAME_END"):
            print(f"FINAL_RESULT: {message}")
            return False
        return True

    def choose_card(self, hand: list[str]) -> int:
        phase = "early" if self.state.turn <= 3 else "mid" if self.state.turn <= 7 else "late"
        # Start with the highest value card from base logic
        priority = list(self.PRIORITIES.get((self.state.round, "early"), self.PRIORITIES[(1, "early")]))

        # --- SOPHISTICATED LOGIC OVERRIDES ---

        # 1. HATE DRAFTING: Deny opponents high-value finishes
        for opp, cards in self.state.opponent_cards.items():
            if cards.count("Sashimi") % 3 == 2 and "Sashimi" in hand:
                # Denying a 10pt set is worth more than gaining 3pts for ourselves
                return hand.index("Sashimi")

        # 2. WASABI COMBO: Always maximize Wasabi with the best available Nigiri
        if "Wasabi" in self.state.played_cards and not any(
                n in self.state.played_cards for n in ["Squid Nigiri", "Salmon Nigiri"]):
            for best_nigiri in ["Squid Nigiri", "Salmon Nigiri"]:
                if best_nigiri in hand: return hand.index(best_nigiri)

        # 3. SET ABANDONMENT: Don't chase Sashimi if they aren't in the deck
        if "Sashimi" in hand and self.state.played_cards.count("Sashimi") % 3 == 1:
            # If we've seen 10 hands and no more Sashimi, abandon the set
            if self.state.seen_in_round.count("Sashimi") < 3 and phase == "late":
                priority.remove("Sashimi")

        # Fallback to standard priorities
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
    host, port, gid, name = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    SushiGoClient(host, port).run(gid, name)