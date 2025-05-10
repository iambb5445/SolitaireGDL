from parser import Parser
from utility import Logger
from player import Player, RandomPlayer, RandomNoRepeatPlayer, MCTSPlayer, WinHeuristic, ActionCountHeuristic, SpiderHeuristic, NoDrawHeuristic, MergedHeuristic, DFSPlayer
from game import Game
from joblib import delayed, Parallel
from tqdm import tqdm
from typing import Callable
import time
import random

thread_count=10

def simulate_one(player: Player, game: Game, max_moves: int|None) -> tuple[Game, int]:
    with open('games/spider.sgdl', 'r') as f:
        game = Parser.parse(f.read(), random.randint(0, 1000000), False)
    move_count = 0
    while not game.is_win():
        game_copy = game.copy()
        action: str|None = player.decide_action(game_copy)
        if action is None or move_count == max_moves:
            return game, move_count
        Parser.perform_action_in_game(action, game)
        move_count += 1
    return game, move_count

def simulate_for_player(count: int, max_moves: int|None, game: Game, player_creator: Callable[[], Player]):
    start_time = time.time()
    results = Parallel(n_jobs=thread_count)(delayed(simulate_one)(player_creator(), game.copy(), max_moves) for _ in tqdm(range(count)))
    # assert isinstance(results, list) and results is all(isinstance(item, (Game, int)) for item in results), "Parallel jobs have not resulted in an output of type list"
    wins = [game.is_win() for game, move_count in results] # type: ignore
    move_counts = [move_count for game, move_count in results] # type: ignore
    print("games:\n" + '\n'.join([f'{i}\n' + game.get_state_view() for i, (game, _) in enumerate(results)])) # type: ignore
    print(f"win_percentage: {sum(wins)/len(wins)}")
    print(move_counts)
    print(f"average_move_counts: {sum(move_counts)/len(move_counts)}")
    print(f"timed at {time.time() - start_time}")

if __name__ == '__main__':
    # with open('games/klondike.sgdl', 'r') as f:
    # with open('games/spider.sgdl', 'r') as f:
    with open('games/easiestspider.sgdl', 'r') as f:
        game = Parser.parse(f.read(), None, False)
        game.logger.active = False
    # simulate_for_player(50, 1000, game, lambda: RandomPlayer(None))
    # simulate_for_player(50, 10000, game, lambda: RandomNoRepeatPlayer(None, spider_heuristic))
    # simulate_for_player(50, 10000, game, lambda: RandomNoRepeatPlayer(None, action_count_heuristic))
    # print("RandomPlayer")
    # simulate_for_player(10, 1000, game, lambda: RandomPlayer(None))
    # print("RandomPlayerNoRepeat, no heuristic")
    # simulate_for_player(10, 1000, game, lambda: RandomNoRepeatPlayer(None))
    # print("RandomPlayerNoRepeat, spider heuristic")
    # simulate_for_player(10, 1000, game, lambda: RandomNoRepeatPlayer(None, spider_heuristic))
    # print("RandomPlayerNoRepeat, action heuristic")
    # simulate_for_player(10, 10000, game, lambda: RandomNoRepeatPlayer(None, ActionCountHeuristic()))
    # simulate_for_player(10, 700, game, lambda: RandomNoRepeatPlayer(None, MergedHeuristic([ActionCountHeuristic(), NoDrawHeuristic(), WinHeuristic(), WinHeuristic(), WinHeuristic()])))
    simulate_for_player(10, 100, game, lambda: DFSPlayer(
        MergedHeuristic(
            [ActionCountHeuristic(), NoDrawHeuristic(), WinHeuristic(), WinHeuristic(), WinHeuristic()]
            )
        ))
    # simulate_for_player(1, 1000, game, lambda: MCTSPlayer(100, None, 100, lambda: RandomNoRepeatPlayer(None, ActionCountHeuristic()), WinHeuristic()))