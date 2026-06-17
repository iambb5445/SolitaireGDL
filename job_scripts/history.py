from __future__ import annotations
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
        ANCESTOR = "Ancestor"

    class GEN_METHOD(BaseStrEnum):
        RANDOM = "Random"
        MUTATION = "Mutation"
        CROSSOVER = "Crossover"
        LLM_MUTATION = "LLM Mutation"
        LLM_ONESHOT = "LLM One-Shot"
        BEST_OF = "Best of Previous Generation"

    @staticmethod
    def get_llm_mutation_method(included_history: int, skill: bool):
        return History.GEN_METHOD.LLM_MUTATION + \
            (f"_{included_history}" if included_history > 0 else "") + \
            ("_skilled" if skill else "")

    def __init__(self) -> None:
        self.df = pd.DataFrame(columns=list(History.KEYS))

    def add(self, timestamp: int, expr_seed: int|None, sgdl_seed: int|None, game_name: str, game_hash: int,
            gen_method: GEN_METHOD|str, parent1_hash: int|None, parent2_hash: int|None, ancestor_hash: int|None):
        self.df.loc[len(self.df)] = {
            History.KEYS.TIMESTAMP: timestamp,
            History.KEYS.EXPR_SEED: expr_seed,
            History.KEYS.SGDL_SEED: sgdl_seed,
            History.KEYS.GAME_NAME: game_name,
            History.KEYS.GAME_HASH: game_hash,
            History.KEYS.GEN_METHOD: gen_method,
            History.KEYS.PARENT1: parent1_hash,
            History.KEYS.PARENT2: parent2_hash,
            History.KEYS.ANCESTOR: ancestor_hash
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
    
    @staticmethod
    def from_csv(filepath: str) -> History:
        history = History()
        if os.path.isfile(filepath):
            df = pd.read_csv(filepath, index_col=False)
            for key in History.KEYS:
                if key not in df:
                    print(f"Cannot read history at {filepath}: key {key} does not exist")
                    return history
            for col in df:
                if col not in History.KEYS:
                    print(f"Cannot read history at {filepath}: key {col} should not exist")
                    return history
            history.df = df
        return history
    
    def get(self, hash: int, col: str) -> str|int|None:
        return self.df.loc[self.df[History.KEYS.GAME_HASH] == hash, col].iloc[0]
    
    def get_ancestor(self, hash: int) -> int|None:
        ancestor = self.get(hash, History.KEYS.ANCESTOR)
        if isinstance(ancestor, float) or isinstance(ancestor, int):
            return int(ancestor)
        return None