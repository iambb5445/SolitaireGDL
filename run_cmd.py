from parser import Parser
from utility import Logger
import utility as util
import sys

if __name__ == '__main__':
    sgdl_filename = sys.argv[1]
    with open(sgdl_filename, 'r') as f:
        game = Parser.parse(f.read(), 42)
    logger = Logger(True)
    logger.info("GAME START!")
    while not game.is_win():
        logger.info(game.get_game_view())
        logger.info(f"{len(game.get_possible_actions(False))} actions")
        valid_actions = game.get_possible_actions(True)
        logger.info(f"{len(valid_actions)} valid actions:")
        for i, valid_action in enumerate(valid_actions):
            logger.info(f"{i}: {valid_action}")
        action: str = input()
        action_int = util.cast(action, int)
        if action_int is not None:
            action = str(valid_actions[action_int])
        Parser.perform_action_in_game(action, game)