import sys
import os
from parser import Parser
from genetic import evaluate_gdl

filepath = sys.argv[1]
filenames = [name for name in os.listdir(filepath) if name.split('.')[-1] == 'sgdl']
gdls: list[str] = []
for filename in filenames:
    with open(os.path.join(filepath, filename), 'r') as f:
        gdls.append(f.read())
    print(filename)
print(f"Read {len(gdls)} files")
for gdl in gdls:
    verdict = evaluate_gdl(gdl, False)
    print(f"{gdl.splitlines()[0]} evaluate as {verdict}")