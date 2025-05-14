from parser import Parser
from player import Player, RandomPlayer, RandomNoRepeatPlayer, MCTSPlayer, WinHeuristic, ActionCountHeuristic, SpiderHeuristic, NoDrawHeuristic, MergedHeuristic, DFSPlayer
from game import Game
from joblib import delayed, Parallel
from tqdm import tqdm
from typing import Callable, Sequence
import time
import random

thread_count=10

class Sample:
    def __init__(self, game: Game, action: str) -> None:
        self.current: Game = game
        self.action: str = action
        self.next: Game|None = game.copy()
        self.valid: bool = True
        self.summary = Parser.get_action_summary(action, self.current)
        if not Parser.perform_action_in_game(action, self.next):
            self.valid = False
            self.next = None

    def as_json(self) -> dict[str, str|bool|None]:
        return {
            "current_state_view": self.current.get_state_view(),
            "current_game_view": self.current.get_game_view(),
            "action": self.action,
            "summary": self.summary,
            "is_valid": self.valid,
            "next_state_view": self.next.get_state_view() if self.next is not None else None,
            "next_game_view": self.next.get_game_view() if self.next is not None else None,
        }

def simulate_one(player: Player, game_filename: str, game_seed: int|None, max_moves: int|None,
                 sampling_seed: int|None, sample_rate: float = 0, invalid_actions_rate: float = 0, bot_action_rate: float = 0) -> tuple[Game, int, list[Sample]]:
    sample_rnd = random.Random(sampling_seed)
    game = Parser.from_file(game_filename, game_seed, False, True)
    game_samples: list[Sample] = []
    move_count = 0
    while not game.is_win():
        game_copy = game.copy()
        action: str|None = player.decide_action(game_copy)
        if action is None or move_count == max_moves:
            return game, move_count, game_samples
        if sample_rnd.random() < sample_rate:
            if sample_rnd.random() < invalid_actions_rate:
                if sample_rnd.random() < bot_action_rate:
                    game_samples.append(Sample(game.copy(), action))
                else:
                    actions = game.get_possible_actions(True)
                    random_action = str(actions[sample_rnd.randint(0, len(actions) - 1)])
                    game_samples.append(Sample(game.copy(), random_action))
            else:
                actions = game.get_possible_actions(False)
                while True:
                    random_action = str(actions[sample_rnd.randint(0, len(actions) - 1)])
                    sample = Sample(game.copy(), random_action)
                    if not sample.valid:
                        game_samples.append(sample)
                        break
        Parser.perform_action_in_game(action, game)
        move_count += 1
    return game, move_count, game_samples

def get_seeds(seeds: int|None|Sequence[int|None], count: int) -> Sequence[int|None]:
    if seeds is None:
        seeds = [None] * count
    elif isinstance(seeds, int):
        rnd = random.Random(seeds)
        seeds = [rnd.randint(0, 10000000) for _ in range(count)]
    assert len(seeds) == count
    return seeds

def simulate_for_player(count: int, max_moves: int|None, game_filename: str, player_creator: Callable[[], Player],
                        game_seeds: int|None|Sequence[int|None], sampling_seeds: int|None|Sequence[int|None],
                        sampling_rate: float, invalid_actions_rate: float, bot_action_rate: float) -> tuple[list[Game], list[int], list[Sample]]:
    game_seeds = get_seeds(game_seeds, count)
    sampling_seeds = get_seeds(sampling_seeds, count)
    results = Parallel(n_jobs=thread_count)(delayed(simulate_one)(
        player_creator(), game_filename, game_seed, max_moves, sampling_seed, sampling_rate, invalid_actions_rate, bot_action_rate) for game_seed, sampling_seed in tqdm(zip(game_seeds, sampling_seeds)))
    # assert isinstance(results, list) and results is all(isinstance(item, (Game, int)) for item in results), "Parallel jobs have not resulted in an output of type list"
    games = [game for game, _, _ in results] # type: ignore
    move_counts = [move_count for _, move_count, _ in results] # type: ignore
    samples = [sample for _, _, game_samples in results for sample in game_samples] # type: ignore
    return games, move_counts, samples

def report_results(games: list[Game], move_counts: list[int]):
    print("games:\n" + '\n'.join([f'{i}\n' + game.get_state_view() for i, game in enumerate(games)])) # type: ignore
    wins: list[bool] = [game.is_win() for game in games]
    print(f"win_percentage: {sum(wins)/len(wins)}")
    print(f"move_count: {move_counts}")
    print(f"average_move_counts: {sum(move_counts)/len(move_counts)}")

if __name__ == '__main__':
    start_time = time.time()
    game_filename = 'games/easiestspider.sgdl'
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
    games, move_counts, samples = simulate_for_player(10, 100, game_filename, lambda: DFSPlayer(
        MergedHeuristic(
            [ActionCountHeuristic(), NoDrawHeuristic(), WinHeuristic(), WinHeuristic(), WinHeuristic()]
            )
        ), None, None, 0.15, 0.5, 0.2)
    report_results(games, move_counts)
    print(f"timed at {time.time() - start_time}")
    if len(samples) == 0:
        exit()
    game = Parser.from_file(game_filename, None, False, False)
    dataset = {
        "name": game.name,
        "bot": "DFSBot",
        "samples": [
            sample.as_json()
            for sample in samples
        ]
    }
    import json, time
    filename = f"results/{dataset['name']}_{dataset['bot']}_{int(time.time())}.json"
    with open(filename, "w") as file:
        json.dump(dataset, file, indent=4)
    print(f"saved as {filename}")
    # simulate_for_player(1, 1000, game, lambda: MCTSPlayer(100, None, 100, lambda: RandomNoRepeatPlayer(None, ActionCountHeuristic()), WinHeuristic()))
