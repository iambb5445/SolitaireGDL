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
    parser.add_argument('count', type=int, help="Number of gdls to generate.")
    parser.add_argument('outpath', type=str, help="Path to save the sgdl results of evaluation.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for creating the gdls.")
    parser.add_argument('--ignore-errors', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    parser.add_argument('--index-from-existing', action="store_true", help="If true, chooses index values for the file that continue from the existing number of files.")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    experiment_seed: int = args.seed if args.seed is not None else get_seed(None, seed_max)
    experiment_rnd = Random(experiment_seed)
    outpath = args.outpath
    print(f"Crossovering games in {dir}")
    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    timestamp = int(time.time())
    history = History()
    base_index = 0
    os.makedirs(outpath, exist_ok=True)
    if args.index_from_existing:
        base_index = len([name for name in os.listdir(outpath) if name.split('.')[-1] == 'sgdl'])
    if len(filenames) < 2:
        if args.ignore_errors:
            raise Exception("Not enough files to crossover")
        exit()
    for i in range(args.count):
        try:
            ind = i + base_index
            parent_filenames = experiment_rnd.sample(filenames, k=2)
            gene1 = GeneParser.from_file(os.path.join(dir, parent_filenames[0]))
            gene2 = GeneParser.from_file(os.path.join(dir, parent_filenames[1]))
            seed = get_seed(experiment_rnd, seed_max)
            new_gene = gene1.crossover(gene2, Random(seed), False)
            gdl = new_gene.get_gdl()
            name = Parser.get_name(gdl)
            history.add(timestamp, experiment_seed, seed, name, new_gene.get_hash(), History.GEN_METHOD.CROSSOVER, gene1.get_hash(), gene2.get_hash())
            with open(os.path.join(outpath, f"{ind}_{name}_{seed}.sgdl"), "w") as f:
                f.write(gdl)
        except Exception as e:
            if not args.ignore_errors:
                raise e
            print(f"!!![ERROR]: {e}")
    history.to_csv(os.path.join(outpath, f"history.csv"), True)