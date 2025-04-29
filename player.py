from abc import ABC, abstractmethod
from game import Game, GameAction
import random
from parser import Parser

class Player(ABC):
    # This function returns an str instead of a GameAction,
    # since the current_state is most likely a copy, and we want to prevent
    # the caller from using action.act, since it will be applied on the copied version
    @abstractmethod
    def decide_action(self, current_state: Game) -> str|None:
        raise NotImplementedError
    
class RandomPlayer(Player):
    def __init__(self, seed: int|None = None) -> None:
        self.random = random.Random(seed)

    def decide_action(self, current_state: Game) -> str|None:
        actions = current_state.get_possible_actions(True)
        if len(actions) == 0:
            return None
        action = self.random.choice(actions)
        return str(action)

class RandomNoRepeatPlayer(RandomPlayer):
    def __init__(self, seed:int|None = None) -> None:
        super().__init__(seed)
        self.seen_states = set()

    def _hash(self, s: str) -> int:
        return len(s)
    
    def decide_action(self, current_state: Game) -> str|None:
        actions = current_state.get_possible_actions(True)
        def filter(action: GameAction):
            state_copy = current_state.copy()
            Parser.perform_action_in_game(str(action), state_copy)
            return self._hash(state_copy.get_game_view()) not in self.seen_states
        actions = [action for action in actions if filter(action)]
        if len(actions) == 0:
            return None
        return str(self.random.choice(actions))