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
import json

seed_max = 1000000000

def get_parent_hash(filename: str, mapping: dict[str, str], prev_dir: str) -> int:
    parent_filename = mapping[filename]
    with open(os.path.join(prev_dir, parent_filename), 'r') as f:
        parent_gdl = f.read()
    return Parser.get_deterministic_hash(parent_gdl)

def get_gdl(dir: str, filename: str):
    with open(os.path.join(dir, filename), 'r') as f:
        gdl = f.read()
    hash = Parser.get_deterministic_hash(gdl)
    name = Parser.get_name(gdl)
    return hash, name, gdl

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help="Path to the directory containing SGDL files..")
    parser.add_argument('--ignore-non-existent', action="store_true", help="If true, logs errors but continues operation.")
    parser.add_argument('--oneshot', action="store_true", help="If true, it means the LLM generated this from nothing, instead of mutating a previous generation.")
    parser.add_argument('--prev-dir', type=str, default=None, help="Path to the directory containing previous generation, which mapping.txt is referring to. Required if this is not oneshot.")
    parser.add_argument('--included_history', type=int, default=0, help="Integer showing how many previous decisions the LLM had access to when generating this new file.")
    parser.add_argument('--skill', action="store_true", help="If true, it means the LLM used a skill file.")
    args = parser.parse_args(sys.argv[1:])
    dir = args.dir
    oneshot = args.oneshot
    prev_dir = args.prev_dir
    if not oneshot:
        assert prev_dir is not None, "Should pass a directory for previous generation if this is not oneshot."
    skill = args.skill
    included_history = args.included_history
    assert included_history >= 0
    assert oneshot == False or included_history == 0, "Cannot have a one-shot generation with history."
    ignore = args.ignore_non_existent

    filenames = [name for name in os.listdir(dir) if name.split('.')[-1] == 'sgdl']
    # alternatively, I can pass timestamp as an arg, but it doesn't matter that much and also lets this control the format
    timestamp = int(time.time())
    prev_history = History()
    mapping = {}
    if not oneshot:
        prev_history = History.from_csv(os.path.join(prev_dir, f"history.csv"))
        with open(os.path.join(prev_dir, "mapping.txt"), 'r') as f:
            mapping: dict[str, str] = json.load(f)

    history = History()
    for index, filename in enumerate(filenames):
        hash, name, gdl = get_gdl(dir, filename)
        try:
            parent_hash = get_parent_hash(filename, mapping, prev_dir) if not oneshot else None
            history.add(timestamp, None, None, name, hash, History.get_llm_mutation_method(included_history, skill),
                        None, None, prev_history.get_ancestor(parent_hash) if parent_hash is not None else None)
        except Exception as e:
            if not ignore:
                raise e
            print(f"!!![ERROR]: {e}")
        index += 1
    history.to_csv(os.path.join(dir, f"history.csv"), True)