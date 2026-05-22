from parser import Parser
from utility import Logger
import sys
from player import RandomPlayer, RandomNoRepeatPlayer, DFSPlayer, MergedHeuristic, ActionCountHeuristic, NoDrawHeuristic, WinHeuristic, MCTSPlayer
import argparse

global_heuristic = lambda: MergedHeuristic(
            [ActionCountHeuristic(), NoDrawHeuristic(), WinHeuristic()],
            [1, 1, 3]
            )

players = {
    "random": lambda seed: RandomPlayer(seed),
    "random-no-repeat": lambda seed: RandomNoRepeatPlayer(seed),
    "dfs": lambda seed: DFSPlayer(None),
    "dfs-heuristic" : lambda seed: DFSPlayer(global_heuristic()),
    "mcts-player": lambda seed: MCTSPlayer(0.2, None, 0, lambda: RandomNoRepeatPlayer(None, global_heuristic()), global_heuristic())
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', type=str, help="Name of the SGDL file defining game rules. Refer to games/ for examples.")
    parser.add_argument('seed', type=int, nargs="?", default=0, help="Integer seed to be used for shuffling the deck.")
    parser.add_argument('--bot', type=str, default="dfs-heuristic", help=f"Choose the bot to play the game. Options are: {players.keys()}")
    parser.add_argument('--bot-seed', type=int, default=0, help=f"Seed for bot actions. Some bots are deterministic, for example all dfs bots.")
    parser.add_argument('--partial-info', action="store_true", help="Show only the cards that are faced up. Face down cards will be shown as [?].")
    args = parser.parse_args(sys.argv[1:])
    game = Parser.from_file(args.filename, args.seed, False, True)
    player = players[args.bot](args.bot_seed)
    logger = Logger(True)
    logger.info("GAME START!")
    while not game.is_win():
        logger.info(game.get_game_view() if args.partial_info else game.get_state_view())
        action: str|None = player.decide_action(game.copy())
        if action is None:
            print("Bot cannot find any possible move")
            break
        print(Parser.get_action_summary(action, game, True, True))
        Parser.perform_action_in_game(action, game)
        input("Press enter to continue") # interupt