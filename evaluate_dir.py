import sys
import os
from parser import Parser
from evaluate_gdl import evaluate_gdl, Verdict

filepath = sys.argv[1]
step = int(sys.argv[2])

print(f"Evaluating games in {filepath} with step {step}")

filenames = [name for name in os.listdir(filepath) if name.split('.')[-1] == 'sgdl']
filenames = [name for id, name in enumerate(filenames) if id % step == 0]
gdls: list[str] = []
for filename in filenames:
    with open(os.path.join(filepath, filename), 'r') as f:
        gdls.append(f.read())
verdict_counts: dict[Verdict, int] = {}
print(f"Read {len(gdls)} files")
for gdl in gdls:
    name = Parser.get_name(gdl)
    try:
        verdict = evaluate_gdl(gdl, False)
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        print(f"{name} evaluate as {verdict}")
    except Exception as e:
        print(f"Error parsing/evaluating {name}")
        print(e)
count = len(gdls)
count_width = len(str(count))
for key, val in verdict_counts.items():
    print(f"{val:0{count_width}d}/{count} ({val*100/count:.0f}%)\tof verdicts are {key}")