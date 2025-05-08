from __future__ import annotations
from abc import ABC, abstractmethod
from game import Game, GameAction
import random
from parser import Parser
from typing import Callable
import math
import time

class Player(ABC):
    # This function returns an str instead of a GameAction,
    # since the current_state is most likely a copy, and we want to prevent
    # the caller from using action.act, since it will be applied on the copied version
    @abstractmethod
    def decide_action(self, current_state: Game) -> str|None:
        raise NotImplementedError

    def _get_performed_state(self, current_state: Game, action: GameAction) -> Game:
        new_state = current_state.copy()
        new_state.logger.temp_deactivate()
        Parser.perform_action_in_game(str(action), new_state)
        return new_state
    
class RandomPlayer(Player):
    def __init__(self, seed: int|None = None, heuristic: Callable[[Game], int]|None=None) -> None:
        self.random = random.Random(seed)
        self.heuristic = heuristic

    def _weighted_choice(self, current_state: Game, actions: list[GameAction]) -> GameAction|None:
        if len(actions) == 0:
            return None
        if self.heuristic is None:
            return self.random.choice(actions)
        values = [self.heuristic(self._get_performed_state(current_state, action)) for action in actions]
        return self.random.choices(actions, values, k=1)[0]

    def decide_action(self, current_state: Game) -> str|None:
        actions = current_state.get_possible_actions(True)
        action = self._weighted_choice(current_state, actions)
        return str(action) if action is not None else None
    
class NoRepeatPlayer(Player):
    HASH_TYPE = str # TODO generic
    def __init__(self) -> None:
        self.seen_states: set[NoRepeatPlayer.HASH_TYPE] = set()
    
    def _hash(self, state: Game) -> HASH_TYPE:
        return state.get_game_view()

    def _get_new_state_hash(self, current_state: Game, action: GameAction) -> HASH_TYPE:
        return self._hash(self._get_performed_state(current_state, action))

class RandomNoRepeatPlayer(RandomPlayer, NoRepeatPlayer):
    def __init__(self, seed:int|None = None, heuristic: Callable[[Game], int]|None = None) -> None:
        RandomPlayer.__init__(self, seed, heuristic)
        NoRepeatPlayer.__init__(self)
    
    def decide_action(self, current_state: Game) -> str|None:
        self.seen_states.add(self._hash(current_state))
        actions = current_state.get_possible_actions(True)
        actions = [action for action in actions if self._get_new_state_hash(current_state, action) not in self.seen_states]
        action = self._weighted_choice(current_state, actions)
        return str(action) if action is not None else None
    
def spider_heuristic(game: Game) -> int:
    score = 0
    for pile in game.name_to_piles['FOUNDATION']:
        if pile.len() > 0:
            score += 200
    for pile in game.name_to_piles['COLUMN']:
        stack_size = 1
        for i in range(pile.len() - 2, -1, -1):
            if pile.cards[i].suit == pile.cards[i+1].suit and pile.cards[i].rank == pile.cards[i+1].rank + 1 and not pile.cards[i].face_down:
                stack_size += 1
            else:
                break
        score += stack_size * stack_size
    return score

def action_count_heuristic(game: Game) -> int:
    if game.is_win():
        return int(1e12)
    return len(game.get_possible_actions(True))

class MCTSNode:
    def __init__(self, state: Game) -> None:
        self.state: Game = state
        self.visits: int = 0
        self.wins: int = 0
        self.children: dict[str, MCTSChild] = {}
    
    def add_child(self, child: MCTSChild) -> None:
        self.children[child.action] = child
    
    def get_children(self) -> list[MCTSChild]:
        return list(self.children.values())
    
    def is_leaf(self) -> bool:
        return len(self.children) == 0
    
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
            exploit_term = self.wins / self.visits
            explore_term = math.sqrt(math.log(self.parent.visits) / self.visits)
            return exploit_term + explore_factor * explore_term

class MCTSPlayer(Player):
    HASH_TYPE = str
    def __init__(self, time_budget: int, seed: int|None, max_rollout_depth: int, rollout_strategist_gen: Callable[[], Player]) -> None:
        self.time_budget = time_budget
        self.random = random.Random(seed)
        self.hash_to_node: dict[MCTSPlayer.HASH_TYPE, MCTSNode] = {}
        self.max_rollout_depth: int = max_rollout_depth
        self.rollout_strategist_gen = rollout_strategist_gen
    
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
        options = node.state.get_possible_actions(True)
        for option in options:
            new_state = self._get_state_copy(node.state)
            Parser.perform_action_in_game(str(option), new_state)
            if self._get_hash(new_state) in self.hash_to_node:
                continue
            child = MCTSChild(new_state, node, str(option))
            node.add_child(child)
            self._register_hash(child)
    
    def _select_node(self, node: MCTSNode) -> MCTSNode:
        while not node.is_leaf():
            max_ucb = max([child.ucb for child in node.get_children()])
            max_nodes = [n for n in node.get_children() if n.ucb == max_ucb]
            node = self.random.choice(max_nodes)
            if node.visits == 0:
                return node
        self._expand(node)
        if not node.is_leaf():
            node = self.random.choice(node.get_children())
        return node
    
    def _rollout(self, state: Game) -> bool:
        depth = 0
        rollout_strategist = self.rollout_strategist_gen()
        while not state.is_win() and depth < self.max_rollout_depth:
            action = rollout_strategist.decide_action(state)
            if action is None:
                break
            Parser.perform_action_in_game(action, state)
            # actions = state.get_possible_actions(True)
            # self.random.choice(actions).act(True)
            depth += 1
        return state.is_win()
    
    def _backpropagate(self, node: MCTSNode, is_win: bool) -> None:
        node.visits += 1
        node.wins += 1 if is_win else 0
        if isinstance(node, MCTSChild):
            self._backpropagate(node.parent, is_win)
        
    def _get_best_action(self, node: MCTSNode) -> str|None:
        if node.is_leaf():
            return None
        best_child = max(node.get_children(), key=lambda child: child.wins/child.visits)
        return best_child.action
    
    def decide_action(self, current_state: Game) -> str | None:
        start_time = time.time()
        node = self.hash_to_node.get(self._get_hash(current_state), None)
        if node is None:
            node = MCTSNode(current_state)
            self._register_hash(node)
        node_count = 0
        while time.time() - start_time < self.time_budget:
            node = self._select_node(node)
            is_win = self._rollout(self._get_state_copy(node.state))
            self._backpropagate(node, is_win)
            node_count += 1
        best_action = self._get_best_action(node)
        print(node_count)
        if best_action is None:
            return str(self.random.choice(current_state.get_possible_actions(True)))
        return best_action