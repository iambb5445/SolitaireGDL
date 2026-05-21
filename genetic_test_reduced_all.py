from random import Random
import genetic

seed = 336289545 # Nouq

gene = genetic.SGDLGene.get_random(Random(seed))
rnd = Random(42)
print("base GDL")
print(gene.get_gdl())
print("***")
iter = 0
while True:
    new_gene = gene.get_reduced(None, iter)
    print(f"iter = {iter}")
    iter += 1
    if new_gene is None:
        print("NONE")
        break
    print(new_gene.get_gdl())
    print("***")