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
    parser.add_argument('step', type=int, nargs="?", default=1, help="Step value in case not all files need to be evaluated (used mostly for testing purposes).")
    parser.add_argument('max_move_count', type=int, nargs="?", default=1000, help="Maximum number of moves to perform per game.")
    parser.add_argument('game_count', type=int, nargs="?", default=10, help="Number of games to simulate.")
    parser.add_argument('outpath', type=str, help="Path to save the csv results of evaluation.")
    parser.add_argument('--add-timestamp', action="store_true", help="If true, will make a directory in outpath based on timestamp.")
    parser.add_argument('--should-log', action="store_true", help="If true, also saves the evaluation logs.")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluate a batch of gdls that may be invalid.")
    parser.add_argument('--bot', type=str, default="dfs-heuristic", help=f"Choose the bot to play the game. Options are: {list(players.keys())}, default: dfs-heuristic")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    step = args.step
    outpath = args.outpath
    add_timestamp = args.add_timestamp
    should_log = args.should_log
    ignore_errors = args.ignore_errors
    max_move_count = args.max_move_count
    game_count = args.game_count
    player_creator = lambda: players[args.bot](None)

    print(f"Evaluating games in {dir}" + (f" with step {step}" if step != 1 else ""))

    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    filenames = [name for id, name in enumerate(filenames) if id % step == 0]
    gdls: list[str] = []
    for filename in filenames:
        with open(os.path.join(dir, filename), 'r') as f:
            gdls.append(f.read())
    print(f"Read {len(gdls)} files")

    if add_timestamp:
        outpath = os.path.join(outpath, f"{int(time.time())}")
    os.makedirs(outpath, exist_ok=True)
    dfs: list[pd.DataFrame] = []
    for i, gdl in enumerate(gdls):
        name = Parser.get_name(gdl)
        csv_filename: str = os.path.join(outpath, f"{i}_{name}.csv")
        # I'm using the if here to prevent errors if path exists but log set to None
        # this logic can't be in logger, since logger doesn't know if logs are gonna get activated at some point (and I don't want a logger runtime check)
        log_filename: str|None = os.path.join(outpath, f"{i}_{name}.log") if should_log else None
        try:
            # TODO add verdict
            dfs.append(get_evaluation_results(gdl, max_move_count, game_count, player_creator=player_creator, should_log=should_log, save_as=csv_filename, log_at=log_filename))
        except Exception as e:
            print(f"Error parsing/evaluating {name}")
            print(e)
            if not ignore_errors:
                raise e
    if len(dfs) > 0:
        all_df = pd.concat(dfs, ignore_index=True)
        all_df.to_csv(os.path.join(outpath, "all.csv"))