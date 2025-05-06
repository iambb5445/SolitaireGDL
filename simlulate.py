from parser import Parser
from utility import Logger
from player import RandomPlayer, RandomNoRepeatPlayer

if __name__ == '__main__':
    # with open('games/klondike.sgdl', 'r') as f:
    with open('games/spider.sgdl', 'r') as f:
        game = Parser.parse(f.read(), 42)
        game.logger.active = False
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
        input() # interupt