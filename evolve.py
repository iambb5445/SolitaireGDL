from random import Random
import genetic
import sys
import os

rnd = Random(42)

out_dir = sys.argv[-1]
os.makedirs(out_dir, exist_ok=False)

def get_seed(rnd: Random):
    return rnd.randint(0, 10000000)

verdict = genetic.Verdict.OK
count = 100
count_width = len(str(count))
seeds = [get_seed(rnd) for _ in range(count)]
population = [genetic.SGDLGene.get_random(Random(seed)) for seed in seeds]
gdls = [gene.get_gdl() for gene in population]
print("Evaluating population")
verdicts: list[genetic.Verdict] = []
verdict_counts: dict[genetic.Verdict, int] = {}
for ind, (gdl, seed) in enumerate(zip(gdls, seeds)):
    verdict = genetic.evaluate_gdl(gdl, False)
    verdicts.append(verdict)
    verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
    name = gdl.splitlines()[0]
    print(f" $$$ {name} evaluated as {verdicts[-1]}, seed = {seed}")
    os.makedirs(os.path.join(out_dir, "gen0"), exist_ok=True)
    with open(os.path.join(out_dir, "gen0", f"{ind}_{name}_{verdict}.sgdl"), "w") as f:
        f.write(gdl)
for key, val in verdict_counts.items():
    # print(f"{val:0{count_width}d}/{count} ({val*100/count:05.1f}%) of verdicts are {key}")
    print(f"{val:0{count_width}d}/{count} ({val*100/count:.0f}%)\tof verdicts are {key}")
print("PRE-REDUCTION RESULTS")
cores: list[genetic.SGDLGene] = []
core_gdls: list[str] = []
for ind, (gene, gdl, verdict) in enumerate(zip(population, gdls, verdicts)):
    if verdict == genetic.Verdict.OK:
        cores.append(gene.get_reduced_to_core(Random(get_seed(rnd)), False, verdict))
        core_gdls.append(cores[-1].get_gdl())
        name = core_gdls[-1].splitlines()[0]
        old_name = gdl.splitlines()[0]
        os.makedirs(os.path.join(out_dir, "gen0_reduced"), exist_ok=True)
        with open(os.path.join(out_dir, "gen0_reduced", f"{ind}_{name}_prev_{old_name}_{verdict}.sgdl"), "w") as f:
            f.write(core_gdls[-1])
        print(f" &&& {old_name} reduced to {name}")
print("FINAL RESULTS")
for core_gdl in core_gdls:
    print(core_gdl)
    print("***")