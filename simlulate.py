from parser import Parser
from utility import Logger
from player import RandomPlayer, RandomNoRepeatPlayer

if __name__ == '__main__':
    game = Parser.from_file('games/spider.sgdl', 42, False, True)
    player = RandomNoRepeatPlayer(42)
    logger = Logger(True)
    logger.info("GAME START!")
    while not game.is_win():
        logger.info(game.get_game_view())
        action: str|None = player.decide_action(game.copy())
        if action is None:
            print("Bot cannot find any possible move")
            break
        Parser.perform_action_in_game(action, game)
        input("Press anything to continue") # interupt