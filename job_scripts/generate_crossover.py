import os
import sys
import time
import argparse
# need to add this because parser is an existing python module :|
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from parser import Parser
from gene_parser import GeneParser
from random import Random
from utility import get_seed
from history import History

seed_max = 1000000000
max_retries = 50

def generate_crossover(ind: int, parent_filenames):
    gene1 = GeneParser.from_file(os.path.join(dir, parent_filenames[0]))
    gene2 = GeneParser.from_file(os.path.join(dir, parent_filenames[1]))
    for attempt in range(max_retries):
        seed = get_seed(experiment_rnd, seed_max)
        try:
            new_gene = gene1.crossover(gene2, Random(seed), False)
            gdl = new_gene.get_gdl()
            # validation
            Parser.parse(gdl, None, False, True)
            name = Parser.get_name(gdl)
            hash = new_gene.get_hash()
            main_parent_hash = gene1.get_hash()
            secondary_parent_hash = gene2.get_hash()
            history.add(
                timestamp, experiment_seed, seed, name, hash, History.GEN_METHOD.CROSSOVER,
                main_parent_hash, secondary_parent_hash, prev_history.get_ancestor(main_parent_hash))
            with open(os.path.join(outpath, f"{ind}_{name}_{hash}.sgdl"), "w") as f:
                f.write(gdl)
            return True
        except Exception as e:
            if not args.ignore_errors:
                raise e
            print(f"!!![ERROR] (attempt {attempt+1}/{max_retries}, seed: {seed},  parents: {parent_filenames}): {e}")
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files.")
    parser.add_argument('count', type=int, help="Number of gdls to generate.")
    parser.add_argument('outpath', type=str, help="Path to save the sgdl results of crossover.")
    parser.add_argument('--max-per-game', type=int, default=None, help="Maximum number of times a game is allowed to be used as a parent.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for creating the gdls.")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    parser.add_argument('--index-from-existing', action="store_true", help="If true, chooses index values for the file that continue from the existing number of files.")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    max_per_game = args.max_per_game
    experiment_seed: int = args.seed if args.seed is not None else get_seed(None, seed_max)
    experiment_rnd = Random(experiment_seed)
    outpath = args.outpath
    print(f"Crossovering games in {dir}")
    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    timestamp = int(time.time())
    prev_history = History.from_csv(os.path.join(dir, f"history.csv"))
    history = History()
    base_index = 0
    os.makedirs(outpath, exist_ok=True)
    if args.index_from_existing:
        base_index = len([name for name in os.listdir(outpath) if name.split('.')[-1] == 'sgdl'])
    if len(filenames) < 2:
        print("Not enough files to crossover")
        if not args.ignore_errors:
            raise Exception("Not enough files to crossover")
        exit()
    game_usage: dict[str, int] = dict([(file, 0) for file in filenames])
    for i in range(args.count):
        ind = i + base_index
        if len(filenames) < 2:
            break
        parent_filenames = experiment_rnd.sample(filenames, k=2)
        if generate_crossover(ind, parent_filenames):
            for parent_filename in parent_filenames:
                game_usage[parent_filename] += 1
                if max_per_game is not None and game_usage[parent_filename] >= max_per_game:
                    filenames.remove(parent_filename)
    history.to_csv(os.path.join(outpath, f"history.csv"), True)