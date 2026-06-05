from enum import StrEnum
from utility import Logger
from simulate_many import simulate_for_player, players, get_seeds, get_seed
from base import Card
from parser import Parser
from game import Game
import pandas as pd
from typing import Callable
from player import Player
import time

class Verdict(StrEnum):
    UNKNOWN = "UNKNOWN"
    IMPOSSIBLE = "IMPOSSIBLE"
    TRIVIAL = "TRIVIAL"
    BIPOLAR = "BIPOLAR"
    EXTRA_CARD = "EXTRA_CARD"
    EXTRA_PILE = "EXTRA_PILE"
    OK = "OK"

def get_verdicts_from_results(df: pd.DataFrame) -> dict[int, Verdict]:
    verdicts: dict[int, Verdict] = {}
    for hash_value, results in df.groupby("SGDL Hash"):
        assert isinstance(hash_value, int)
        verdicts[hash_value] = get_verdict_from_results(results)
    return verdicts

def get_verdict_from_results(df: pd.DataFrame):
    if df["Exhausted"].mean() > 0.9:
        return Verdict.UNKNOWN
    if df["Win"].mean() < 0.1:
        return Verdict.IMPOSSIBLE
    if df[df["Win"]]["Move Count"].mean() < 20: # not needed because of card usage unless the game is very few cards
        return Verdict.TRIVIAL
    if (df[df["Win"]]["Card Usage"] < 0.9).any():
        return Verdict.EXTRA_CARD
    if (df[df["Win"]]["Pile Usage"] < 0.8).any():
        return Verdict.EXTRA_PILE
    return Verdict.OK

def get_evaluation_results(gdl: str, max_move_count: int = 1000, game_count: int = 10, player_creator: Callable[[], Player] = lambda: players["dfs-heuristic"](None), should_log: bool = False, save_as: str|None = None, log_at: str|None = None, experiment_seed: int|None = None):
    logger = Logger(should_log, log_at)
    logger.info("gdl")
    logger.info(gdl)
    logger.info(str(player_creator()))
    logger.info(f"Experiment seed: {experiment_seed}")
    game_seeds = get_seeds(experiment_seed, game_count) # passing seeds in so I can also put them in the dataset
    game_ends, move_counts, samples, traces, game_starts, stopped = simulate_for_player(
        game_count, max_move_count, True, gdl, player_creator,
        game_seeds, 0, 0, 0, 1, True
    )
    game_name = game_ends[0].name
    wins: list[bool] = [game.is_win() for game in game_ends]
    win_percentage = sum(wins)/len(wins)
    exhausted_percentage = sum(stopped)/len(stopped)
    card_usage = [get_card_usage(start, end, logger) for start, end in zip(game_starts, game_ends)]
    pile_usage = [get_pile_usage(game, trace, logger) for game, trace in zip(game_starts, traces)]
    df = pd.DataFrame({
        "Game": [game_name] * game_count,
        "Simulation Seed": game_seeds,
        "Experiment Seed": [experiment_seed] * game_count,
        "SGDL Hash": [Parser.get_deterministic_hash(gdl)] * game_count,
        "Win": wins,
        # "Win Percentage": [win_percentage] * len(games),
        "Move Count": move_counts,
        "Exhausted": stopped,
        # "Exhausted Percentage": [exhausted] * len(games),
        "Card Usage": card_usage,
        "Pile Usage": pile_usage,
        "Timestamp": int(time.time())
    })
    if save_as is not None:
        df.to_csv(save_as)
    return df

def get_card_usage(game_start: Game, game_end: Game, logger: Logger) -> float:
    # I can use Parser.get_cards_of_action_in_game, but it's faster to compare the final position of cards
    # even though it's not accurate since a card can move and then return
    # or two cards with same value may swap
    logger.info("start")
    logger.info(game_start.get_state_view())
    logger.info("end")
    logger.info(game_end.get_state_view())
    cards = game_start.get_all_cards()
    card_set: set[str] = set()
    used_count = 0
    all_count = 0
    for card in cards:
        card_copy = card.copy()
        card_copy.face(True)
        card_str = card_copy.__str__()
        if card_str not in card_set:
            card_set.add(card_str)
            start_positions = game_start.get_card_positions(card)
            end_positions = game_end.get_card_positions(card)
            logger.info(f"adding {card_str}")
            logger.info(f"\tstart positions: {start_positions}")
            logger.info(f"\tend positions: {end_positions}")
            assert len(start_positions) == len(end_positions), f"{len(start_positions)} start positions but {len(end_positions)} end positions"
            used_count += len([position for position in end_positions if position not in start_positions])
            all_count += len(start_positions)
            logger.info(f"\tall count: {all_count}")
            logger.info(f"\tused count: {used_count}")
    assert all_count == len(cards), f"{all_count} is not same as {len(cards)}"
    return used_count/all_count

def get_pile_usage(game: Game, trace: list[str], logger: Logger) -> float:
    pile_positions_used: set[str] = set()
    for action in trace:
        pile_positions_used.update(Parser.get_piles_of_action_in_game(action))
    all_pile_positions: set[str] = set()
    for pilename in game.name_to_piles.keys():
        all_pile_positions.update([pile_pos.__str__() for pile_pos in game._get_pile_positions(pilename)])
    if game.draw_pile is not None:
        all_pile_positions.add("DRAW")
    logger.info("All pile positions:")
    logger.info(str(all_pile_positions))
    logger.info("Pile positions used:")
    logger.info(str(pile_positions_used))
    logger.info("Trace:")
    logger.info(str(trace))
    assert len(pile_positions_used & all_pile_positions) == len(pile_positions_used), f"{pile_positions_used.difference(all_pile_positions)} are not valid pile positions"
    return len(pile_positions_used)/len(all_pile_positions)

def evaluate_gdl(gdl: str, should_log: bool, max_move_count: int = 1000, game_count: int = 10) -> Verdict:
    logger = Logger(should_log)
    games, move_counts, samples, traces, starting_games, stopped = simulate_for_player(
        game_count, max_move_count, True, gdl, lambda: players["dfs-heuristic"](None),
        0, 0, 0, 0, 1, False
    )
    wins: list[bool] = [game.is_win() for game in games]
    win_percentage = sum(wins)/len(wins)
    win_move_counts = [move_count for win, move_count in zip(wins, move_counts) if win]
    exhausted = [move_count == max_move_count for move_count in move_counts]
    exhausted_percentage = sum(exhausted)/len(exhausted)
    logger.info("result for " + games[0].name)
    logger.info(f"wins: {wins}")
    logger.info(f"win percentage: {win_percentage}, exhausted: {exhausted_percentage}")
    logger.info(f"move counts: {move_counts}")
    logger.info(f"average move count: {sum(move_counts)/len(move_counts)}")
    logger.info(f"win move count: {win_move_counts}")
    logger.info(f"average win move count: {(sum(win_move_counts)/len(win_move_counts)) if len(win_move_counts) > 0 else 'NaN'}")
    # win_percentages.append(win_percentage)
    # exhausted_percentages.append(exhausted_percentage)
    if exhausted_percentage > 0.9:
        verdict = Verdict.UNKNOWN
    elif sum(wins) == 0:
        verdict = Verdict.IMPOSSIBLE
    elif sum(wins) == len(wins) and sum(win_move_counts)/len(win_move_counts) < 20:
        verdict = Verdict.TRIVIAL
    elif sum(win_move_counts)/len(win_move_counts) < 20:
        verdict = Verdict.BIPOLAR
    else:
        verdict = Verdict.OK
    logger.info(f"VERDICT: {str(verdict)}")
    return verdict