import sys
import os
from evaluate_gdl import get_evaluation_results
import argparse
import time
import pandas as pd
from simulate import players
from parser import Parser

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files.")
    parser.add_argument('max_move_count', type=int, nargs="?", default=1000, help="Maximum number of moves to perform per game.")
    parser.add_argument('game_count', type=int, nargs="?", default=10, help="Number of games to simulate.")
    parser.add_argument('--should-log', action="store_true", help="If true, also saves the evaluation logs.")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    parser.add_argument('--bot', type=str, default="dfs-heuristic", help=f"Choose the bot to play the game. Options are: {list(players.keys())}, default: dfs-heuristic")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    outpath = args.dir # save in the same path
    should_log = args.should_log
    ignore_errors = args.ignore_errors
    max_move_count = args.max_move_count
    game_count = args.game_count
    player_creator = lambda: players[args.bot](None)

    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']

    verdicts = []
    names = []
    hashes = []
    os.makedirs(outpath, exist_ok=True)
    dfs: list[pd.DataFrame] = []
    for i, filename in enumerate(filenames):
        with open(os.path.join(dir, filename), 'r') as f:
            gdl = f.read()
        name = Parser.get_name(gdl)
        log_filename: str|None = os.path.join(outpath, f"{i}_{name}.log") if should_log else None
        try:
            dfs.append(get_evaluation_results(gdl, max_move_count, game_count, player_creator=player_creator, should_log=should_log, save_as=None, log_at=log_filename))
        except Exception as e:
            print(f"Error parsing/evaluating {name}")
            print(f"!!![ERROR]: {e}")
            if not ignore_errors:
                raise e
    if len(dfs) > 0:
        all_df = pd.concat(dfs, ignore_index=True)
        all_df.to_csv(os.path.join(outpath, "evaluation.csv"))