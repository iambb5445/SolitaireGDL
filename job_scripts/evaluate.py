import sys
import os
import argparse
import pandas as pd
# need to add this because parser is an existing python module :|
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from evaluate_gdl import get_evaluation_results
from simulate import players
from parser import Parser
from utility import get_seed

seed_max = 1000000000

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files.")
    parser.add_argument('max_move_count', type=int, nargs="?", default=1000, help="Maximum number of moves to perform per game.")
    parser.add_argument('game_count', type=int, nargs="?", default=10, help="Number of games to simulate.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for creating the gdls.")
    parser.add_argument('--should-log', action="store_true", help="If true, also saves the evaluation logs.")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    parser.add_argument('--comment-errors', action="store_true", help="If true, errors will be added as comments to the end of the GDL. !!! This will cause it to stop running games for that gdl to avoid overcommenting on one file.")
    parser.add_argument('--bot', type=str, default="dfs-heuristic", help=f"Choose the bot to play the game. Options are: {list(players.keys())}, default: dfs-heuristic")
    parser.add_argument('--worker-index', type=int, default=None, help=f"The index of worker. Used for parallelism.")
    parser.add_argument('--worker-count', type=int, default=1, help=f"Number of workers. Used for parallelism.")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    outpath = args.dir # save in the same path
    should_log = args.should_log
    ignore_errors = args.ignore_errors
    comment_errors = args.comment_errors
    max_move_count = args.max_move_count
    game_count = args.game_count
    player_creator = lambda: players[args.bot](None)
    worker_index = args.worker_index
    worker_count = args.worker_count
    seed = args.seed

    experiment_seed: int = args.seed if args.seed is not None else get_seed(None, seed_max)
    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    if worker_index is not None:
        assert worker_count >= 1, "Cannot have a negative or zero worker count"
        assert worker_index < worker_count, "Worker index should be in range [0, worker_count)"
        filenames = [name for id, name in enumerate(filenames) if id % worker_count == worker_index]

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
            dfs.append(get_evaluation_results(gdl, max_move_count, game_count, player_creator=player_creator, should_log=should_log, save_as=None, log_at=log_filename, experiment_seed=experiment_seed))
        except Exception as e:
            print(f"Error parsing/evaluating {name}")
            print(f"!!![ERROR]: {e}")
            if comment_errors:
                with open(os.path.join(dir, filename), 'a') as f:
                    f.write("\n\n# ERROR when using this gdl:\n" + "\n".join([f"# {line}" for line in str(e).splitlines()]))
                continue
            if not ignore_errors:
                raise e
    if len(dfs) > 0:
        all_df = pd.concat(dfs, ignore_index=True)
        all_df.to_csv(os.path.join(outpath, f"evaluation_worker_{worker_index}.csv" if worker_index is not None else "evaluation.csv"))