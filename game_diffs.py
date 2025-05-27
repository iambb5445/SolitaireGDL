from parser import Parser
from diffs import Diffs

if __name__ == '__main__':
    game_filenames = ['games\\klondike.sgdl', 'games\\spider.sgdl']
    games = [Parser.from_file(filename, None, False, True) for filename in game_filenames]
    for game1 in games:
        for game2 in games:
            diff = game1.diff(game2, True, Diffs.get_sum_normalized_diff_normalized)
            print(f'Diff between {game1.name} and {game2.name} is {diff.get_sum_normalized_diff_normalized()}, {diff.get_normalized_diff_points()}')