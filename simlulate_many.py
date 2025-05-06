from parser import Parser
from utility import Logger
from player import Player, RandomPlayer, RandomNoRepeatPlayer
from game import Game
from joblib import delayed, Parallel
from tqdm import tqdm
from typing import Callable

thread_count=1

def simulate_one(player: Player, game: Game, max_moves: int|None) -> tuple[Game, int]:
    move_count = 0
    while not game.is_win():
        action: str|None = player.decide_action(game.copy())
        if action is None or move_count == max_moves:
            return game, move_count
        Parser.perform_action_in_game(action, game)
        move_count += 1
    return game, move_count

def simulate_for_player(count: int, max_moves: int|None, game: Game, player_creator: Callable[[], Player]):
    results = Parallel(n_jobs=thread_count)(delayed(simulate_one)(player_creator(), game.copy(), max_moves) for _ in tqdm(range(count)))
    # assert isinstance(results, list) and results is all(isinstance(item, (Game, int)) for item in results), "Parallel jobs have not resulted in an output of type list"
    wins = [game.is_win() for game, move_count in results] # type: ignore
    move_counts = [move_count for game, move_count in results] # type: ignore
    print(f"win_percentage: {sum(wins)/len(wins)}")
    print(f"average_move_counts: {sum(move_counts)/len(move_counts)}")

if __name__ == '__main__':
    # with open('games/klondike.sgdl', 'r') as f:
    with open('games/spider.sgdl', 'r') as f:
        game = Parser.parse(f.read(), 42)
        game.logger.active = False
    simulate_for_player(10, 100, game, lambda: RandomPlayer(None))
    simulate_for_player(10, 100, game, lambda: RandomNoRepeatPlayer(None))