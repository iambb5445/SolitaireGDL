import os
import pandas as pd
from base import BaseStrEnum

class History:
    class KEYS(BaseStrEnum):
        TIMESTAMP = "Timestamp"
        EXPR_SEED = "Experiment Seed"
        SGDL_SEED = "SGDL Seed"
        GAME_NAME = "Name"
        GAME_HASH = "SGDL Hash"
        GEN_METHOD = "Generation Method"
        PARENT1 = "Parent 1"
        PARENT2 = "Parent 2"

    class GEN_METHOD(BaseStrEnum):
        RANDOM = "Random"
        MUTATION = "Mutation"
        CROSSOVER = "Crossover"
        LLM_MUTATION = "LLM Mutation"
        LLM_ONESHOT = "LLM One-Shot"
        BEST_OF = "Best of Previous Generation"

    def __init__(self) -> None:
        self.df = pd.DataFrame(columns=list(History.KEYS))

    def add(self, timestamp: int, expr_seed: int|None, sgdl_seed: int|None, game_name: str, game_hash: int,
            gen_method: GEN_METHOD, parent1_hash: int|None, parent2_hash: int|None):
        self.df.loc[len(self.df)] = {
            History.KEYS.TIMESTAMP: timestamp,
            History.KEYS.EXPR_SEED: expr_seed,
            History.KEYS.SGDL_SEED: sgdl_seed,
            History.KEYS.GAME_NAME: game_name,
            History.KEYS.GAME_HASH: game_hash,
            History.KEYS.GEN_METHOD: gen_method,
            History.KEYS.PARENT1: parent1_hash,
            History.KEYS.PARENT2: parent2_hash,
        }

    def to_csv(self, filepath: str, concat: bool):
        if os.path.isfile(filepath):
            if concat:
                existing = pd.read_csv(filepath, index_col=False)
                pd.concat([existing, self.df], ignore_index=True).to_csv(filepath)
            else:
                raise Exception("Filename already exists")
        else:
            self.df.to_csv(filepath)
    