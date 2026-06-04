import sys
import os
from evaluate_gdl import get_verdicts_from_results, Verdict
import argparse
import pandas as pd
from parser import Parser
import shutil

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', type=str, help="Evaluation csv file.")
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files.")
    parser.add_argument('outpath', type=str, help="Path to save the sgdl results of choosing bests.")
    parser.add_argument('--ignore-non-existent', action="store_true", help="If true, logs errors but continues operation. Useful for evaluating a batch of gdls that may be invalid.")
    parser.add_argument('--index-from-existing', action="store_true", help="If true, chooses index values for the file that continue from the existing number of files.")
    args = parser.parse_args(sys.argv[1:])
    filename = args.filename
    outpath = args.outpath
    ignore = args.ignore_none_existent
    dir = args.dir

    eval_results = pd.read_csv(filename)
    verdicts = get_verdicts_from_results(eval_results)
    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    index = 0
    if args.index_from_existing:
        index = len([name for name in os.listdir(outpath) if name.split('.')[-1] == 'sgdl'])
    for filename in filenames:
        with open(os.path.join(dir, filename), 'r') as f:
            gdl = f.read()
        hash = Parser.get_deterministic_hash(gdl)
        name = Parser.get_name(gdl)
        try:
            verdict = verdicts[hash]
            if verdict == Verdict.OK:
                shutil.copy(os.path.join(dir, filename), os.path.join(outpath, f"{index}_{name}.sgdl"))
        except Exception as e:
            if not ignore:
                raise e
            print(f"!!![ERROR]: {e}")
        index += 1