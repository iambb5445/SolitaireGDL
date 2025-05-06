from __future__ import annotations
from abc import ABC, abstractmethod
from game import Game, GameAction
import random
from parser import Parser
from typing import Callable

class Player(ABC):
    # This function returns an str instead of a GameAction,
    # since the current_state is most likely a copy, and we want to prevent
    # the caller from using action.act, since it will be applied on the copied version
    @abstractmethod
    def decide_action(self, current_state: Game) -> str|None:
        raise NotImplementedError
    
class RandomPlayer(Player):
    def __init__(self, seed: int|None = None, heuristic: Callable[[Game], int]|None=None) -> None:
        self.random = random.Random(seed)
        self.heuristic = heuristic

    def _get_performed_state(self, current_state: Game, action: GameAction) -> Game:
        new_state = current_state.copy()
        new_state.logger.temp_deactivate()
        Parser.perform_action_in_game(str(action), new_state)
        return new_state

    def _weighted_choice(self, current_state: Game, actions: list[GameAction]) -> GameAction|None:
        if len(actions) == 0:
            return None
        if self.heuristic is None:
            return self.random.choice(actions)
        values = [(self.heuristic(self._get_performed_state(current_state, action)), action) for action in actions]
        return max(values)[1] # TODO weighted random

    def decide_action(self, current_state: Game) -> str|None:
        actions = current_state.get_possible_actions(True)
        action = self._weighted_choice(current_state, actions)
        return str(action) if action is not None else None

class RandomNoRepeatPlayer(RandomPlayer):
    HASH_TYPE = str # TODO generic
    def __init__(self, seed:int|None = None, heuristic: Callable[[Game], int]|None = None) -> None:
        super().__init__(seed, heuristic)
        self.seen_states: set[RandomNoRepeatPlayer.HASH_TYPE] = set()

    def _hash(self, state: Game) -> HASH_TYPE:
        return state.get_game_view()
    
    def _get_new_state_hash(self, current_state: Game, action: GameAction) -> HASH_TYPE:
        return self._hash(self._get_performed_state(current_state, action))
    
    def decide_action(self, current_state: Game) -> str|None:
        self.seen_states.add(self._hash(current_state))
        actions = current_state.get_possible_actions(True)
        actions = [action for action in actions if self._get_new_state_hash(current_state, action) not in self.seen_states]
        action = self._weighted_choice(current_state, actions)
        return str(action) if action is not None else None