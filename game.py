from __future__ import annotations
from typing import Callable, Sequence, Protocol, ParamSpec, Generic, TypeVar
from abc import ABC, abstractmethod
from base import Deck, Card, Stack, Pile, DealPile, RotateDrawPile, Viewable
import condition as cond
from utility import Logger
from diffs import Diffs
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

T = TypeVar('T', bound=cond.ConditionComponents, contravariant=True)
class ActionArgs(Generic[T], ABC):
    def __init__(self) -> None:
        self.condition: cond.Condition[T]|None
        self.components: T|None

    @abstractmethod
    def _default_summary(self) -> str:
        raise NotImplementedError

    def get_summary(self, all_resolutions: bool, explain: bool) -> str:
        summary = self._default_summary()
        if len(summary) > 0:
            summary += '\n'
        if self.condition is None or self.components is None:
            return summary
        return summary + 'This action can only be performed if:\n' + '-' * 10 + '\n' + self.condition.summary(all_resolutions, explain, self.components) + '\n' + '-' * 10 + '\n'
    
class DrawArgs(ActionArgs[cond.GeneralConditionComponents]):
    def __init__(self, name_to_piles: dict[str, list[Stack]], draw_pile: Pile, condition: cond.Condition[cond.GeneralConditionComponents]|None) -> None:
        self.condition = condition
        self.components: cond.GeneralConditionComponents|None = None
        if self.condition is not None:
            self.components = cond.GeneralConditionComponents(name_to_piles, draw_pile)

    def _default_summary(self) -> str:
        assert not (self.components is None and self.condition is not None)
        attempt = f'Actin \"draw\" is attempted'
        exist = f'Action \"draw\" should be a possible action for this game {cond.Condition.format_TF(self.condition is not None)}'
        return attempt + '\n' + exist

    @staticmethod
    def get(game: Game) -> DrawArgs:
        assert game.draw_pile is not None, "Cannot draw if a draw pile does not exist"
        return DrawArgs(game.name_to_piles, game.draw_pile, game.draw_conditions)

class MoveArgs(ActionArgs[cond.MoveCardComponents]):
    def __init__(self, src_pile: Pile, dest_pile: Stack, condition: cond.Condition[cond.MoveCardComponents]|None):
        self.src_pile = src_pile
        self.dest_pile = dest_pile
        self.condition = condition
        self.components: cond.MoveCardComponents|None = None
        if condition is not None and not src_pile.empty() and not src_pile.peak().face_down: # TODO perhaps handle as conditions?
            self.components = cond.MoveCardComponents(src_pile.peak(), dest_pile)
    
    def _default_summary(self) -> str:
        card = 'NON_EXISTENT_CARD' if self.src_pile.empty() else self.src_pile.peak().get_state_view()
        attempt = f'Action \"move\" is attempted to move {card} from top of {self.src_pile.get_tag()} to {self.dest_pile.get_tag()}'
        exist = f'Action \"move\" from a {self.src_pile.name} to a {self.dest_pile.name} should be a possible action for this game {cond.Condition.format_TF(self.condition is not None)}'
        not_empty = f'Action \"move\" should move at least one card {cond.Condition.format_TF(not self.src_pile.empty())}'
        face_up = f'Action \"move\" can only move face-up card {cond.Condition.format_TF(not self.src_pile.empty() and not self.src_pile.peak().face_down)}'
        if not self.src_pile.empty:
            not_empty += '\n' + face_up # TODO is this the best way?
        return attempt + '\n' + exist + '\n' + not_empty

    @staticmethod
    def from_pos(game: Game, src_pos: PilePos, dest_pos: StackPilePos, auto:bool = False) -> MoveArgs:
        src_pile = game._get_pile(src_pos)
        assert src_pile is not None, f"Cannot move from non-existent pile: {src_pos}"
        dest_pile = game._get_stack(dest_pos)
        assert dest_pile is not None, f"Cannot move to non-existent or non-stack pile: {dest_pos}" # TODO perhaps handle as conditions?
        if auto:
            condition: cond.Condition[cond.MoveCardComponents]|None = game.auto_move_conditions.get((src_pos.pilename, dest_pos.pilename), None)
        else:
            condition: cond.Condition[cond.MoveCardComponents]|None = game.move_conditions.get((src_pos.pilename, dest_pos.pilename), None)
        return MoveArgs(src_pile, dest_pile, condition)
    
class MoveStackArgs(ActionArgs[cond.MoveStackComponents]):
    def __init__(self, src_pile: Stack, src_ind, dest_pile: Stack, condition: cond.Condition[cond.MoveStackComponents]|None):
        self.src_pile = src_pile
        self.src_ind = src_ind
        self.dest_pile = dest_pile
        self.condition = condition
        self.components: cond.MoveStackComponents|None = None
        if condition is not None and src_ind < src_pile.len() and all([not card.face_down for card in src_pile.peak_many(src_ind)]):
            self.components = cond.MoveStackComponents(src_pile.peak_many(src_ind), dest_pile)

    def _default_summary(self) -> str:
        assert self.src_ind < self.src_pile.len(), "non-existant source card action should not be generated"
        cards = 'NON_EXISTENT_STACK' if self.src_ind >= self.src_pile.len() else '-'.join(card.get_state_view() for card in self.src_pile.peak_many(self.src_ind))
        attempt = f'Action \"move_stack\" is attempted to move {cards} from {self.src_pile.get_tag()} to {self.dest_pile.get_tag()}'
        exist = f'Action \"move_stack\" from a {self.src_pile.name} to a {self.dest_pile.name} should be a possible action for this game {cond.Condition.format_TF(self.condition is not None)}'
        not_empty = f'Action \"move_stack\" should move at least one card {cond.Condition.format_TF(not self.src_pile.empty())}' # one card actoins are not generated for move_stack, but technically are correct (also this is always true because of the leading assert)
        face_up = f'Action \"move_stack\" can only move face-up card {cond.Condition.format_TF(all([not card.face_down for card in self.src_pile.peak_many(self.src_ind)]))}'
        return attempt + '\n' + exist + '\n' + not_empty + '\n' + face_up
    
    @staticmethod
    def from_pos(game: Game, src_pos: RunPos, dest_pos: StackPilePos, auto: bool=False) -> MoveStackArgs:
        src_pile = game._get_stack(src_pos.stack_pos)
        assert src_pile is not None, f"Cannot move stack from non-existent pile: {src_pos}"
        dest_pile = game._get_stack(dest_pos)
        assert dest_pile is not None, f"Cannot move stack to non-existent pile: {dest_pos}"
        if auto:
            condition: cond.Condition[cond.MoveStackComponents]|None = game.auto_move_stack_conditions.get((src_pos.stack_pos.pilename, dest_pos.pilename), None)
        else:
            condition: cond.Condition[cond.MoveStackComponents]|None = game.move_stack_conditions.get((src_pos.stack_pos.pilename, dest_pos.pilename), None)
        return MoveStackArgs(src_pile, src_pos.from_ind, dest_pile, condition)

class Game(Viewable):
    class MoveType(Enum):
        Move = 1
        MoveStack = 2
        Draw = 3

    def __init__(self, name: str, should_log: bool = True) -> None:
        self.name: str = name
        self.deck: Deck = Deck(0)
        self.draw_pile: Pile|None = None
        self.started = False
        self.initializers: list[Callable[[], None]] = []
        self.name_to_piles: dict[str, list[Stack]] = {}
        self.move_conditions: dict[tuple[str, str], cond.Condition[cond.MoveCardComponents]] = {}
        self.move_stack_conditions: dict[tuple[str, str], cond.Condition[cond.MoveStackComponents]] = {}
        self.auto_move_conditions: dict[tuple[str, str], cond.Condition[cond.MoveCardComponents]] = {}
        self.auto_move_stack_conditions: dict[tuple[str, str], cond.Condition[cond.MoveStackComponents]] = {}
        self.draw_func: DrawCallable
        self.draw_conditions: cond.Condition[cond.GeneralConditionComponents]|None = None
        self.win_conditions: cond.Condition[cond.GeneralConditionComponents]|None = None
        self.logger: Logger = Logger(should_log)

    def _get_draw_pile_diff(self, other: Game,) -> Diffs:
        if self.draw_pile is None or other.draw_pile is None:
            return Diffs().add(1 if self.draw_pile is not None or other.draw_pile is not None else 0, 1)
        else:
            return self.draw_pile.diff(other.draw_pile)

    def _get_draw_con_diff(self, other: Game, accept_shuffled: bool, minimizer_metric: Callable[[Diffs], float]) -> Diffs:
        if self.draw_conditions is None or other.draw_conditions is None:
            return Diffs().add(1 if self.draw_conditions is not None or other.draw_conditions is not None else 0, 1)
        else:
            return self.draw_conditions.diff(other.draw_conditions, accept_shuffled, minimizer_metric)
        
    def _get_piles_diff(self, other: Game, accept_shuffled: bool, minimizer_metric: Callable[[Diffs], float]) -> Diffs:
        return Diffs().add_dict_diff(self.name_to_piles, other.name_to_piles,
                    lambda a, b: Diffs().add_deep_list_diff(a, b, Stack.diff, minimizer_metric, accept_shuffled, True))
    
    def get_action_condition_diff(self, self_conditions: dict[tuple[str, str], cond.Condition],
                                  other_conditions: dict[tuple[str, str], cond.Condition],
                                  accept_shuffled: bool, minimizer_metric: Callable[[Diffs], float]) -> Diffs:
        return Diffs().add_dict_diff(self_conditions, other_conditions,
                    lambda a, b: a.diff(b, accept_shuffled, minimizer_metric))

    def diff(self, other: Game, accept_shuffled: bool, minimizer_metric: Callable[[Diffs], float]) -> Diffs:
        diff = Diffs()
        # draw
        diff.merge(self._get_draw_pile_diff(other))
        diff.merge(self._get_draw_con_diff(other, accept_shuffled, minimizer_metric))
        # piles
        diff.merge(self._get_piles_diff(other, accept_shuffled, minimizer_metric))
        # move condition diffs * 4
        diff.merge(self.get_action_condition_diff(self.move_conditions, other.move_conditions, accept_shuffled, minimizer_metric))
        diff.merge(self.get_action_condition_diff(self.move_stack_conditions, other.move_stack_conditions, accept_shuffled, minimizer_metric))
        diff.merge(self.get_action_condition_diff(self.auto_move_conditions, other.auto_move_conditions, accept_shuffled, minimizer_metric))
        diff.merge(self.get_action_condition_diff(self.auto_move_stack_conditions, other.auto_move_stack_conditions, accept_shuffled, minimizer_metric))
        # win condition diff
        assert self.win_conditions is not None and other.win_conditions is not None
        diff.merge(self.win_conditions.diff(other.win_conditions, accept_shuffled, minimizer_metric))
        return diff

    def get_description(self) -> str:
        desc = f'''# {self.name}
{self.name} is a Solitaire game, played with {len(self.get_all_cards()) + len(self.deck.cards)} cards. The game has the following piles:\n'''
        if self.draw_pile is not None:
            desc += '- 1 draw pile'
            if isinstance(self.draw_pile, RotateDrawPile):
                desc += ' of type \"rotate\"\n'
            elif isinstance(self.draw_pile, DealPile):
                desc += ' of type \"deal\"\n'
            else:
                raise Exception("Unrecognized draw pile")
        for name, piles in self.name_to_piles.items():
            desc += f'- {len(piles)} `{name}` pile{"s" if len(piles) > 1 else ""}\n'
        if self.draw_pile is not None or len(self.move_conditions) > 0 or len(self.move_stack_conditions) > 0:
            desc += '## Actions\n'
            desc += 'Actions in the game move cards between piles. Each action has conditions that defines its validity. These conditions may involve the following keywords:\n'
            desc += '* Source card: The source card is the card that is being moved. If a stack of cards is being moved together, the source card is the first card in that stack.\n'
            desc += '* Source pile: The source pile is the pile that the source card belongs to prior to the movement.\n'
            desc += '* Destination pile: The destination pile is the target pile that the source card is being moved to.\n'
            desc += '* Destination card: The destination card is the top card of the destination pile. If the destination pile is empty, no destination card exists, and any conditions involving it are resolved as False.\n'
            desc += 'The following actions are possible in the game:\n'
        if self.draw_pile is not None:
            desc += '### Draw\n'
            desc += '- `draw`: The draw action will '
            if isinstance(self.draw_pile, RotateDrawPile):
                desc += f'turn the top {self.draw_pile.draw_count} card{"s" if self.draw_pile.draw_count > 1 else ""} from the draw pile face-up. '
                desc += f'At any point, only the top card of the draw pile can be moved and '
                if self.draw_pile.view_count is None:
                    desc += 'all face-up cards in the draw pile are shown in the game state. '
                else:
                    desc += f'only the top {self.draw_pile.view_count} card{"s" if self.draw_pile.view_count > 1 else ""} are shown in the game state. '
                if self.draw_pile.max_redeals is None or self.draw_pile.max_redeals > 0:
                    desc += f'When all the cards in the draw pile are turned face-up, drawing will rotate all of its cards that haven\'t been moved back into the draw pile. '
                    if self.draw_pile.max_redeals is not None:
                        desc += f'This can be done until {self.draw_pile.max_redeals} pass through the draw pile.'
                    else:
                        desc += f'This can be done for an unlimited number of itmes.'
                else:
                    desc += 'if the draw pile is empty, performing a `draw` action will not do anything.'
            elif isinstance(self.draw_pile, DealPile):
                desc += 'deal 1 card from the draw pile to every ' + 'pile, '.join(self.draw_pile.target_names) + ' pile.'
            else:
                raise Exception("Unrecognized draw pile")
        if self.draw_conditions is not None:
            desc += f' The `draw` action is valid if and only if the following condition is true:\nCondition: {self.draw_conditions.summary(False, False, None)}'
        desc += '\n'
        if len(self.move_conditions) > 0:
            desc += '### Move\n'
            desc += 'A `move` action is valid if it matches one of the listed types, meets all conditions, and only involves face-up cards.\n'
        for (src_pile, dest_pile), cond in self.move_conditions.items():
            desc += f'- `move` from a {src_pile} pile to a {dest_pile} pile: This will move one card from a {src_pile} pile to a {dest_pile} pile and is valid if and only if the following condition is true:\nCondition: {cond.summary(False, False, None)}'
        if len(self.move_stack_conditions) > 0:
            desc += '### Move Stack\n'
            desc += 'A `move_stack` action is valid if it matches one of the listed types, meets all conditions, and only involves face-up cards (all cards in the moving stack should be face-up).\n'
        for (src_pile, dest_pile), cond in self.move_stack_conditions.items():
            desc += f'- `move_stack` from a {src_pile} pile to a {dest_pile} pile: This will move a stack of at least two cards from a {src_pile} pile to a {dest_pile} pile and is valid if and only if the following condition is true:\nCondition: {cond.summary(False, False, None)}'
        desc += '## Win Condition\n'
        assert self.win_conditions is not None
        desc += 'To win the game, the following condition should be true:\n'
        desc += f'Condition: {self.win_conditions.summary(False, False, None)}'
        if len(self.auto_move_conditions) > 0 or len(self.auto_move_stack_conditions) > 0:
            desc += '## Auto Actions\n'
            desc += 'Auto actions are actions that occur automatically as soon as their conditions are met. After every action in the game, all auto actions are checked and performed as many times as necessary.\n'
        if len(self.auto_move_conditions) > 0:
            desc += '### Auto Move\n'
            desc += f'In a game of {self.name}, the following move actions will happen automatically whenever their conditions are true:\n'
            for (src_pile, dest_pile), cond in self.move_conditions.items():
                desc += f'- `move` from a {src_pile} pile to a {dest_pile} pile: This will move one card from a {src_pile} pile to a {dest_pile} pile if and only if the following condition is true:\nCondition: {cond.summary(False, False, None)}'
        if len(self.auto_move_stack_conditions) > 0:
            desc += '## Auto Move Stack\n'
            desc += f'In a game of {self.name}, the following move_stack actions will happen automatically whenever their conditions are true:\n'
            for (src_pile, dest_pile), cond in self.move_conditions.items():
                desc += f'- `move_stack` from a {src_pile} pile to a {dest_pile} pile: This will move a stack of at least two cards from a {src_pile} pile to a {dest_pile} pile if and only if the following condition is true:\nCondition: {cond.summary(False, False, None)}'
        return desc

    def start(self):
        for initializer in self.initializers:
            initializer()
        self.started = True

    def copy(self) -> Game:
        game = Game(self.name, self.logger.active)
        game.started = self.started
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
        assert self.started, "Cannot check the win condition if game has not started"
        assert self.win_conditions is not None, "No win condition defined for the game"
        components = cond.GeneralConditionComponents(self.name_to_piles, self.draw_pile)
        # self.logger.info("WIN CONDITIONS:\n" + self.win_conditions.summary(components))
        self.logger.info_from(["WIN CONDITIONS:\n", (self.win_conditions.summary, [True, False, components])])
        return self.win_conditions.evaluate(components)
    
    def get_draw_summary(self, all_resolutions: bool, explain: bool) -> str:
        args = DrawArgs.get(self)
        return args.get_summary(all_resolutions, explain)
    
    def draw(self, perform: bool=True) -> bool:
        assert self.started, "Cannot draw if game has not started"
        args = DrawArgs.get(self)
        if args.condition is not None and args.components is not None:
            self.logger.info_from(["DRAW CONDITIONS:\n", (args.condition.summary, [True, False, args.components])])
            if not args.condition.evaluate(args.components):
                return False
        valid = self.draw_func(perform)
        if valid and perform:
            self.check_auto_moves()
        return valid

    def define_deal_draw(self, count: int, targets: set[str]) -> None:
        assert self.draw_pile is None, "Defining multiple draw conditions for a game is invalid"
        def initializer():
            assert self.draw_pile is not None
            self.draw_pile.cards = self.deck.deal(count)
        self.draw_pile = DealPile([], targets)
        self._submit_deal_draw_func(targets)
        self.initializers.append(initializer)
    
    def _submit_deal_draw_func(self, targets: set[str]):
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
        def initializer():
            assert self.draw_pile is not None
            self.draw_pile.cards = self.deck.deal(count)
        self.draw_pile = RotateDrawPile([], draw_count, view_count, max_redeals)
        self.draw_func = self.draw_pile.rotate
        self.initializers.append(initializer)

    def define_pile(self, pile_name: str, count: int, face: Stack.Face, starting_cards: list[Card]|None) -> None:
        assert starting_cards is None or len(starting_cards) == count, f"Initial cards define for pile does not match number of expected cards: {count} {starting_cards}"
        self.name_to_piles[pile_name] = self.name_to_piles.get(pile_name, [])
        ind = len(self.name_to_piles[pile_name])
        pile = Stack([], pile_name, ind)
        self.name_to_piles[pile_name].append(pile)
        def initilizer():
            if starting_cards == None:
                pile.cards = self.deck.deal(count)
            else:
                pile.cards = self.deck.extract(starting_cards)
            pile.apply_face(face)
        self.initializers.append(initilizer)

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
        assert self.started, "Cannot make move if game has not started"
        args = MoveArgs.from_pos(self, src_pos, dest_pos, auto)
        if args.condition is None or args.components is None:
            return False
        self.logger.info_from([f"MOVE_CONDITIONS {src_pos} to {dest_pos}\n", (args.condition.summary, [True, False, args.components])])
        if not args.condition.evaluate(args.components):
            return False
        if perform:
            args.dest_pile.add([args.src_pile.get()])
            self.check_auto_moves()
        return True
    
    def get_move_summary(self, all_resolutions: bool, explain: bool, src_pos: PilePos, dest_pos: StackPilePos, auto: bool=False) -> str:
        args = MoveArgs.from_pos(self, src_pos, dest_pos, auto)
        return args.get_summary(all_resolutions, explain)
    
    def move_stack(self, src_pos: RunPos, dest_pos: StackPilePos, perform: bool=True, auto: bool=False) -> bool:
        assert self.started, "Cannot make move stack if game has not started"
        args = MoveStackArgs.from_pos(self, src_pos, dest_pos, auto)
        if args.condition is None or args.components is None:
            return False
        self.logger.info_from([f"MOVE_STACK CONDITIONS {src_pos} to {dest_pos}\n", (args.condition.summary, [True, False, args.components])])
        if not args.condition.evaluate(args.components):
            return False
        if perform:
            args.dest_pile.add(args.src_pile.get_many(src_pos.from_ind))
            self.check_auto_moves()
        return True
    
    def get_move_stack_summary(self, all_resolutions: bool, explain: bool, src_pos: RunPos, dest_pos: StackPilePos, auto: bool=False) -> str:
        args = MoveStackArgs.from_pos(self, src_pos, dest_pos, auto)
        return args.get_summary(all_resolutions, explain)
    
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
        assert self.started, "Cannot check auto move if game has not started"
        while(True):
            actions: list[GameAction] = []
            for src_pilename, dest_pilename in self.auto_move_conditions.keys():
                actions += self._get_move_actions(src_pilename, dest_pilename, True)
            for src_pilename, dest_pilename in self.auto_move_stack_conditions.keys():
                actions += self._get_move_stack_actions(src_pilename, dest_pilename, True)
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
    
    def _get_move_actions(self, src_pilename: str, dest_pilename: str, only_valid: bool) -> list[GameAction[PilePos, StackPilePos, bool, bool]]:
        actions: list[GameAction[PilePos, StackPilePos, bool, bool]] = []
        for src_pos in self._get_pile_positions(src_pilename):
            for dest_pos in self._get_stack_pile_positions(dest_pilename):
                if str(src_pos) != str(dest_pos):
                    actions.append(GameAction(self.move, src_pos=src_pos, dest_pos=dest_pos))
        return actions

    def _get_move_stack_actions(self, src_pilename: str, dest_pilename: str, only_valid: bool) -> list[GameAction[RunPos, StackPilePos, bool, bool]]:
        actions: list[GameAction[RunPos, StackPilePos, bool, bool]] = []
        for src_pos in self._get_stack_pile_positions(src_pilename):
            src_pile = self._get_stack(src_pos)
            if src_pile is None:
                continue
            for dest_pos in self._get_stack_pile_positions(dest_pilename):
                if str(src_pos) == str(dest_pos):
                    continue
                for i in range(src_pile.len() - 2, -1, -1): # stack should have a size of at least 2
                    dest_pile = self.name_to_piles[dest_pilename]
                    if isinstance(dest_pile, Stack) and dest_pile.cards[i].face_down:
                        break
                    actions.append(GameAction(self.move_stack, src_pos=RunPos(src_pos, i), dest_pos=dest_pos))
        return actions

    def get_possible_actions(self, only_valid: bool) -> list[GameAction]:
        actions: list[GameAction] = []
        if self.draw_pile is not None:
            actions.append(GameAction(self.draw))
        if only_valid:
            for src_pilename, dest_pilename in self.move_conditions.keys():
                actions += self._get_move_actions(src_pilename, dest_pilename, only_valid)
            for src_pilename, dest_pilename in self.move_stack_conditions.keys():
                actions += self._get_move_stack_actions(src_pilename, dest_pilename, only_valid)
        else:
            for src_pilename in self.name_to_piles.keys():
                for dest_pilename in list(self.name_to_piles.keys()) + ['DRAW']:
                    actions += self._get_move_actions(src_pilename, dest_pilename, only_valid)
                    actions += self._get_move_stack_actions(src_pilename, dest_pilename, only_valid)
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