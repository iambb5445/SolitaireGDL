from simulate_many import simulate_for_player
from player import DFSPlayer, MergedHeuristic, ActionCountHeuristic, NoDrawHeuristic, WinHeuristic
import time
import json
import matplotlib.pyplot as plt
import math

max_move_count = 1000
simulation_count_per_game = 20
# from_file = '1750842589_win_percentages.out'
from_file = None
save = True

def get_win_points(wins: list[bool], move_counts: list[int]) -> list[tuple[float, float]]:
    wins_per_count = {}
    for win, move_count in zip(wins, move_counts):
        wins_per_count[move_count] = wins_per_count.get(move_count, 0) + (1 if win else 0)
    move_counts = sorted(list(set(move_counts)))
    points: list[tuple[float, float]] = []
    total = len(wins)
    win_total = 0
    for move_count in move_counts:
        win_total += wins_per_count[move_count]
        points.append((move_count, win_total/total))
    return points

if __name__ == '__main__':
    data = []
    if from_file is None:
        out_filename = f"{int(time.time())}_win_percentages.out"
        game_filenames = [
            # 'games\\klondike_family\\klondike.sgdl',
            # 'games\\klondike_family\\blindalleys.sgdl',
            # 'games\\klondike_family\\thirtysix.sgdl',
            'games\\klondike_family\\legion.sgdl',
            'games\\pairing_family\\golf.sgdl',
            'games\\freecell_family\\bakersgame.sgdl',
            # 'games\\spider_family\\spider.sgdl',
            'games\\klondike_family\\miniwestcliff.sgdl',
        ]
        for game_filename in game_filenames:
            games, move_counts, samples = simulate_for_player(simulation_count_per_game, max_move_count, True, game_filename, lambda: DFSPlayer(
                MergedHeuristic(
                    [ActionCountHeuristic(), NoDrawHeuristic(), WinHeuristic()],
                    [1, 1, 3]
                    )
                ), None, None, 0, 0, 0)
            wins: list[bool] = [game.is_win() for game in games]
            data.append({'filename': game_filename, 'game': games[0].name, "max_move_count": max_move_count, 'wins': wins, 'move_counts': move_counts})
        with open(out_filename, 'w') as f:
            json.dump(data, f)
    else:
        with open(from_file, 'r') as f:
            data = json.load(f)
    plt.figure(figsize=(10, 6))
    for game_data in data:
        print(game_data)
        points = [(0.0, 0.0)] + get_win_points(game_data['wins'], game_data['move_counts'])
        x_values = [x for x, _ in points]
        y_values = [y for _, y in points]
        exhaust_count = sum([1 if win or move_count < game_data['max_move_count'] else 0 for win, move_count in zip(game_data['wins'], game_data['move_counts'])])
        plt.plot(x_values, y_values, label = f"{game_data['game']}:{round((exhaust_count/len(game_data['wins'])) * 100, 2)}% exhausted")
    plt.legend()
    # plt.title('Win Percentages')
    plt.xlabel('Number of Moves')
    plt.ylabel('Winrate')
    plt.grid(True)
    if save:
        plt.savefig('wins.pdf',dpi=300,pad_inches=0)
    else:
        plt.show()