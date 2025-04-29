from __future__ import annotations
from typing import Callable, Sequence, Protocol, ParamSpec, Generic
from base import Deck, Card, Stack, Pile, DealPile, RotateDrawPile, Viewable
import condition as cond
from utility import Logger
from enum import Enum
import random

class PilePos:
    def __init__(self, pilename: str) -> None:
        self.pilename = pilename

    def __str__(self) -> str:
        return self.pilename

class StackPilePos(PilePos):
    def __init__(self, pilename: str, ind: int) -> None:
        super().__init__(pilename)
        self.ind = ind
    
    def __str__(self) -> str:
        return f'{self.pilename}[{self.ind}]'

class DrawPilePos(PilePos):
    def __init__(self) -> None:
        super().__init__('DRAW')

class RunPos:
    def __init__(self, stack_pos: StackPilePos, from_ind: int) -> None:
        self.stack_pos = stack_pos
        self.from_ind = from_ind

    def __str__(self) -> str:
        return f'{self.stack_pos}:{self.from_ind}'

# type DrawCallable = Callable[[bool], bool] # Python 3.12 or newer
class DrawCallable(Protocol):
    def __call__(self, perform: bool = True) -> bool:
        ...

P = ParamSpec('P')
# R = TypeVar('R') # return type is always bool
# class GameAction(Generic[P, R]):
#     def __init__(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> None:
class GameAction(Generic[P]):
    def __init__(self, func: Callable[P, bool], *args: P.args, **kwargs: P.kwargs) -> None:
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def act(self, perform: bool, **kwargs) -> bool:
        kwargs['perform'] = perform
        for arg, val in self.kwargs.items():
            kwargs[arg] = val
        return self.func(*self.args, **kwargs)

    def __str__(self) -> str:
        all_args = list(self.args) + list(self.kwargs.values())
        return f"{self.func.__name__} {' '.join([str(arg) for arg in all_args])}"

class Game(Viewable):
    class MoveType(Enum):
        Move = 1
        MoveStack = 2
        Draw = 3

    def __init__(self, name: str, should_log: bool = True) -> None:
        self.name: str = name
        self.deck: Deck = Deck(0)
        self.draw_pile: Pile|None = None
        self.name_to_piles: dict[str, list[Stack]] = {}
        self.move_conditions: dict[tuple[str, str], cond.Condition[cond.MoveCardComponents]] = {}
        self.move_stack_conditions: dict[tuple[str, str], cond.Condition[cond.MoveStackComponents]] = {}
        self.auto_move_conditions: dict[tuple[str, str], cond.Condition[cond.MoveCardComponents]] = {}
        self.auto_move_stack_conditions: dict[tuple[str, str], cond.Condition[cond.MoveStackComponents]] = {}
        self.draw_func: DrawCallable
        self.draw_conditions: cond.Condition[cond.GeneralConditionComponents]|None = None
        self.win_conditions: cond.Condition[cond.GeneralConditionComponents]|None = None
        self.logger: Logger = Logger(should_log)

    def copy(self) -> Game:
        game = Game(self.name, self.logger.active)
        game.deck = self.deck.copy()
        game.draw_pile = self.draw_pile.copy() if self.draw_pile is not None else None
        game.name_to_piles = dict([(name, [pile.copy() for pile in piles]) for name, piles in self.name_to_piles.items()])
        game.move_conditions = self.move_conditions
        game.move_stack_conditions = self.move_stack_conditions
        game.auto_move_conditions = self.auto_move_conditions
        game.auto_move_stack_conditions = self.auto_move_stack_conditions
        if isinstance(game.draw_pile, DealPile):
            game._submit_deal_draw_func(game.draw_pile.target_names)
        elif isinstance(game.draw_pile, RotateDrawPile):
            game.draw_func = game.draw_pile.rotate
        game.draw_conditions = self.draw_conditions
        game.win_conditions = self.win_conditions
        return game
    
    def scramble(self, seed: int|None):
        # shuffle unknown cards to prevent bots from perfect predictions
        class CardAccess:
            def get_card(self) -> Card:
                raise NotImplementedError
            def set_card(self, new_card: Card) -> None:
                raise NotImplementedError
        class PileCardAccess(CardAccess):
            def __init__(self, pile: Pile, index: int) -> None:
                self.pile = pile
                self.index = index
            def get_card(self) -> Card:
                return self.pile.cards[self.index]
            def set_card(self, new_card: Card) -> None:
                self.pile.cards[self.index] = new_card
        class RotateCardBackpileAccess(CardAccess):
            def __init__(self, pile: RotateDrawPile, index: int) -> None:
                self.pile = pile
                self.index = index
            def get_card(self) -> Card:
                return self.pile.backpile[self.index]
            def set_card(self, new_card: Card) -> None:
                self.pile.backpile[self.index] = new_card
        card_locations: list[CardAccess] = []
        if isinstance(self.draw_pile, RotateDrawPile) and self.draw_pile.redeals == 0:
            for i in range(len(self.draw_pile.backpile)):
                card_locations.append(RotateCardBackpileAccess(self.draw_pile, i))
        elif isinstance(self.draw_pile, DealPile):
            for i in range(len(self.draw_pile.cards)):
                card_locations.append(PileCardAccess(self.draw_pile, i))
        for piles in self.name_to_piles.values():
            for pile in piles:
                for i, card in enumerate(pile.cards):
                    if card.face_down:
                        card_locations.append(PileCardAccess(pile, i))
        shuffled: list[int] = list(range(len(card_locations)))
        random.Random(seed).shuffle(shuffled)
        cards: list[Card] = [access.get_card() for access in card_locations]
        for i, j in enumerate(shuffled):
            card_locations[i].set_card(cards[j])

    def get_all_cards(self) -> list[Card]:
        all_cards: list[Card] = []
        for pile in self.get_all_piles():
            all_cards += pile.get_all_cards()
        return all_cards
    
    def get_all_piles(self) -> list[Pile]:
        all_piles: list[Pile] = []
        if self.draw_pile is not None:
            all_piles.append(self.draw_pile)
        for piles in self.name_to_piles.values():
            all_piles += piles
        return all_piles

    def is_win(self):
        assert self.win_conditions is not None, "No win condition defined for the game"
        components = cond.GeneralConditionComponents(self.name_to_piles, self.draw_pile)
        self.logger.info("WIN CONDITIONS:\n" + self.win_conditions.summary(components))
        return self.win_conditions.evaluate(components)
    
    def draw(self, perform: bool=True) -> bool:
        if self.draw_conditions is not None:
            components = cond.GeneralConditionComponents(self.name_to_piles, self.draw_pile)
            self.logger.info("DRAW CONDITIONS:\n" + self.draw_conditions.summary(components))
            if not self.draw_conditions.evaluate(components):
                return False
        if self.draw_pile is None:
            return False # no draw pile, action invalid
        valid = self.draw_func(perform)
        if valid and perform:
            self.check_auto_moves()
        return valid

    def define_deal_draw(self, count: int, targets: list[str]) -> None:
        assert self.draw_pile is None, "Defining multiple draw conditions for a game is invalid"
        self.draw_pile = DealPile(self.deck.deal(count), targets)
        self._submit_deal_draw_func(targets)
    
    def _submit_deal_draw_func(self, targets: list[str]):
        def deal_draw(perform: bool=True) -> bool:
            assert self.draw_pile is not None, "Attempting to draw from non-existant draw card"
            if self.draw_pile.len() == 0:
                return False
            if not perform:
                return True
            for name in targets:
                for pile in self.name_to_piles.get(name, []):
                    if not self.draw_pile.empty():
                        pile.add([self.draw_pile.get()])
            return True
        self.draw_func = deal_draw

    def define_rotate_draw(self, count: int, draw_count: int, view_count: int|None, max_redeals: int|None) -> None:
        assert self.draw_pile is None, "Defining multiple draw conditions for a game is invalid"
        self.draw_pile = RotateDrawPile(self.deck.deal(count), draw_count, view_count, max_redeals)
        self.draw_func = self.draw_pile.rotate

    def define_pile(self, pile_name: str, count: int, face: Stack.Face, starting_cards: list[Card]|None) -> None:
        assert starting_cards is None or len(starting_cards) == count, f"Initial cards define for pile does not match number of expected cards: {count} {starting_cards}"
        if starting_cards == None:
            starting_cards = self.deck.deal(count)
        self.name_to_piles[pile_name] = self.name_to_piles.get(pile_name, [])
        ind = len(self.name_to_piles[pile_name])
        pile = Stack(starting_cards, pile_name, ind)
        pile.apply_face(face)
        self.name_to_piles[pile_name].append(pile)

    def _get_stack(self, pos: StackPilePos) -> Stack|None:
        if pos.pilename not in self.name_to_piles:
            return None
        if len(self.name_to_piles[pos.pilename]) <= pos.ind:
            return None
        return self.name_to_piles[pos.pilename][pos.ind]

    def _get_pile(self, pos: PilePos) -> Pile|None:
        if isinstance(pos, DrawPilePos):
            return self.draw_pile
        elif isinstance(pos, StackPilePos):
            return self._get_stack(pos)
        else:
            raise Exception(f"Pile Position type not recognized {pos}")

    # Invalid syntax is getting an exception, while invalid move is getting False
    def move(self, src_pos: PilePos, dest_pos: StackPilePos, perform: bool=True, auto: bool=False) -> bool:
        src_pile = self._get_pile(src_pos)
        assert src_pile is not None, f"Cannot move from non-existent pile: {src_pos}"
        dest_pile = self._get_stack(dest_pos)
        assert dest_pile is not None, f"Cannot move to non-existent or non-stack pile: {dest_pos}" # TODO perhaps handle as conditions?
        if auto:
            condition: cond.Condition[cond.MoveCardComponents]|None = self.auto_move_conditions.get((src_pos.pilename, dest_pos.pilename), None)
        else:
            condition: cond.Condition[cond.MoveCardComponents]|None = self.move_conditions.get((src_pos.pilename, dest_pos.pilename), None)
        if condition is None or src_pile.empty() or src_pile.peak().face_down: # TODO perhaps handle as conditions?
            return False
        components: cond.MoveCardComponents = cond.MoveCardComponents(src_pile.peak(), dest_pile)
        self.logger.info(f"MOVE_CONDITIONS {src_pos} to {dest_pos}" + condition.summary(components))
        if not condition.evaluate(components):
            return False
        if perform:
            dest_pile.add([src_pile.get()])
            self.check_auto_moves()
        return True
    
    def move_stack(self, src_pos: RunPos, dest_pos: StackPilePos, perform: bool=True, auto: bool=False) -> bool:
        src_pile = self._get_stack(src_pos.stack_pos)
        assert src_pile is not None, f"Cannot move stack from non-existent pile: {src_pos}"
        dest_pile = self._get_stack(dest_pos)
        assert dest_pile is not None, f"Cannot move stack to non-existent pile: {dest_pos}"
        if auto:
            condition: cond.Condition[cond.MoveStackComponents]|None = self.auto_move_stack_conditions.get((src_pos.stack_pos.pilename, dest_pos.pilename), None)
        else:
            condition: cond.Condition[cond.MoveStackComponents]|None = self.move_stack_conditions.get((src_pos.stack_pos.pilename, dest_pos.pilename), None)
        if condition is None or src_pos.from_ind >= src_pile.len() or any([card.face_down for card in src_pile.peak_many(src_pos.from_ind)]):
            return False
        components: cond.MoveStackComponents = cond.MoveStackComponents(src_pile.peak_many(src_pos.from_ind), dest_pile)
        self.logger.info(f"MOVE_STACK CONDITIONS {src_pos} to {dest_pos}" + condition.summary(components))
        if not condition.evaluate(components):
            return False
        if perform:
            dest_pile.add(src_pile.get_many(src_pos.from_ind))
            self.check_auto_moves()
        return True
    
    def _check_pilename(self, name: str, stack_only: bool) -> bool:
        if name == 'DRAW':
            return True if not stack_only else False
        elif name in self.name_to_piles:
            return True
        return False
    
    def define_win_cond(self, condition: cond.Condition[cond.GeneralConditionComponents]):
        assert self.win_conditions is None, f"Cannot define win conditiosn twice, use AND or OR to combine the rules"
        self.win_conditions = condition
    
    def define_draw_cond(self, condition: cond.Condition[cond.GeneralConditionComponents]):
        assert self.draw_pile is not None, f"Cannot define draw conditions for non-existent draw pile"
        assert self.draw_conditions is None, f"Cannot define draw conditions twice, use AND or OR to combine the rules"
        self.draw_conditions = condition
    
    def define_move(self, src_pilename: str, dest_pilename: str, condition: cond.Condition[cond.MoveCardComponents]) -> None:
        assert self._check_pilename(src_pilename, False), f"Cannot define move from non-existent pile {src_pilename}"
        assert self._check_pilename(dest_pilename, True), f"Cannot define move to non-existent or non-stack pile {dest_pilename}"
        assert (src_pilename, dest_pilename) not in self.move_conditions, f"Cannot define move conditions for same piles twice, use AND or OR to combine the rules"
        self.move_conditions[(src_pilename, dest_pilename)] = condition
    
    def define_stack_move(self, src_pilename: str, dest_pilename: str, condition: cond.Condition[cond.MoveStackComponents]) -> None:
        assert self._check_pilename(src_pilename, True), f"Cannot define stack move from non-existent or non-stack pile {src_pilename}"
        assert self._check_pilename(dest_pilename, True), f"Cannot define stack move to non-existent or non-stack pile {dest_pilename}"
        assert (src_pilename, dest_pilename) not in self.move_stack_conditions, f"Cannot define move_stack conditions for same piles twice, use AND or OR to combine the rules"
        self.move_stack_conditions[(src_pilename, dest_pilename)] = condition

    def define_auto_move(self, src_pilename: str, dest_pilename: str, condition: cond.Condition[cond.MoveCardComponents]) -> None:
        assert self._check_pilename(src_pilename, False), f"Cannot define auto move from non-existent pile {src_pilename}"
        assert self._check_pilename(dest_pilename, True), f"Cannot define auto move to non-existent or non-stack pile {dest_pilename}"
        self.auto_move_conditions[(src_pilename, dest_pilename)] = condition
    
    def define_auto_stack_move(self, src_pilename: str, dest_pilename: str, condition: cond.Condition[cond.MoveStackComponents]) -> None:
        assert self._check_pilename(src_pilename, True), f"Cannot define auto stack move from non-existent or non-stack pile {src_pilename}"
        assert self._check_pilename(dest_pilename, True), f"Cannot define auto stack move to non-existent or non-stack pile {dest_pilename}"
        self.auto_move_stack_conditions[(src_pilename, dest_pilename)] = condition
    
    def check_auto_moves(self):
        while(True):
            actions: list[GameAction] = []
            for src_pilename, dest_pilename in self.auto_move_conditions.keys():
                actions += self._get_move_actions(src_pilename, dest_pilename)
            for src_pilename, dest_pilename in self.auto_move_stack_conditions.keys():
                actions += self._get_move_stack_actions(src_pilename, dest_pilename)
            actions = self._filter_valid(actions, auto=True)
            if len(actions) == 0:
                break
            self.logger.info(f"valid auto-action found: {actions[0]}")
            actions[0].act(perform=True, auto=True)

    def _get_stack_pile_positions(self, pilename) -> Sequence[StackPilePos]:
        return [StackPilePos(pilename, pile.ind) for pile in self.name_to_piles.get(pilename, [])]
    
    def _get_pile_positions(self, pilename) -> Sequence[PilePos]:
        if pilename == 'DRAW':
            return [DrawPilePos()]
        return self._get_stack_pile_positions(pilename)
    
    def _filter_valid(self, actions: list[GameAction], auto: bool=False) -> list[GameAction]:
        self.logger.temp_deactivate()
        if auto:
            actions = [action for action in actions if action.act(perform=False, auto=auto)]
        else: # some non-auto action (draw) can't get auto as input
            actions = [action for action in actions if action.act(perform=False)]
        self.logger.revert_activation()
        return actions
    
    def _get_move_actions(self, src_pilename: str, dest_pilename: str) -> list[GameAction[PilePos, StackPilePos, bool, bool]]:
        actions: list[GameAction[PilePos, StackPilePos, bool, bool]] = []
        for src_pos in self._get_pile_positions(src_pilename):
            for dest_pos in self._get_stack_pile_positions(dest_pilename):
                if str(src_pos) != str(dest_pos):
                    actions.append(GameAction(self.move, src_pos=src_pos, dest_pos=dest_pos))
        return actions

    def _get_move_stack_actions(self, src_pilename: str, dest_pilename: str) -> list[GameAction[RunPos, StackPilePos, bool, bool]]:
        actions: list[GameAction[RunPos, StackPilePos, bool, bool]] = []
        for src_pos in self._get_stack_pile_positions(src_pilename):
            src_pile = self._get_stack(src_pos)
            if src_pile is None:
                continue
            for dest_pos in self._get_stack_pile_positions(dest_pilename):
                for i in range(src_pile.len() - 1): # stack should have a size of at least 2
                    if str(src_pos) != str(dest_pos):
                        actions.append(GameAction(self.move_stack, src_pos=RunPos(src_pos, i), dest_pos=dest_pos))
        return actions

    def get_possible_actions(self, only_valid: bool) -> list[GameAction]:
        actions: list[GameAction] = []
        if self.draw_pile is not None:
            actions.append(GameAction(self.draw))
        for src_pilename in list(self.name_to_piles.keys()) + ['DRAW']:
            for dest_pilename in self.name_to_piles.keys():
                actions += self._get_move_actions(src_pilename, dest_pilename)
                actions += self._get_move_stack_actions(src_pilename, dest_pilename)
        if only_valid:
            return self._filter_valid(actions)
        return actions

    def get_game_view(self) -> str:
        ret = self.name + '\n'
        if self.draw_pile is not None:
            ret += self.draw_pile.get_game_view() + '\n'
        for piles in self.name_to_piles.values():
            for pile in piles:
                ret += pile.get_game_view() + '\n'
        return ret
    
    # TODO remove duplicate code (get_state_view/get_game_view)
    def get_state_view(self) -> str:
        ret = self.name + '\n'
        if self.draw_pile is not None:
            ret += self.draw_pile.get_state_view() + '\n'
        for piles in self.name_to_piles.values():
            for pile in piles:
                ret += pile.get_state_view() + '\n'
        return ret