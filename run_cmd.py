from parser import Parser
from utility import Logger
import utility as util

if __name__ == '__main__':
    # with open('games/klondike.sgdl', 'r') as f:
    with open('games/spider.sgdl', 'r') as f:
        game = Parser.parse(f.read(), 42)
    logger = Logger(True)
    logger.info("GAME START!")
    while not game.is_win():
        logger.info(game.get_game_view())
        logger.info(f"{len(game.get_possible_actions(False))} actions")
        valid_actions = game.get_possible_actions(True)
        logger.info(f"{len(valid_actions)} valid actions:")
        valid_actions_str = [f"{move_func.__name__} {' '.join([str(value) for value in args.values()])}" for move_func, args in valid_actions]
        for i, valid_action_str in enumerate(valid_actions_str):
            logger.info(f"{i}: {valid_action_str}")
        action: str = input()
        action_int = util.cast(action, int)
        if action_int is not None:
            action = valid_actions_str[action_int]
        Parser.perform_action_in_game(action, game)