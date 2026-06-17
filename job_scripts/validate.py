import sys
import os
import argparse
import pandas as pd
# need to add this because parser is an existing python module :|
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from parser import Parser

seed_max = 1000000000
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing all SGDL files.")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir

    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']

    for filename in filenames:
        with open(os.path.join(dir, filename), 'r') as f:
            gdl = f.read()
        try:
            name = Parser.parse(gdl, None, False, True)
        except Exception as e:
            print(f"!!![ERROR]: {e}")
            with open(os.path.join(dir, filename), 'a') as f:
                f.write("\n# ERROR when compiling this gdl:\n" + "\n".join([f"# {line}" for line in str(e).splitlines()]))