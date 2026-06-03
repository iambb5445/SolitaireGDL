import os
import sys
import time
import argparse
# need to add this because parser is an existing python module :|
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from parser import Parser
from random import Random
from genetic import SGDLGene
from utility import get_seed
from history import History

seed_max = 1000000000

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('count', type=int, help="Number of gdls to generate.")
    parser.add_argument('outpath', type=str, help="Path to save the sgdl results of evaluation.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for creating the gdls.")
    parser.add_argument('--add-timestamp', action="store_true", help="If true, will make a directory in outpath based on timestamp.")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    args = parser.parse_args(sys.argv[1:])
    count = args.count
    experiment_seed: int = args.seed if args.seed is not None else get_seed(None, seed_max)
    experiment_rnd = Random(experiment_seed)
    seeds = [get_seed(experiment_rnd, seed_max) for _ in range(count)]
    outpath = args.outpath
    timestamp = int(time.time())
    if args.add_timestamp:
        outpath = os.path.join(outpath, f"{timestamp}")
    history = History()
    os.makedirs(outpath, exist_ok=True)
    for i, seed in enumerate(seeds):
        try:
            gene = SGDLGene.get_random(Random(seed))
            gdl = gene.get_gdl()
            name = Parser.get_name(gdl)
            hash = SGDLGene._get_deterministic_name
            history.add(timestamp, experiment_seed, seed, name, gene.get_hash(), History.GEN_METHOD.RANDOM, None, None)
            with open(os.path.join(outpath, f"{i}_{name}_{seed}.sgdl"), "w") as f:
                f.write(gdl)
        except Exception as e:
            if not args.ignore_errors:
                raise e
            print(f"!!![ERROR]: {e}")
    history.to_csv(os.path.join(outpath, f"history_{timestamp}.csv"))