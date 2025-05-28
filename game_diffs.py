from parser import Parser
from diffs import Diffs
import pandas as pd

if __name__ == '__main__':
    game_filenames = ['games\\klondike.sgdl', 'games\\spider.sgdl']#, 'games\\easiestspider.sgdl']
    games = [Parser.from_file(filename, None, False, True) for filename in game_filenames]
    diff_vals: list[list[float]] = [[0 for _ in games] for _ in games]
    diff_points: list[list[float]] = [[0 for _ in games] for _ in games]
    for i in range(len(games)):
        for j in range(len(games)):
            diff = games[i].diff(games[j], True, Diffs.get_sum_normalized_diff_normalized)
            diff_vals[i][j] = diff.get_sum_normalized_diff_normalized()
            diff_points[i][j] = diff.get_normalized_diff_points()
    names: list[str] = [game.name for game in games]
    print('-' * 25)
    print(pd.DataFrame(diff_vals, columns=names, index=names))
    print('-' * 25)
    print(pd.DataFrame(diff_points, columns=names, index=names))
    print('-' * 25)