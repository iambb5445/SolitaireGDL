import os
import sys
import time
import argparse
# need to add this because parser is an existing python module :|
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from parser import Parser
from gene_parser import GeneParser
from random import Random
from genetic import SGDLGene
from utility import get_seed
from history import History

seed_max = 1000000000

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files.")
    parser.add_argument('outpath', type=str, help="Path to save the sgdl results of evaluation.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for creating the gdls.")
    parser.add_argument('--count-per-gdl', type=int, default=1, help="How many mutated versions should be created of each gdl.")
    parser.add_argument('--add-timestamp', action="store_true", help="If true, will make a directory in outpath based on timestamp.")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    parser.add_argument('--ensure-change', action="store_true", help="If true, ensures the mutated version is different than the original. This will result in a different GDL compared to having this option off with the same experiment seed.")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    experiment_seed: int = args.seed if args.seed is not None else get_seed(None, seed_max)
    experiment_rnd = Random(experiment_seed)
    outpath = args.outpath
    add_timestamp = args.add_timestamp
    print(f"Mutating games in {dir}")
    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    timestamp = int(time.time())
    if add_timestamp:
        outpath = os.path.join(outpath, f"{timestamp}")
    history = History()
    os.makedirs(outpath, exist_ok=True)
    for i, filename in enumerate(filenames):
        for j in range(args.count_per_gdl):
            try:
                ind = i * args.count_per_gdl + j
                gene = GeneParser.from_file(os.path.join(dir, filename))
                seed = get_seed(experiment_rnd, seed_max)
                if args.ensure_change:
                    mutated, seed = gene.mutate_until_change(Random(seed))
                else:
                    mutated = gene.mutate(Random(seed))
                gdl = mutated.get_gdl()
                name = Parser.get_name(gdl)
                history.add(timestamp, experiment_seed, seed, name, mutated.get_hash(), History.GEN_METHOD.MUTATION, gene.get_hash(), None)
                with open(os.path.join(outpath, f"{ind}_{name}_{seed}.sgdl"), "w") as f:
                    f.write(gdl)
            except Exception as e:
                if not args.ignore_errors:
                    raise e
                print(f"!!![ERROR]: {e}")
    history.to_csv(os.path.join(outpath, f"history_{timestamp}.csv"))