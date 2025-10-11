from parser import Parser
from utility import Logger
import utility as util
import sys
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', type=str, help="Name of the SGDL file defining game rules. Refer to games/ for examples.")
    parser.add_argument('seed', type=int, nargs="?", default=0, help="Integer seed to be used for shuffling the deck.")
    parser.add_argument('--partial-info', action="store_true", help="Show only the cards that are faced up. Face down cards will be shown as [?].")
    args = parser.parse_args(sys.argv[1:])
    sgdl_filename: str = args.filename
    seed = args.seed
    game = Parser.from_file(sgdl_filename, seed, True, True)
    logger = Logger(True)
    logger.info("GAME START!")
    while not game.is_win():
        logger.info(game.get_game_view() if args.partial_info else game.get_state_view())
        logger.info(f"{len(game.get_possible_actions(False))} total actions")
        valid_actions = game.get_possible_actions(True)
        logger.info(f"{len(valid_actions)} valid actions:")
        for i, valid_action in enumerate(valid_actions):
            logger.info(f"{i}: {valid_action}")
        action: str = input()
        action_int = util.cast(action, int)
        if action_int is not None:
            action = str(valid_actions[action_int])
        Parser.perform_action_in_game(action, game)