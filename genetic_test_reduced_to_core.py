from random import Random
from evaluate_gdl import Verdict
import genetic

seed = 336289545 # Nouq

verdict = Verdict.OK
gene = genetic.SGDLGene.get_random(Random(seed))
rnd = Random(42)
print(gene.get_reduced_to_core(rnd, True, verdict).get_gdl())