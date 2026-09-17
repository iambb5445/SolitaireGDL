from utility import Logger
from simulate_many import get_seeds
from parser import Parser
from game import Game
import pandas as pd
import os
from diffs import Diffs
from typing import Callable

def apply_pile_count_bucket(df: pd.DataFrame, boundaries: list[float], prev_bucket) -> int:
    assert df["Pile Count"].nunique() == 1
    return find_multi_bucket(df["Pile Count"].iloc[0], boundaries, prev_bucket)

def apply_omc_bucket(df: pd.DataFrame, boundaries: list[float], prev_bucket) -> int:
    return find_multi_bucket(df["Opening Move Count"].mean(), boundaries, prev_bucket)

def apply_min_familiarity_bucket(df: pd.DataFrame, boundaries: list[float], prev_bucket) -> int:
    dist_cols = [c for c in df.columns if c.startswith("Distance to")]
    assert (df[dist_cols].nunique() == 1).all()
    min_dist = df[dist_cols].iloc[0].min()
    return find_multi_bucket(min_dist, boundaries, prev_bucket)

bucket_mapping: list[tuple[Callable[[pd.DataFrame, list[float], int], int], list[float]]] = [
    (apply_min_familiarity_bucket, [0.2, 0.4]),
    (apply_omc_bucket, [10]),
    (apply_pile_count_bucket, [10]),
]

def get_map_buckets_from_results(df: pd.DataFrame, should_log: bool) -> dict[int, int]:
    logger = Logger(should_log)
    logger.info("Bucket calculation decided as:")
    total_bucket_count = 1
    for func, boundaries in bucket_mapping:
        logger.info(f"\t{func.__name__} at boundaries {boundaries}")
        total_bucket_count *= len(boundaries) + 1
    logger.info(f"Total bucket count is {total_bucket_count}")
    bucket: dict[int, int] = {}
    for hash_value, results in df.groupby("SGDL Hash"):
        assert isinstance(hash_value, int)
        bucket[hash_value] = get_map_bucket_from_results(results)
    return bucket

def get_map_bucket_from_results(df: pd.DataFrame) -> int:
    bucket = 0
    for func, boundaries in bucket_mapping:
        func(df, boundaries, bucket)
    return bucket

def find_multi_bucket(value, boundaries: list[float], bucket_so_far: int):
    return bucket_so_far * (len(boundaries) + 1) + _find_bucket(boundaries, value)

def _find_bucket(boundaries, value) -> int:
    for i, boundary in enumerate(boundaries):
        if value < boundary:
            return i
    return len(boundaries)

_bd_reference_games_cache: dict[str, Game] | None = None

BD_REFERENCE_GAME_PATHS = { # reference games for behavior metrics (map-elites axis)
    "Klondike": "games/klondike_family/klondike.sgdl",
    "Spider": "games/spider_family/spider.sgdl",
    "FreeCell": "games/freecell_family/freecell.sgdl",
    "Pairing": "games/pairing_family/golf.sgdl",
}

def _get_bd_reference_games() -> dict[str, Game]:
    global _bd_reference_games_cache
    if _bd_reference_games_cache is None:
        repo_root = os.path.abspath(os.path.dirname(__file__))
        _bd_reference_games_cache = {
            name: Parser.from_file(os.path.join(repo_root, rel_path), 0, False, True)
            for name, rel_path in BD_REFERENCE_GAME_PATHS.items()
        }
    return _bd_reference_games_cache

def get_bd_metrics(gdl: str, game_count: int = 10, should_log: bool = False,
                   save_as: str|None = None, log_at: str|None = None, experiment_seed: int|None = None):
    logger = Logger(should_log, log_at)
    logger.info("gdl")
    logger.info(gdl)
    logger.info(f"Experiment seed: {experiment_seed}")
    game_name = Parser.get_name(gdl)
    game_hash = Parser.get_deterministic_hash(gdl)
    if experiment_seed is None:
        experiment_seed = game_hash
    game_seeds: list[int] = [seed for seed in get_seeds(experiment_seed, game_count) if seed is not None]
    assert len(game_seeds) == game_count
    games = [Parser.parse(gdl, game_seed, False, True) for game_seed in game_seeds]
    metrics: dict[str, list[float]|list[str]|list[int]] = {
        "Game": [game_name] * game_count,
        "Simulation Seed": game_seeds,
        "Experiment Seed": [experiment_seed] * game_count,
        "SGDL Hash": [game_hash] * game_count,
        "Card Count": [len(game.get_all_cards()) for game in games],
        "Pile Count": [sum(len(piles) for piles in game.name_to_piles.values()) for game in games],
        "Pile Type Count": [len(game.name_to_piles) for game in games],
        "Has Rotate Draw": [float(game.has_rotate_draw_pile()) for game in games],
        "Has Deal Draw": [float(game.has_deal_draw_pile()) for game in games],
        "Move Card Rule Count": [len(game.move_conditions) for game in games],
        "Move Stack Rule Count": [len(game.move_stack_conditions) for game in games],
        "Opening Move Count": [len(game.get_possible_actions(True)) for game in games],
    }

    for ref_name, ref_game in _get_bd_reference_games().items():
        diff = games[0].diff(ref_game, True, Diffs.get_sum_normalized_diff_normalized)
        metrics[f"Distance to {ref_name}"] = [diff.get_sum_normalized_diff_normalized() for _ in games]

    df = pd.DataFrame(metrics)
    if save_as is not None:
        df.to_csv(save_as)
    return df