from cProfile import Profile
from pstats import SortKey, Stats
from random import Random
import genetic

seed = 336289545 # Nouq

with Profile() as profile:
    verdict = genetic.Verdict.OK
    gene = genetic.SGDLGene.get_random(Random(seed))
    rnd = Random(42)
    # while verdict == genetic.Verdict.OK:
    for i in range(3):
        gdl = gene.get_gdl()
        print(gdl)
        print("***")
        verdict = genetic.evaluate_gdl(gdl, True, 100)
        print(verdict)
        print("------------------")
        gene = gene.get_reduced(rnd, 0)
        if gene is None:
            print("NONE")
            break
    (
        Stats(profile)
            .strip_dirs()
            .sort_stats(SortKey.CALLS)
            .print_stats()
            # .dump_stats("out4_time10.prof")
    )