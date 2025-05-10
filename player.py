from __future__ import annotations
from abc import ABC, abstractmethod
from game import Game
from utility import get_max_elements
import random
from parser import Parser
from typing import Callable
import math
import time

class StateEval(ABC):
    def __init__(self, max_value: int) -> None:
        self.max_value = max_value
    
    @abstractmethod
    def get_value(self, state: Game, action: str|None) -> int:
        raise NotImplementedError
    
    def get_normalized_value(self, state: Game, action: str|None) -> float:
        return self.get_value(state, action) / self.max_value
    
class MergedHeuristic(StateEval):
    def __init__(self, state_evals: list[StateEval]) -> None:
        super().__init__(0)
        self.state_evals = state_evals
    
    def get_value(self, state: Game, action: str|None) -> int:
        return sum((state_eval.get_value(state, action) * 100)//state_eval.max_value for state_eval in self.state_evals)
    
    def get_normalized_value(self, state: Game, action: str|None) -> float:
        return sum(state_eval.get_value(state, action) for state_eval in self.state_evals) / len(self.state_evals)

class WinHeuristic(StateEval):
    def __init__(self) -> None:
        super().__init__(1)
    
    def get_value(self, state: Game, action: str | None) -> int:
        if state.is_win():
            return 1
        return 0
    
class NoDrawHeuristic(StateEval):
    def __init__(self) -> None:
        super().__init__(1)

    def get_value(self, state: Game, action: str | None) -> int:
        if action is not None and str(action) == 'draw':
            return 0
        return 1
    
class SpiderHeuristic(StateEval):
    def __init__(self) -> None:
        super().__init__(200*8)

    def get_value(self, state: Game, action: str | None) -> int:
        score = 0
        for pile in state.name_to_piles['FOUNDATION']:
            if pile.len() > 0:
                score += 200
        for pile in state.name_to_piles['COLUMN']:
            stack_size = 1
            for i in range(pile.len() - 2, -1, -1):
                if pile.cards[i].suit == pile.cards[i+1].suit and pile.cards[i].rank == pile.cards[i+1].rank + 1 and not pile.cards[i].face_down:
                    stack_size += 1
                else:
                    break
            score += stack_size * stack_size
        return score

class ActionCountHeuristic(StateEval):
    def __init__(self) -> None:
        super().__init__(1000)

    def get_value(self, state: Game, action: str | None) -> int:
        if state.is_win():
            return int(1000) # an estimate
        return len(state.get_possible_actions(True))

class Player(ABC):
    # This function returns an str instead of a GameAction,
    # since the current_state is most likely a copy, and we want to prevent
    # the caller from using action.act, since it will be applied on the copied version
    @abstractmethod
    def decide_action(self, current_state: Game) -> str|None:
        raise NotImplementedError

    def _get_performed_state(self, current_state: Game, action: str) -> Game:
        new_state = current_state.copy()
        new_state.logger.temp_deactivate()
        Parser.perform_action_in_game(action, new_state)
        return new_state
    
    def _get_actions(self, current_state: Game) -> list[str]:
        return [str(action) for action in current_state.get_possible_actions(True)]
    
    def _get_state_actions(self, current_state: Game) -> list[tuple[Game, str]]:
        actions = self._get_actions(current_state)
        return [(self._get_performed_state(current_state, action), action) for action in actions]
    
class RandomPlayer(Player):
    def __init__(self, seed: int|None = None, heuristic: StateEval|None=None) -> None:
        self.random = random.Random(seed)
        self.heuristic = heuristic

    def _weighted_choice(self, state_actions: list[tuple[Game, str]]) -> str|None:
        if len(state_actions) == 0:
            return None
        if self.heuristic is None:
            return self.random.choice(state_actions)[1]
        values = [self.heuristic.get_normalized_value(new_state, action) for new_state, action in state_actions]
        return self.random.choices(state_actions, values, k=1)[0][1]

    def decide_action(self, current_state: Game) -> str|None:
        state_actions = self._get_state_actions(current_state)
        action = self._weighted_choice(state_actions)
        return action if action is not None else None
    
class NoRepeatPlayer(Player):
    HASH_TYPE = str # TODO generic
    def __init__(self) -> None:
        self.seen_states: set[NoRepeatPlayer.HASH_TYPE] = set()
    
    def _hash(self, state: Game) -> HASH_TYPE:
        return state.get_game_view()
    
    def _register_state(self, current_state: Game):
        self.seen_states.add(self._hash(current_state))
    
    def _get_new_state_actions(self, current_state: Game) -> list[tuple[Game, str]]:
        state_actions = self._get_state_actions(current_state)
        actions = [(new_state, action) for new_state, action in state_actions\
                   if self._hash(new_state) not in self.seen_states]
        return actions
    
class DFSPlayer(NoRepeatPlayer):
    def __init__(self, heuristic: StateEval|None) -> None:
        super().__init__()
        self.heuristic = heuristic
    
    def decide_action(self, current_state: Game) -> str | None:
        self._register_state(current_state)
        state_actions = self._get_new_state_actions(current_state)
        if len(state_actions) == 0:
            return None
        if self.heuristic is not None:
            not_none_heuristic: StateEval = self.heuristic # otherwise, next line will raise typing errors, even though it's correct
            return max(state_actions, key=lambda state_action: not_none_heuristic.get_value(state_action[0], state_action[1]))[1]
        return state_actions[0][1]

class RandomNoRepeatPlayer(RandomPlayer, NoRepeatPlayer):
    def __init__(self, seed:int|None = None, heuristic: StateEval|None = None) -> None:
        RandomPlayer.__init__(self, seed, heuristic)
        NoRepeatPlayer.__init__(self)
    
    def decide_action(self, current_state: Game) -> str|None:
        assert current_state not in self.seen_states
        self._register_state(current_state)
        state_actions = self._get_new_state_actions(current_state)
        action = self._weighted_choice(state_actions)
        return str(action) if action is not None else None

class MCTSNode:
    def __init__(self, state: Game) -> None:
        self.state: Game = state
        self.visits: int = 0
        self.reward: float = 0
        self.children: dict[str, MCTSChild] = {}
    
    def add_child(self, child: MCTSChild) -> None:
        self.children[child.action] = child
    
    def get_children(self) -> list[MCTSChild]:
        return list(self.children.values())
    
    def is_leaf(self) -> bool:
        return len(self.children) == 0
    
    def create_child(self, new_state: Game, performed_action: str) -> MCTSChild:
        return MCTSChild(new_state, self, performed_action)
    
class MCTSChild(MCTSNode):
    def __init__(self, state: Game, parent: MCTSNode, action: str) -> None:
        super().__init__(state)
        self.parent = parent
        self.action = action

    @property
    def ucb(self, explore_factor: float = 0.5):
        if self.visits == 0:
            return 0 if explore_factor == 0 else math.inf
        else:
            exploit_term = self.reward / self.visits
            explore_term = math.sqrt(math.log(self.parent.visits) / self.visits)
            return exploit_term + explore_factor * explore_term

class MCTSPlayer(Player):
    HASH_TYPE = str
    def __init__(self, time_budget: int, seed: int|None, max_rollout_depth: int,
                 rollout_strategist_gen: Callable[[], Player], reward_func: StateEval) -> None:
        self.time_budget = time_budget
        self.random = random.Random(seed)
        self.hash_to_node: dict[MCTSPlayer.HASH_TYPE, MCTSNode] = {}
        self.max_rollout_depth: int = max_rollout_depth
        self.rollout_strategist_gen = rollout_strategist_gen
        self.reward_func = reward_func
    
    def _get_hash(self, game: Game) -> HASH_TYPE:
        return str(game)

    def _get_state_copy(self, state: Game):
        state = state.copy()
        state.logger.active = False
        return state
    
    def _register_hash(self, node: MCTSNode):
        hash = self._get_hash(node.state)
        self.hash_to_node[hash] = node

    def _expand(self, node: MCTSNode):
        options = self._get_state_actions(node.state)
        for new_state, action in options:
            if self._get_hash(new_state) in self.hash_to_node:
                continue
            child = node.create_child(new_state, action)
            node.add_child(child)
            self._register_hash(child)
    
    def _select_node(self, node: MCTSNode) -> MCTSNode:
        while not node.is_leaf():
            max_nodes = get_max_elements(node.get_children(), lambda child: child.ucb)
            node = self.random.choice(max_nodes)
            if node.visits == 0:
                return node
        self._expand(node)
        if not node.is_leaf():
            node = self.random.choice(node.get_children())
        return node
    
    def _rollout(self, state: Game) -> float:
        depth = 0
        rollout_strategist = self.rollout_strategist_gen()
        last_action: None|str = None
        while not state.is_win() and depth < self.max_rollout_depth:
            action = rollout_strategist.decide_action(state)
            if action is None:
                break
            Parser.perform_action_in_game(action, state)
            last_action = action
            depth += 1
        return self.reward_func.get_normalized_value(state, last_action)
    
    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        node.visits += 1
        node.reward += reward
        if isinstance(node, MCTSChild):
            self._backpropagate(node.parent, reward)
        
    def _get_best_action(self, node: MCTSNode) -> str|None:
        if node.is_leaf():
            return None
        best_children = get_max_elements(node.get_children(), lambda child: child.reward/child.visits)
        return self.random.choice(best_children).action
    
    def decide_action(self, current_state: Game) -> str | None:
        start_time = time.time()
        node = self.hash_to_node.get(self._get_hash(current_state), None)
        if node is None:
            node = MCTSNode(current_state)
            self._register_hash(node)
        node_count = 0
        while time.time() - start_time < self.time_budget:
            node = self._select_node(node)
            reward = self._rollout(self._get_state_copy(node.state))
            self._backpropagate(node, reward)
            node_count += 1
        best_action = self._get_best_action(node)
        print(node_count)
        if best_action is None:
            return str(self.random.choice(current_state.get_possible_actions(True)))
        return best_action