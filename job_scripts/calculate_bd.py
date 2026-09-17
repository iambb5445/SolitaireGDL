import sys
import os
import argparse
import pandas as pd
# need to add this because parser is an existing python module :|
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from parser import Parser
from calcualte_gdl_bd import get_bd_metrics
from utility import get_seed

seed_max = 1000000000

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files. Is searched recursively.")
    parser.add_argument('game_count', type=int, nargs="?", default=10, help="Number of games to simulate.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for shuffling the cards in games.")
    # disabled logging. since the calculation is super fast and doesn't make any decisions, logs are not very useful
    # parser.add_argument('--should-log', action="store_true", help="If true, also saves the bds logs.")
    parser.add_argument('--hash-as-seed', action="store_true", help="If true, uses the hash of the gdl as seed to ensure evaluation results are always the same (and consistent with evaluation).")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    game_count = args.game_count
    should_log = False # args.should_log
    hash_as_seed = args.hash_as_seed
    ignore_errors = args.ignore_errors

    experiment_seed: int|None = args.seed if args.seed is not None else get_seed(None, seed_max)

    filepaths: list[str] = []
    for root, _, files in os.walk(dir):
        for f in files:
            if f.endswith('.sgdl'):
                filepaths.append(os.path.join(root, f))

    dfs = []
    for filepath in sorted(filepaths):
        with open(filepath, 'r') as f:
            gdl = f.read()
        try:
            name = Parser.get_name(gdl)
            if args.hash_as_seed:
                experiment_seed = None
            metrics = get_bd_metrics(gdl=gdl, game_count=game_count, should_log=should_log,
                                     save_as=None, log_at=None, experiment_seed=experiment_seed)
            dfs.append(metrics)
        except Exception as e:
            print(f"!!![ERROR] {filepath}: {e}")
            if not ignore_errors:
                raise

    if len(dfs) > 0:
        all_df: pd.DataFrame = pd.concat(dfs, ignore_index=True)
        all_df.to_csv(os.path.join(dir, f"bd_metrics.csv"), index=False)
