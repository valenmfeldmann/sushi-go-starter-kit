#!/usr/bin/env python3
"""
run_bots.py - One-command bot battle launcher.

Creates a game on the server, then spins up the selected bots to fill it.

Usage:
    python run_bots.py [num_players] [--host HOST] [--port PORT] [--webport WEBPORT]

Examples:
    python run_bots.py           # 5-player game with all 5 bots
    python run_bots.py 3         # 3-player game with bots 1, 2, 3
    python run_bots.py 2         # 2-player game with bots 1, 2
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
DEFAULT_PLAYERS = 5
HOST = "localhost"
TCP_PORT = 7878
WEB_PORT = 8080

delay_mult_startup = 0.1

# Bot scripts in priority order; rotate through them to fill slots
BOT_SCRIPTS = [
    "b_v_sushi_go_client.py",
    "client_2.py",
    "client_3.py",
    "client_4.py",
    "client_5.py",
]

BOT_NAMES = [
    "Completion",
    "MakiRush",
    "Denier",
    "Chopsticks",
    "Adaptive",
]

HERE = Path(__file__).parent
# ───────────────────────────────────────────────────────────────────────────────


def create_game(num_players: int) -> str:
    """POST /api/games → returns the new game ID."""
    url = f"http://{HOST}:{WEB_PORT}/api/games"
    payload = json.dumps({"max_players": num_players}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data["id"]
    except urllib.error.URLError as e:
        print(f"[ERROR] Could not reach web server at {url}")
        print(f"        Is the Docker container running?  ({e})")
        sys.exit(1)
    except (KeyError, json.JSONDecodeError) as e:
        print(f"[ERROR] Unexpected response from server: {e}")
        sys.exit(1)


def launch_bots(game_id: str, num_players: int) -> list[subprocess.Popen]:
    """Launch num_players bot subprocesses and return them."""
    procs = []
    for i in range(num_players):
        script = BOT_SCRIPTS[i % len(BOT_SCRIPTS)]
        name = BOT_NAMES[i % len(BOT_NAMES)]
        cmd = [sys.executable, str(HERE / script), game_id, name]
        # Small stagger so they don't all hammer the server at once
        time.sleep(0.15*delay_mult_startup)
        # Force UTF-8 so box-drawing chars in the server banner don't crash on Windows
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env=env,
        )
        procs.append((name, script, proc))
        print(f"  ✓ launched {name:12s}  ({script})  pid={proc.pid}")
    return procs


def wait_for_bots(procs: list) -> list[tuple[str, str, str]]:
    """Wait for all bots to finish and collect their output."""
    results = []
    for name, script, proc in procs:
        out, _ = proc.communicate()
        results.append((name, script, out))
    return results


def parse_game_end(output: str) -> tuple[dict | None, list | None]:
    """Extract scores and winners from a bot's captured output.

    The receive() method prints every server line as '<<< <message>'.
    GAME_END format: GAME_END {"Alice":41,"Bob":24} ["Alice"]
    """
    for line in output.splitlines():
        if "<<< GAME_END" in line:
            payload = line.split("<<< GAME_END", 1)[1].strip()
            try:
                # Split on the boundary between the JSON object and the JSON array
                bracket_pos = payload.index("[")
                scores = json.loads(payload[:bracket_pos].strip())
                winners = json.loads(payload[bracket_pos:].strip())
                return scores, winners
            except (ValueError, json.JSONDecodeError):
                pass
    return None, None


def print_summary(results: list[tuple[str, str, str]]):
    """Parse GAME_END from all bot outputs and print a ranked leaderboard."""
    # Grab scores from the first bot that has them (all see the same GAME_END)
    scores, winners = None, None
    for _, _, output in results:
        scores, winners = parse_game_end(output)
        if scores:
            break

    print("\n" + "═" * 50)
    print("  BATTLE RESULTS")
    print("═" * 50)

    if scores:
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for rank, (player, score) in enumerate(ranked, 1):
            crown = "🏆" if player in (winners or []) else "  "
            print(f"  {crown} #{rank}  {player:14s}  {score:3d} pts")
    else:
        for name, _, output in results:
            finished = "Game over!" in output
            print(f"  {name:12s}  →  {'finished' if finished else 'error/disconnected'}")

    print("═" * 50)
    print(f"\n  Watch the replay at: http://{HOST}:{WEB_PORT}")


def main():
    num_players = DEFAULT_PLAYERS
    if len(sys.argv) > 1:
        try:
            num_players = int(sys.argv[1])
            if not (2 <= num_players <= 5):
                raise ValueError
        except ValueError:
            print("Usage: python run_bots.py [num_players]  (num_players must be 2-5)")
            sys.exit(1)

    print(f"\n🍣  Sushi Go Bot Battle Launcher")
    print(f"    Players : {num_players}")
    print(f"    Server  : {HOST}:{TCP_PORT}  (web: {WEB_PORT})\n")

    print("Creating game...")
    game_id = create_game(num_players)
    print(f"  ✓ Game created: {game_id}")
    print(f"  👀 Spectate at: http://{HOST}:{WEB_PORT}\n")

    print("Launching bots...")
    procs = launch_bots(game_id, num_players)

    print(f"\nAll {num_players} bots running — waiting for game to finish...\n")
    results = wait_for_bots(procs)
    print_summary(results)


if __name__ == "__main__":
    main()

