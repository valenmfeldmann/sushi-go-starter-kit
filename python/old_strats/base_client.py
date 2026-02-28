#!/usr/bin/env python3
"""Shared infrastructure for all Sushi Go experiment clients (1-5)."""

import re
import socket
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

NIGIRI = ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]
MAKI = ["Maki Roll (3)", "Maki Roll (2)", "Maki Roll (1)"]


@dataclass
class GameState:
    game_id: str
    player_id: int
    hand: list[str]
    player_name: str = ""
    round: int = 1
    turn: int = 1
    played_cards: list[str] = None
    has_chopsticks: bool = False
    has_unused_wasabi: bool = False
    opponent_cards: dict = None  # {player_name: [cards played this round]}

    def __post_init__(self):
        if self.played_cards is None:
            self.played_cards = []
        if self.opponent_cards is None:
            self.opponent_cards = {}

    def count_played(self, card: str) -> int:
        return self.played_cards.count(card)

    def opponent_total(self, card: str) -> int:
        """Total times any opponent has played this card this round."""
        return sum(cards.count(card) for cards in self.opponent_cards.values())

    def any_opponent_has(self, card: str) -> bool:
        return any(card in cards for cards in self.opponent_cards.values())


class SushiGoClient(ABC):
    def __init__(self, host="localhost", port=7878):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.state: Optional[GameState] = None
        self._buf = ""

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._buf = ""
        print(f"Connected to {self.host}:{self.port}")

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def send(self, cmd: str):
        self.sock.sendall((cmd + "\n").encode())
        print(f">>> {cmd}")

    def receive(self) -> str:
        while True:
            if "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                msg = line.strip()
                print(f"<<< {msg}")
                return msg
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Server closed connection")
            self._buf += chunk.decode("utf-8", errors="replace")

    def receive_until(self, pred) -> str:
        while True:
            msg = self.receive()
            if msg and pred(msg):
                return msg

    def join_game(self, game_id: str, player_name: str) -> bool:
        self.send(f"JOIN {game_id} {player_name}")
        resp = self.receive_until(
            lambda l: l.startswith("WELCOME") or l.startswith("ERROR")
        )
        if resp.startswith("WELCOME"):
            parts = resp.split()
            self.state = GameState(
                game_id=parts[1], player_id=int(parts[2]),
                hand=[], player_name=player_name,
            )
            return True
        print(f"Failed to join: {resp}")
        return False

    def parse_hand(self, message: str):
        payload = message[5:]
        cards = [m.group(2).strip() for m in re.finditer(r"(\d+):(.*?)(?=\s\d+:|$)", payload)]
        if self.state:
            self.state.hand = cards
            self.state.has_chopsticks = "Chopsticks" in self.state.played_cards
            wasabi_count = self.state.played_cards.count("Wasabi")
            nigiri_count = sum(self.state.played_cards.count(n) for n in NIGIRI)
            self.state.has_unused_wasabi = wasabi_count > nigiri_count

    def parse_played(self, message: str):
        """Parse PLAYED message to track opponent cards.
        Format: PLAYED Alice:Squid Nigiri; Bob:Tempura,Wasabi
        """
        payload = message[7:]  # strip "PLAYED "
        for seg in payload.split("; "):
            if ":" not in seg:
                continue
            name, cards_str = seg.split(":", 1)
            name = name.strip()
            if self.state and name != self.state.player_name:
                cards = [c.strip() for c in cards_str.split(",") if c.strip()]
                self.state.opponent_cards.setdefault(name, []).extend(cards)

    def handle_message(self, message: str) -> bool:
        if message.startswith("HAND"):
            self.parse_hand(message)
        elif message.startswith("ROUND_START"):
            if self.state:
                self.state.round = int(message.split()[1])
                self.state.turn = 1
                self.state.played_cards = []
                self.state.opponent_cards = {}
        elif message.startswith("PLAYED"):
            self.parse_played(message)
            if self.state:
                self.state.turn += 1
        elif message.startswith("ROUND_END"):
            if self.state:
                self.state.played_cards = []
        elif message.startswith("GAME_END"):
            print("Game over!")
            return False
        return True

    @abstractmethod
    def choose_card(self, hand: list[str]) -> int:
        """Implement this in subclasses to define card-selection strategy."""

    def play_turn(self):
        if not self.state or not self.state.hand:
            return
        idx = self.choose_card(self.state.hand)
        played = self.state.hand[idx]
        self.send(f"PLAY {idx}")
        resp = self.receive()
        if resp.startswith("OK") and self.state:
            self.state.played_cards.append(played)

    def run(self, game_id: str, player_name: str):
        try:
            self.connect()
            if not self.join_game(game_id, player_name):
                return
            self.send("READY")
            self.receive()
            running = True
            while running:
                msg = self.receive()
                running = self.handle_message(msg)
                if msg.startswith("HAND") and self.state and self.state.hand:
                    self.play_turn()
        except KeyboardInterrupt:
            print("\nDisconnecting...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.disconnect()

