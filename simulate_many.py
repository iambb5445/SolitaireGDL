import argparse
from parser import Parser
from player import Player, RandomPlayer, RandomNoRepeatPlayer, MCTSPlayer, WinHeuristic, ActionCountHeuristic, SpiderHeuristic, NoDrawHeuristic, MergedHeuristic, DFSPlayer
from simulate import players
from game import Game
from tqdm import tqdm
from typing import Callable, Sequence
from utility import get_seed
import random
import sys
import time

thread_count = 1
max_time_per_sim: int|None = 60 # seconds

class Sample:
    def __init__(self, game: Game, action: str, game_id: int) -> None:
        self.game_id: int = game_id
        self.current: Game = game
        self.action: str = action
        self.next: Game|None = game.copy()
        self.valid: bool = True
        self.summary = Parser.get_action_summary(action, self.current, all_resolutions=False, explain=True)
        if not Parser.perform_action_in_game(action, self.next):
            self.valid = False
            self.next = None

    def as_json(self) -> dict[str, str|bool|None|int]:
        return {
            "game_id": self.game_id,
            "current_state_view": self.current.get_state_view(),
            "current_game_view": self.current.get_game_view(),
            "action": self.action,
            "summary": self.summary,
            "is_valid": self.valid,
            "next_state_view": self.next.get_state_view() if self.next is not None else None,
            "next_game_view": self.next.get_game_view() if self.next is not None else None,
        }
    
def sample(sample_rnd: random.Random, invalid_actions_rate: float, bot_action_rate: float, game: Game, bot_action: str, game_id: int) -> Sample:
    if sample_rnd.random() < invalid_actions_rate:
        if sample_rnd.random() < bot_action_rate:
            return Sample(game, bot_action, game_id)
        else:
            actions = game.get_possible_actions(True)
            random_action = str(actions[sample_rnd.randint(0, len(actions) - 1)])
            return Sample(game, random_action, game_id)
    else:
        actions = game.get_possible_actions(False)
        while True:
            random_action = str(actions[sample_rnd.randint(0, len(actions) - 1)])
            sample = Sample(game, random_action, game_id)
            if not sample.valid:
                return sample


def simulate_one(game_id: int, player: Player, game_desc: str, game_seed: int|None, max_moves: int|None, backtracking: bool,
                 sampling_seed: int|None, sample_rate: float = 0, invalid_actions_rate: float = 0, bot_action_rate: float = 0,
                 return_trace: bool = False) -> tuple[Game, int, list[Sample], list[str], Game, bool]:
    sample_rnd = random.Random(sampling_seed)
    game = Parser.parse(game_desc, game_seed, False, True)
    game_samples: list[Sample] = []
    move_count = 0
    backtrack_trace: list[Game] = []
    action_trace: list[str] = []
    start_time = time.time()
    starting_game = game.copy()
    while not game.is_win():
        action: str|None = player.decide_action(game.copy())
        if backtracking:
            while action is None and len(backtrack_trace) > 0:
                game = backtrack_trace.pop()
                if return_trace:
                    action_trace.pop()
                action: str|None = player.decide_action(game.copy())
        if action is None or move_count == max_moves or (max_time_per_sim is not None and (time.time() - start_time) > max_time_per_sim):
            return game, move_count, game_samples, (action_trace if return_trace else []), starting_game, True
        if sample_rnd.random() < sample_rate:
            game_samples.append(sample(sample_rnd, invalid_actions_rate, bot_action_rate, game.copy(), action, game_id))
        if return_trace:
            action_trace.append(action)
        if backtracking:
            backtrack_trace.append(game.copy())
        Parser.perform_action_in_game(action, game)
        move_count += 1
    return game, move_count, game_samples, (action_trace if return_trace else []), starting_game, False

def get_seeds(seeds: int|None|Sequence[int|None], count: int) -> Sequence[int|None]:
    if seeds is None:
        seeds = [None] * count
    elif isinstance(seeds, int):
        rnd = random.Random(seeds)
        seeds = [get_seed(rnd) for _ in range(count)]
    assert len(seeds) == count
    return seeds

def simulate_for_player(count: int, max_moves: int|None, backtracking: bool, game_desc: str, player_creator: Callable[[], Player],
                        game_seeds: int|None|Sequence[int|None], sampling_seeds: int|None|Sequence[int|None],
                        sampling_rate: float, invalid_actions_rate: float, bot_action_rate: float, return_trace: bool
                    ) -> tuple[list[Game], list[int], list[Sample], list[list[str]], list[Game], list[bool]]:
    game_seeds = get_seeds(game_seeds, count)
    sampling_seeds = get_seeds(sampling_seeds, count)
    if thread_count == 1:
        results = [simulate_one(
            game_id, player_creator(), game_desc, game_seed, max_moves, backtracking,
            sampling_seed, sampling_rate, invalid_actions_rate, bot_action_rate, return_trace
        ) for game_id, (game_seed, sampling_seed) in enumerate(tqdm(zip(game_seeds, sampling_seeds)))]
    else:
        from joblib import delayed, Parallel
        results = Parallel(n_jobs=thread_count)(delayed(simulate_one)(
            game_id, player_creator(), game_desc, game_seed, max_moves, backtracking,
            sampling_seed, sampling_rate, invalid_actions_rate, bot_action_rate, return_trace
        ) for game_id, (game_seed, sampling_seed) in enumerate(tqdm(zip(game_seeds, sampling_seeds))))
    # assert isinstance(results, list) and results is all(isinstance(item, (Game, int)) for item in results), "Parallel jobs have not resulted in an output of type list"
    games = [game for game, _, _, _, _, _ in results] # type: ignore
    move_counts = [move_count for _, move_count, _, _, _, _ in results] # type: ignore
    samples = [sample for _, _, game_samples, _, _, _ in results for sample in game_samples] # type: ignore
    full_trace = [moves for _, _, _, moves, _, _ in results] # type: ignore
    starting_games = [games for _, _, _, _, games, _ in results] # type: ignore
    stopped_search = [stopped for _, _, _, _, _, stopped in results] # type: ignore
    return games, move_counts, samples, full_trace, starting_games, stopped_search

def report_results(games: list[Game], move_counts: list[int]):
    # print("games:\n" + '\n'.join([f'{i}\n' + game.get_state_view() for i, game in enumerate(games)])) # type: ignore
    wins: list[bool] = [game.is_win() for game in games]
    print(f"win_percentage: {sum(wins)/len(wins)}")
    print(f"move_count: {move_counts}")
    print(f"average_move_counts: {sum(move_counts)/len(move_counts)}")

if __name__ == '__main__':
    start_time = time.time()
    parser = argparse.ArgumentParser(description="We have intentionally chosen default values that will ensure a fast response. For creating balanced datasets, these default values should be changed.")
    parser.add_argument('filename', type=str, help="Name of the SGDL file defining game rules. Refer to games/ for examples.")
    parser.add_argument('--bot', type=str, default="dfs-heuristic", help=f"Choose the bot to play the game. Options are: {list(players.keys())}, default: dfs-heuristic")
    parser.add_argument('--sampling-seed', type=int, default=None, help="Integer seed to be used for choosing the samples, random by default.")
    parser.add_argument('--game-seed', type=int, default=None, help="Integer seed to be used for shuffling the games, random by default.")
    parser.add_argument('--max-moves', type=int, default=100, help="Maximum number of moves in a game before stopping the sampling process (per game). Set to None using the code to continue until exhausting all the states the bot can reach.")
    parser.add_argument('--max-count', type=int, default=100, help="Maximum number of samples to save in the dataset. Set to None using the code save all the sampled states.")
    parser.add_argument('--game-count', type=int, default=5, help="Number of games to play.")
    parser.add_argument('--sampling-rate', type=float, default=0.1, help="Rate of sampling (between 0 and 1). While you can directly set the number of samples by using max-count, not sampling all games can save memory.")
    parser.add_argument('--invalid-action-rate', type=float, default=0.5, help="Rate of invalid actions to sample. Default is 0.5 to have a balanced dataset between valid/invalid responses.")
    parser.add_argument('--bot-action-rate', type=float, default=0.2, help="Rate of bot actoins to sample (between 0 and 1). We avoid bias, we don't want to always (or ever) sample bot actions when choosing a valid action.")
    parser.add_argument('--thread-count', type=int, default=20, help="Number of threads to run the simulation.")
    args = parser.parse_args(sys.argv[1:])
    game_filename: str = args.filename
    max_sample_count: int|None = args.max_count
    thread_count = args.thread_count
    with open(game_filename, 'r') as f:
        gdl = f.read()
    # game_filename = 'games/klondike.sgdl'
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
    games, move_counts, samples, _, _, _ = simulate_for_player(
        args.game_count, args.max_moves, True, gdl, lambda: players[args.bot](None),
        args.game_seed, args.sampling_seed, args.sampling_rate,
        args.invalid_action_rate, args.bot_action_rate, False
    )
    report_results(games, move_counts)
    print(f"timed at {time.time() - start_time}")
    if len(samples) == 0:
        exit()
    random.shuffle(samples)
    if max_sample_count is not None:
        samples = samples[:int(max_sample_count)]
    game = Parser.from_file(game_filename, None, False, False)
    wins: list[bool] = [game.is_win() for game in games]
    dataset = {
        "name": game.name,
        "bot": "DFSBot",
        "move_counts": move_counts,
        "average_move_count": sum(move_counts)/len(move_counts),
        "wins": wins,
        "win_percentage": sum(wins)/len(wins),
        "description": game.get_description(),
        "samples": [
            sample.as_json()
            for sample in samples
        ],
        "sample_count": len(samples)
    }
    import json, time
    filename = f"results/{dataset['name']}_{dataset['bot']}_{int(time.time())}.json"
    with open(filename, "w") as file:
        json.dump(dataset, file, indent=4)
    print(f"saved as {filename}")
    # simulate_for_player(1, 1000, game, lambda: MCTSPlayer(100, None, 100, lambda: RandomNoRepeatPlayer(None, ActionCountHeuristic()), WinHeuristic()))
