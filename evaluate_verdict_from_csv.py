import sys
import os
from evaluate_gdl import get_verdict_from_results
import argparse
import pandas as pd

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files.")
    parser.add_argument('step', type=int, nargs="?", default=1, help="Step value in case not all files need to be evaluated (used mostly for testing purposes).")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    step = args.step

    print(f"Evaluating games in {dir}" + (f" with step {step}" if step != 1 else ""))

    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'csv']
    filenames = [name for id, name in enumerate(filenames) if id % step == 0]
    dfs: list[pd.DataFrame] = []
    for filename in filenames:
        dfs.append(pd.read_csv(os.path.join(dir, filename), index_col=0))
    print(f"Read {len(dfs)} files")

    for df in dfs:
        games = df["Game"].unique()
        for game in games:
            verdict = get_verdict_from_results(df[df["Game"] == game])
            print(f"Verdict for game {game} is {verdict}")