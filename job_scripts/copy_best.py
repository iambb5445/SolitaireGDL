import sys
import os
import argparse
from random import Random
import shutil
import time
# need to add this because parser is an existing python module :|
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from parser import Parser
from utility import get_seed
from history import History

seed_max = 1000000000

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing **best** SGDL files. This doesn't perform evaluation.")
    parser.add_argument('max_count', type=int, help="Maximum number of files to copy. Chosen randomly if there are more files than maximum.")
    parser.add_argument('outpath', type=str, help="Path to save the sgdl results of copying bests.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for choosing the files.")
    parser.add_argument('--index-from-existing', action="store_true", help="If true, chooses index values for the file that continue from the existing number of files.")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    outpath = args.outpath
    ignore = args.ignore_non_existent
    max_count = args.max_count
    seed: int = args.seed if args.seed is not None else get_seed(None, seed_max)
    assert max_count >= 0

    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    if len(filenames) > max_count:
        filenames = Random(seed).sample(filenames, max_count)
    timestamp = int(time.time())
    history = History()
    os.makedirs(outpath, exist_ok=True)
    index = 0
    if args.index_from_existing:
        index = len([name for name in os.listdir(outpath) if name.split('.')[-1] == 'sgdl'])
    for filename in filenames:
        with open(os.path.join(dir, filename), 'r') as f:
            gdl = f.read()
        hash = Parser.get_deterministic_hash(gdl)
        name = Parser.get_name(gdl)
        try:
            shutil.copy(os.path.join(dir, filename), os.path.join(outpath, f"{index}_{name}.sgdl"))
            history.add(timestamp, seed, None, name, hash, History.GEN_METHOD.BEST_OF, None, None)
        except Exception as e:
            if not ignore:
                raise e
            print(f"!!![ERROR]: {e}")
        index += 1
    history.to_csv(os.path.join(outpath, f"history.csv"), True)