from random import Random
from evaluate_gdl import get_evaluation_results
import genetic

seed = 336289545 # Nouq

gene = genetic.SGDLGene.get_random(Random(seed))
rnd = Random(42)
df = get_evaluation_results(gene.get_gdl(), should_log=False)
print(df)