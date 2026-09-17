from utility import Logger
from simulate_many import get_seeds
from parser import Parser
from game import Game
import pandas as pd
import os
from diffs import Diffs

def get_map_buckets_from_results(df: pd.DataFrame) -> dict[int, int]:
    bucket: dict[int, int] = {}
    for hash_value, results in df.groupby("SGDL Hash"):
        assert isinstance(hash_value, int)
        bucket[hash_value] = get_map_bucket_from_results(results)
    return bucket

def get_map_bucket_from_results(df: pd.DataFrame):
    return 0 # TODO

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