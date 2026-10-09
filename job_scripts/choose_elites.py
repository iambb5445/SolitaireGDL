import sys
import os
import argparse
import pandas as pd
import shutil
import time
# need to add this because parser is an existing python module :|
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from evaluate_gdl import get_scores_from_results
from calcualte_gdl_bd import get_map_buckets_from_results
from parser import Parser
from typing import NamedTuple

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('eval_filename', type=str, help="Evaluation csv file.")
    parser.add_argument('bd_filename', type=str, help="BD metrics csv file.")
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files.")
    parser.add_argument('outpath', type=str, help="Path to save the sgdl results of choosing bests.")
    # TODO count per cell
    parser.add_argument('--bucket-size', type=int, default=1, help="Number of elites kept in each bucket.")
    parser.add_argument('--should-log', action="store_true", help="If true, also saves the bd log, reporting the metrics used for it.")
    parser.add_argument('--ignore-non-existent', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    parser.add_argument('--index-from-existing', action="store_true", help="If true, chooses index values for the file that continue from the existing number of files.")
    args = parser.parse_args(sys.argv[1:])
    eval_filename = args.eval_filename
    bd_filename = args.bd_filename
    dir = args.dir
    outpath = args.outpath
    should_log = args.should_log
    ignore = args.ignore_non_existent
    bucket_size = args.bucket_size
    log_filename: str|None = os.path.join(outpath, f"bd.log") if should_log else None

    eval_results = pd.read_csv(eval_filename)
    bd_results = pd.read_csv(bd_filename)
    scores = get_scores_from_results(eval_results)
    buckets = get_map_buckets_from_results(bd_results, should_log, log_filename)
    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    index = 0
    timestamp = int(time.time())
    os.makedirs(outpath, exist_ok=True)
    shutil.copy(os.path.join(dir, "history.csv"), os.path.join(outpath, "history.csv"))
    if args.index_from_existing:
        index = len([name for name in os.listdir(outpath) if name.split('.')[-1] == 'sgdl'])
    class Elite(NamedTuple):
        name: str
        hash: int
        score: float
        filename: str
    elites: dict[int, list[Elite]] = {} # alterative: keep list as heap
    for filename in filenames:
        with open(os.path.join(dir, filename), 'r') as f:
            gdl = f.read()
        hash = Parser.get_deterministic_hash(gdl)
        name = Parser.get_name(gdl)
        try:
            bucket = buckets[hash]
            score = scores[hash]
            if bucket not in elites:
                 elites[bucket] = []
            new_elite = Elite(name=name, hash=hash, score=score, filename=filename)
            if len(elites[bucket]) < bucket_size:
                elites[bucket].append(new_elite)
            elif elites[bucket][-1].score < new_elite.score:
                elites[bucket][-1] = new_elite
            elites[bucket].sort(key=lambda e: (e.score * -1))
            # alternative:
            # for i in range(len(elites[bucket]) - 1, 0, -1):
            #      if elites[bucket][i].score < elites[bucket][i-1].score:
            #           elites[bucket][i], elites[bucket][i-1] = elites[bucket][i-1], elites[bucket][i]
        except Exception as e:
            if not ignore:
                raise e
            print(f"!!![ERROR]: {e}")
    for elite_list in elites.values():
        for elite in elite_list:
            try:
                shutil.copy(os.path.join(dir, elite.filename), os.path.join(outpath, f"{index}_{elite.name}_{elite.hash}.sgdl"))
            except Exception as e:
                        if not ignore:
                            raise e
                        print(f"!!![ERROR]: {e}")
            index += 1