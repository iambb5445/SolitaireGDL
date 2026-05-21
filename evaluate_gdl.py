from enum import StrEnum
from utility import Logger
from simulate_many import simulate_for_player, players
from base import Card
from parser import Parser

class Verdict(StrEnum):
    UNKNOWN = "UNKNOWN"
    IMPOSSIBLE = "IMPOSSIBLE"
    TRIVIAL = "TRIVIAL"
    BIPOLAR = "BIPOLAR"
    EXTRA = "EXTRA"
    OK = "OK"

def evaluate_gdl(gdl: str, should_log: bool, max_move_count: int = 1000, game_count: int = 10, check_trace: bool = False) -> Verdict:
    logger = Logger(should_log)
    games, move_counts, samples, traces, starting_games = simulate_for_player(
        game_count, max_move_count, True, gdl, lambda: players["dfs-heuristic"](None),
        0, 0, 0, 0, 1, check_trace
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
        precentage_cards_used: list[float] = []
        if check_trace:
            cards_moved: set[Card] = set()
            for starting_game, trace in zip(starting_games, traces):
                game = starting_game.copy()
                for action in trace:
                    cards = Parser.get_cards_of_action_in_game(action, game)
                    cards_moved.add(*cards)
                    Parser.perform_action_in_game(action, game)
                precentage_cards_used.append(len(cards_moved) / len(starting_game.get_all_cards()))
            logger.info(f"percentage of cards used: {(sum(win_move_counts)/len(win_move_counts)) if len(win_move_counts) > 0 else 'NaN'}")
    logger.info(f"VERDICT: {str(verdict)}")
    return verdict