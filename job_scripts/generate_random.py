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
    parser.add_argument('outpath', type=str, help="Path to save the sgdl results of generation.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for creating the gdls.")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    parser.add_argument('--index-from-existing', action="store_true", help="If true, chooses index values for the file that continue from the existing number of files.")
    parser.add_argument('--until', action="store_true", help="If true, generates until there are {{count}} sgdls available.")
    args = parser.parse_args(sys.argv[1:])
    count = args.count
    experiment_seed: int = args.seed if args.seed is not None else get_seed(None, seed_max)
    experiment_rnd = Random(experiment_seed)
    outpath = args.outpath
    if args.until:
        existing = len([name for name in os.listdir(outpath) if name.split('.')[-1] == 'sgdl'])
        print(f"{existing} files already exists, generating {count - existing} instead of {count}.")
        count -= existing
    seeds = [get_seed(experiment_rnd, seed_max) for _ in range(count)]
    timestamp = int(time.time())
    history = History()
    os.makedirs(outpath, exist_ok=True)
    base_index = 0
    if args.index_from_existing:
        base_index = len([name for name in os.listdir(outpath) if name.split('.')[-1] == 'sgdl'])
    for i, seed in enumerate(seeds):
        try:
            gene = SGDLGene.get_random(Random(seed))
            gdl = gene.get_gdl()
            name = Parser.get_name(gdl)
            hash = gene.get_hash()
            history.add(timestamp, experiment_seed, seed, name, hash, History.GEN_METHOD.RANDOM, None, None, hash)
            with open(os.path.join(outpath, f"{i + base_index}_{name}_{hash}.sgdl"), "w") as f:
                f.write(gdl)
        except Exception as e:
            if not args.ignore_errors:
                raise e
            print(f"!!![ERROR]: {e}")
    history.to_csv(os.path.join(outpath, f"history.csv"), True)