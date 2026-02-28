import subprocess
import time
import json
import urllib.request
import re
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# --- Configuration ---
SERVER_HOST = "localhost"
SERVER_PORT = 7878
WEB_URL = "http://localhost:8080/api/games"
# Ensure all bot files are in the same directory as this script
STRATEGIES = ["first_card_bot.py", "sushi_go_client.py", "sushi_go_client.py", "b_v_sushi_go_client_card_aware_TEST.py"]
NUM_ROUNDS = 10  # Increase this for better data!


def create_game(num_players):
    """Creates a new game via the REST API."""
    data = json.dumps({"max_players": num_players}).encode('utf-8')
    req = urllib.request.Request(WEB_URL, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as response:
            return response.getcode() == 200
    except:
        return False


def get_waiting_game_ids():
    """Fetches the game list and returns IDs for all 'waiting' games."""
    try:
        with urllib.request.urlopen(WEB_URL) as response:
            data = json.loads(response.read().decode())
            games_list = data.get('games', [])
            return [g['id'] for g in games_list if g.get('status') == "waiting"]
    except:
        return []


def print_leaderboard(win_matrix, strat_names):
    """
    Calculates total wins for each strategy and prints an ordered leaderboard.
    A 'win' is counted each time a strategy beats any other player in a round.
    """
    # Sum across the rows to get total head-to-head wins for each bot
    total_wins = np.sum(win_matrix, axis=1)

    # Pair names with their win counts and sort descending
    leaderboard = sorted(zip(strat_names, total_wins), key=lambda x: x[1], reverse=True)

    print("\n" + "=" * 30)
    print("      FINAL LEADERBOARD")
    print("=" * 30)
    print(f"{'Strategy':<25} | {'Total Wins':<10}")
    print("-" * 30)
    for name, wins in leaderboard:
        print(f"{name:<25} | {int(wins):<10}")
    print("=" * 30 + "\n")


def run_bench():
    num_strats = len(STRATEGIES)
    # matrix[i][j] = how many times strat i beat strat j
    win_matrix = np.zeros((num_strats, num_strats), dtype=int)
    strat_names = [s.replace('.py', '') for s in STRATEGIES]

    print(f"--- Starting Benchmark with JSON-Aware Parsing ---")

    for i in range(NUM_ROUNDS):
        create_game(num_strats)
        time.sleep(0.5)
        ids = get_waiting_game_ids()
        if not ids: continue
        game_id = ids[-1]

        procs = []
        for idx, script in enumerate(STRATEGIES):
            name = f"{script.split('.')[0]}_{idx}"
            cmd = ["python3", script, SERVER_HOST, str(SERVER_PORT), game_id, name]
            procs.append((idx, subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)))

        game_scores = {}
        for idx, p in procs:
            stdout, _ = p.communicate()
            match = re.search(r"FINAL_RESULT: GAME_END (.*)", stdout)
            if match:
                raw_data = match.group(1).strip()
                # Find all "key": value or key: value pairs
                found_scores = re.findall(r'["\']?([\w-]+)["\']?\s*[:=]\s*(\d+)', raw_data)
                for p_name, p_score in found_scores:
                    game_scores[p_name] = int(p_score)

        if game_scores:
            print(f"  Scores captured: {game_scores}")
            for w_idx in range(num_strats):
                w_name = f"{strat_names[w_idx]}_{w_idx}"
                for l_idx in range(num_strats):
                    if w_idx == l_idx: continue
                    l_name = f"{strat_names[l_idx]}_{l_idx}"
                    if game_scores.get(w_name, 0) > game_scores.get(l_name, 0):
                        win_matrix[w_idx][l_idx] += 1

        print(f"Round {i + 1}/{NUM_ROUNDS} complete.")

    # 1. Print the text-based leaderboard
    print_leaderboard(win_matrix, strat_names)

    # 2. Save to CSV and generate Heatmap
    df = pd.DataFrame(win_matrix, index=strat_names, columns=strat_names)
    df.to_csv("win_matrix.csv")

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(win_matrix, cmap="YlGn")
    ax.set_xticks(np.arange(num_strats), labels=strat_names)
    ax.set_yticks(np.arange(num_strats), labels=strat_names)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    for i in range(num_strats):
        for j in range(num_strats):
            ax.text(j, i, int(win_matrix[i, j]), ha="center", va="center", color="black")

    ax.set_title(f"Sushi Go Bot Win Matrix (Rows beat Columns)\n{NUM_ROUNDS} Rounds")
    ax.set_xlabel("Loser Strategy")
    ax.set_ylabel("Winner Strategy")
    fig.tight_layout()
    plt.savefig("win_heatmap.png")
    print("Success! Results saved to win_matrix.csv and win_heatmap.png")


if __name__ == "__main__":
    run_bench()



# import subprocess
# import time
# import json
# import urllib.request
# import re
# import os
# import matplotlib.pyplot as plt
# import numpy as np
# import pandas as pd
#
# # --- Configuration ---
# SERVER_HOST = "localhost"
# SERVER_PORT = 7878
# WEB_URL = "http://localhost:8080/api/games"
# STRATEGIES = ["first_card_bot.py", "sushi_go_client.py", "sushi_go_client.py", "b_v_sushi_go_client_card_aware_TEST.py"]
# NUM_ROUNDS = 10 # Increase this for better data!
#
# def create_game(num_players):
#     data = json.dumps({"max_players": num_players}).encode('utf-8')
#     req = urllib.request.Request(WEB_URL, data=data, method='POST')
#     req.add_header('Content-Type', 'application/json')
#     try:
#         with urllib.request.urlopen(req) as response:
#             return response.getcode() == 200
#     except: return False
#
# def get_waiting_game_ids():
#     try:
#         with urllib.request.urlopen(WEB_URL) as response:
#             data = json.loads(response.read().decode())
#             games_list = data.get('games', [])
#             return [g['id'] for g in games_list if g.get('status') == "waiting"]
#     except: return []
#
# def run_bench():
#     num_strats = len(STRATEGIES)
#     win_matrix = np.zeros((num_strats, num_strats), dtype=int)
#     strat_names = [s.replace('.py', '') for s in STRATEGIES]
#
#     print(f"--- Starting Benchmark with JSON-Aware Parsing ---")
#
#     for i in range(NUM_ROUNDS):
#         create_game(num_strats)
#         time.sleep(0.5)
#         ids = get_waiting_game_ids()
#         if not ids: continue
#         game_id = ids[-1]
#
#         procs = []
#         for idx, script in enumerate(STRATEGIES):
#             name = f"{script.split('.')[0]}_{idx}"
#             cmd = ["python3", script, SERVER_HOST, str(SERVER_PORT), game_id, name]
#             procs.append((idx, subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)))
#
#
#         game_scores = {}
#         for idx, p in procs:
#             stdout, _ = p.communicate()
#             # Look for the FINAL_RESULT line
#             match = re.search(r"FINAL_RESULT: GAME_END (.*)", stdout)
#             if match:
#                 raw_data = match.group(1).strip()
#
#                 # REPLACEMENT LOGIC: Find all "key": value or key: value pairs
#                 # This works for both JSON {"name": 10} and legacy name: 10 formats
#                 found_scores = re.findall(r'["\']?([\w-]+)["\']?\s*[:=]\s*(\d+)', raw_data)
#
#                 for p_name, p_score in found_scores:
#                     game_scores[p_name] = int(p_score)
#
#         # Calculate wins for the matrix
#         if game_scores:
#             print(f"  Scores captured: {game_scores}")  # Debug print to see it working!
#             for w_idx in range(num_strats):
#                 w_name = f"{strat_names[w_idx]}_{w_idx}"
#                 for l_idx in range(num_strats):
#                     if w_idx == l_idx: continue
#                     l_name = f"{strat_names[l_idx]}_{l_idx}"
#                     if game_scores.get(w_name, 0) > game_scores.get(l_name, 0):
#                         win_matrix[w_idx][l_idx] += 1
#
#         print(f"Round {i+1}/{NUM_ROUNDS} complete.")
#
#     # Save to CSV and generate Heatmap
#     df = pd.DataFrame(win_matrix, index=strat_names, columns=strat_names)
#     df.to_csv("win_matrix.csv")
#
#     fig, ax = plt.subplots(figsize=(10, 8))
#     im = ax.imshow(win_matrix, cmap="YlGn")
#     ax.set_xticks(np.arange(num_strats), labels=strat_names)
#     ax.set_yticks(np.arange(num_strats), labels=strat_names)
#     plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
#
#     for i in range(num_strats):
#         for j in range(num_strats):
#             ax.text(j, i, int(win_matrix[i, j]), ha="center", va="center", color="black")
#
#     ax.set_title(f"Sushi Go Bot Win Matrix (Rows beat Columns)\n{NUM_ROUNDS} Rounds")
#     ax.set_xlabel("Loser Strategy")
#     ax.set_ylabel("Winner Strategy")
#     fig.tight_layout()
#     plt.savefig("win_heatmap.png")
#     print("\nSuccess! Results saved to win_matrix.csv and win_heatmap.png")
#
# if __name__ == "__main__":
#     run_bench()
#
#
