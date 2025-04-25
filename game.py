from typing import TypeVar, List, Callable, Sequence, Protocol
from base import Deck, Suit, Card, Stack, Pile, DealPile, RotateDrawPile, Viewable
import condition as cond
from utility import TextUtil, Logger
import utility as util
from enum import StrEnum, Enum

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

class DrawCallable(Protocol):
    def __call__(self, perform: bool = True) -> bool:
        ...

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
        self.logger: Logger = Logger(should_log)

    def is_win(self):
        return False # TODO
    
    def draw(self, perform: bool=True) -> bool:
        return self.draw_func(perform)

    def define_deal_draw(self, count: int, targets: list[str]) -> None:
        assert self.draw_pile is None, "Defining multiple draw conditions for a game is invalid"
        self.draw_pile = DealPile(self.deck.deal(count))
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
    def move(self, src_pos: PilePos, dest_pos: StackPilePos, perform: bool=True) -> bool:
        src_pile = self._get_pile(src_pos)
        assert src_pile is not None, f"Cannot move from non-existent pile: {src_pos}"
        dest_pile = self._get_stack(dest_pos)
        assert dest_pile is not None, f"Cannot move to non-existent or non-stack pile: {dest_pos}"
        if (src_pos.pilename, dest_pos.pilename) not in self.move_conditions:
            return False
        condition: cond.Condition[cond.MoveCardComponents] = self.move_conditions[src_pos.pilename, dest_pos.pilename]
        if src_pile.empty() or src_pile.peak().face_down:
            return False
        components: cond.MoveCardComponents = cond.MoveCardComponents(src_pile.peak(), dest_pile)
        self.logger.info(condition.summary(components))
        if not condition.evaluate(components):
            self.logger.info(TextUtil.get_colored_text("EVALUATED: FALSE", TextUtil.TEXT_COLOR.Red))
            return False
        self.logger.info(TextUtil.get_colored_text("EVALUATED: TRUE", TextUtil.TEXT_COLOR.Green))
        if perform:
            dest_pile.add([src_pile.get()])
        return True
    
    def move_stack(self, src_pos: RunPos, dest_pos: StackPilePos, perform: bool = True) -> bool:
        src_pile = self._get_stack(src_pos.stack_pos)
        assert src_pile is not None, f"Cannot move stack from non-existent pile: {src_pos}"
        dest_pile = self._get_stack(dest_pos)
        assert dest_pile is not None, f"Cannot move stack to non-existent pile: {dest_pos}"
        if (src_pos.stack_pos.pilename, dest_pos.pilename) not in self.move_stack_conditions:
            return False
        condition: cond.Condition[cond.MoveStackComponents] = self.move_stack_conditions[src_pos.stack_pos.pilename, dest_pos.pilename]
        if src_pos.from_ind >= src_pile.len() or any([card.face_down for card in src_pile.peak_many(src_pos.from_ind)]):
            return False
        components: cond.MoveStackComponents = cond.MoveStackComponents(src_pile.peak_many(src_pos.from_ind), dest_pile)
        self.logger.info(condition.summary(components))
        if not condition.evaluate(components):
            self.logger.info(TextUtil.get_colored_text("EVALUATED: FALSE", TextUtil.TEXT_COLOR.Red))
            return False
        self.logger.info(TextUtil.get_colored_text("EVALUATED: TRUE", TextUtil.TEXT_COLOR.Green))
        if perform:
            dest_pile.add(src_pile.get_many(src_pos.from_ind))
        return True
    
    def _check_pilename(self, name: str, stack_only: bool) -> bool:
        if name == 'DRAW':
            return True if not stack_only else False
        elif name in self.name_to_piles:
            return True
        return False
    
    def define_move(self, src_pilename: str, dest_pilename: str, condition: cond.Condition[cond.MoveCardComponents]) -> None:
        assert self._check_pilename(src_pilename, False), f"Cannot define move from non-existent pile {src_pilename}"
        assert self._check_pilename(dest_pilename, True), f"Cannot define move to non-existent or non-stack pile {dest_pilename}"
        self.move_conditions[(src_pilename, dest_pilename)] = condition
    
    def define_stack_move(self, src_pilename: str, dest_pilename: str, condition: cond.Condition[cond.MoveStackComponents]) -> None:
        assert self._check_pilename(src_pilename, True), f"Cannot define stack move from non-existent or non-stack pile {src_pilename}"
        assert self._check_pilename(dest_pilename, True), f"Cannot define stack move to non-existent or non-stack pile {dest_pilename}"
        self.move_stack_conditions[(src_pilename, dest_pilename)] = condition

    def define_auto_move(self, src_pilename: str, dest_pilename: str, condition: cond.Condition[cond.MoveCardComponents]) -> None:
        assert self._check_pilename(src_pilename, False), f"Cannot define auto move from non-existent pile {src_pilename}"
        assert self._check_pilename(dest_pilename, True), f"Cannot define auto move to non-existent or non-stack pile {dest_pilename}"
        self.auto_move_conditions[(src_pilename, dest_pilename)] = condition
    
    def define_auto_stack_move(self, src_pilename: str, dest_pilename: str, condition: cond.Condition[cond.MoveStackComponents]) -> None:
        assert self._check_pilename(src_pilename, True), f"Cannot define auto stack move from non-existent or non-stack pile {src_pilename}"
        assert self._check_pilename(dest_pilename, True), f"Cannot define auto stack move to non-existent or non-stack pile {dest_pilename}"
        self.auto_move_stack_conditions[(src_pilename, dest_pilename)] = condition

    def _get_stack_pile_positions(self, pilename) -> Sequence[StackPilePos]:
        return [StackPilePos(pilename, pile.ind) for pile in self.name_to_piles.get(pilename, [])]

    def _get_pile_positions(self, pilename) -> Sequence[PilePos]:
        if pilename == 'DRAW':
            return [DrawPilePos()]
        return self._get_stack_pile_positions(pilename)
    
    def _get_move_actions(self, src_pilename: str, dest_pilename: str) -> list[tuple[Callable[[PilePos, StackPilePos], bool], dict]]:
        actions: list[tuple[Callable[[PilePos, StackPilePos], bool], dict]] = []
        for src_pos in self._get_pile_positions(src_pilename):
            for dest_pos in self._get_stack_pile_positions(dest_pilename):
                if str(src_pos) != str(dest_pos):
                    actions.append((self.move, {'src_pos': src_pos, 'dest_pos': dest_pos}))
        return actions

    def _get_move_stack_actions(self, src_pilename: str, dest_pilename: str) -> list[tuple[Callable[[RunPos, StackPilePos], bool], dict]]:
        actions: list[tuple[Callable[[RunPos, StackPilePos], bool], dict]] = []
        for src_pos in self._get_stack_pile_positions(src_pilename):
            src_pile = self._get_stack(src_pos)
            if src_pile is None:
                continue
            for dest_pos in self._get_stack_pile_positions(dest_pilename):
                for i in range(src_pile.len() - 1): # stack should have a size of at least 2
                    if str(src_pos) != str(dest_pos):
                        actions.append((self.move_stack, {'src_pos': RunPos(src_pos, i), 'dest_pos': dest_pos}))
        return actions

    def get_possible_actions(self, only_valid: bool) -> list[tuple[Callable[..., bool], dict]]:
        actions: list[tuple[Callable[..., bool], dict]] = []
        if self.draw_pile is not None:
            actions.append((self.draw, {}))
        for src_pilename in list(self.name_to_piles.keys()) + ['DRAW']:
            for dest_pilename in self.name_to_piles.keys():
                actions += self._get_move_actions(src_pilename, dest_pilename)
                actions += self._get_move_stack_actions(src_pilename, dest_pilename)
        if only_valid:
            self.logger.temp_deactivate()
            actions = [action for action in actions if action[0](**action[1], perform=False)]
            self.logger.revert_activation()
        return actions

    def get_game_view(self) -> str:
        ret = self.name + '\n'
        if self.draw_pile is not None:
            ret += self.draw_pile.get_game_view() + '\n'
        for pilename, piles in self.name_to_piles.items():
            for pile in piles:
                ret += pile.get_game_view() + '\n'
        # ret += "Possible Moves:\n"
        # if hasattr(self, 'draw'):
        #     ret += 'draw\n'
        # for src_pilename, dest_pilename in self.move_conditions.keys():
        #     ret += f'move {src_pilename} {dest_pilename}\n'
        # for src_pilename, dest_pilename in self.move_stack_conditions.keys():
        #     ret += f'move_stack {src_pilename} {dest_pilename}\n'
        return ret
    
    # TODO remove duplicate code (get_state_view/get_game_view)
    def get_state_view(self) -> str:
        ret = self.name + '\n'
        if self.draw_pile is not None:
            ret += self.draw_pile.get_state_view()
        for pilename, piles in self.name_to_piles.items():
            for pile in piles:
                ret += pile.get_state_view() + '\n'
        return ret
    
T = TypeVar('T')
class Parser:
    @staticmethod
    def parse_str(s: str) -> str:
        return s

    @staticmethod
    def parse_number(s: str) -> int:
        try:
            val = int(s)
            return val
        except Exception as e:
            raise Exception(f"Cannot parse value as a number: {s}")
    
    @staticmethod
    def parse_suit(s: str) -> Suit:
        if s == 'SPADES':
            return Suit.Spades
        elif s == 'HEARTS':
            return Suit.Hearts
        elif s == 'CLUBS':
            return Suit.Clubs
        elif s == 'DIAMONDS':
            return Suit.Diamonds
        raise Exception(f"Suit not recognized: {s}")
    
    @staticmethod
    def parse_short_suit(s: str) -> Suit:
        if s == 'S':
            return Suit.Spades
        elif s == 'H':
            return Suit.Hearts
        elif s == 'C':
            return Suit.Clubs
        elif s == 'D':
            return Suit.Diamonds
        raise Exception(f"Suit not recognized: {s}")
    
    @staticmethod
    def parse_rank(s: str) -> int:
        if s == 'K':
            return 13
        elif s == 'Q':
            return 12
        elif s == 'J':
            return 11
        rank = int(s)
        assert rank >= 1 and rank <= 10, f"Rank is not in the expected range: {s}; it should be in range [1, 10] or J/Q/K"
        return rank
    
    @staticmethod
    def parse_card(s: str, is_face_down: bool = False) -> Card:
        suit = Parser.parse_short_suit(s[0])
        rank = Parser.parse_rank(s[1:])
        return Card(suit, rank, is_face_down)
    
    @staticmethod
    def parse_pile_face(s: str) -> Stack.Face:
        for val in Stack.Face:
            if s == val:
                return val
        raise Exception(f"Pile facing option not recognized: {s}")
    
    @staticmethod
    def parse_list(s: str) -> list[str]:
        s = s.strip()
        return [part.strip() for part in s.split(',')]
    
    @staticmethod
    def parse_items(s: str, parse_func: Callable[[str], T]) -> List[T]:
        if s[0] == '{' and s[-1] == '}':
            return [parse_func(suit_text) for suit_text in Parser.parse_list(s[1:-1])]
        return [parse_func(s)]
    
    @staticmethod
    def split_line(s: str) -> list[str]:
        parts: list[str] = [""]
        list_counter = 0
        for char in s:
            if char == '{':
                list_counter += 1
            elif char == '}':
                list_counter -= 1
            if list_counter < 0 or list_counter > 1: # Note that this grammar does not have nested lists
                raise Exception(f"Line contains invalid list: {s}")
            if char in [' ', '\t'] and list_counter == 0:
                parts.append("")
            else:
                parts[-1] += char
        return [part for part in parts if len(part) > 0]

    @staticmethod
    def remove_comments(game_desc: str) -> str:
        lines = game_desc.splitlines()
        for i in range(len(lines)):
            if '#' in lines[i]:
                ind = lines[i].find('#')
                lines[i] = lines[i][:ind]
        lines = [line for line in lines if len(line) > 0]
        return '\n'.join(lines)
    
    @staticmethod
    def apply(section_desc: list[str], game: Game, seed: int|None):
        section_title = section_desc[0]
        section_desc = section_desc[1:]
        if section_title == '$cards':
            Parser.apply_deck(section_desc, game, seed)
        elif section_title == '$initial':
            Parser.apply_initial(section_desc, game)
        elif section_title == '$moves':
            Parser.apply_moves(section_desc, game)
        elif section_title == '$auto':
            Parser.apply_auto(section_desc, game)
        elif section_title == '$win':
            Parser.apply_win(section_desc, game)
        else:
            raise Exception(f"Invalid section title: {section_title}")
        
    @staticmethod
    def apply_deck(deck_desc: list[str], game: Game, seed: int|None):
        assert len(deck_desc) == 1, "deck description not recognized [invalid line count]"
        # finds = re.findall(r"^\s*DECK\s+(\d+)\s+\{\s*([A-Za-z, ]+)\s*\}\s*$", deck_desc[1])
        # assert len(finds) == 1, "deck description does not match with the expected format"
        # count, suits_text = finds[0]
        _, count_text, suits_text = Parser.split_line(deck_desc[0])
        count = Parser.parse_number(count_text)
        suits = Parser.parse_items(suits_text, Parser.parse_suit)
        game.deck = Deck(count, suits)
        game.deck.shuffle(seed)

    @staticmethod
    def apply_initial(initial_desc: list[str], game: Game):
        for initial in initial_desc:
            parts = Parser.split_line(initial)
            if parts[0] == 'DRAW':
                count = Parser.parse_number(parts[1])
                if parts[2] == 'DEAL':
                    game.define_deal_draw(count, Parser.parse_items(parts[3], Parser.parse_str))
                elif parts[2] == 'ROTATE':
                    draw_count = Parser.parse_number(parts[3])
                    view_count = Parser.parse_number(parts[4]) if parts[4] != 'U' else None
                    max_redeals = Parser.parse_number(parts[5]) if parts[5] != 'U' else None
                    game.define_rotate_draw(count, draw_count, view_count, max_redeals)
            else:
                pile_name = parts[0]
                count = Parser.parse_number(parts[1])
                face = Stack.Face.FACE_LAST # default value is here because it's a property of the gdl to have this for default, not a property of the game or base
                cards: list[Card]|None = None
                if len(parts) > 2 and parts[2] in Stack.Face:
                    Parser.parse_pile_face(parts[2])
                if len(parts) > 2 and face is None or len(parts) > 3:
                    cards = Parser.parse_items(parts[-1], Parser.parse_card)
                game.define_pile(pile_name, count, face, cards)

    @staticmethod
    def apply_moves(moves_desc: list[str], game: Game, auto: bool = False):
        while len(moves_desc) > 0:
            move_def = Parser.split_line(moves_desc[0])
            if move_def[0] == 'MOVE':
                assert len(move_def) == 3, f"MOVE arguments missing or extra: {moves_desc[0]}"
                src_pilenames = Parser.parse_items(move_def[1], Parser.parse_str)
                dst_pilenames = Parser.parse_items(move_def[2], Parser.parse_str)
                cond, moves_desc = Parser.extract_move_cond(moves_desc[1:])
                for src_pilename in src_pilenames:
                    for dst_pilename in dst_pilenames:
                        if auto:
                            game.define_auto_move(src_pilename, dst_pilename, cond)
                        else:
                            game.define_move(src_pilename, dst_pilename, cond)
            elif move_def[0] == 'MOVE_STACK':
                assert len(move_def) == 3, f"MOVE_STACK arguments missing or extra: {moves_desc[0]}"
                src_pilenames = Parser.parse_items(move_def[1], Parser.parse_str)
                dst_pilenames = Parser.parse_items(move_def[2], Parser.parse_str)
                cond, moves_desc = Parser.extract_move_stack_cond(moves_desc[1:])
                for src_pilename in src_pilenames:
                    for dst_pilename in dst_pilenames:
                        if auto:
                            game.define_auto_stack_move(src_pilename, dst_pilename, cond)
                        else:
                            game.define_stack_move(src_pilename, dst_pilename, cond)
            else:
                raise Exception(f"Cannot recognize move type of {move_def}")
    
    @staticmethod
    def extract_block(desc: list[str]) -> tuple[list[str], list[str]]:
        sub_desc = []
        for i in range(0, len(desc)):
            if desc[i].startswith('    '):
                sub_desc.append(desc[i][4:])
            else:
                break
        return sub_desc, desc[len(sub_desc):]

    @staticmethod
    def extract_move_cond(moves_desc: list[str]) -> tuple[cond.Condition[cond.MoveCardComponents], list[str]]:
        if moves_desc[0] in ['AND', 'OR']:
            ret: cond.ConditionTree[cond.MoveCardComponents] = \
                cond.AndSubTree() if moves_desc[0] == 'AND' else cond.OrSubTree()
            sub_desc, moves_desc = Parser.extract_block(moves_desc[1:])
            while len(sub_desc) > 0:
                subtree, sub_desc = Parser.extract_move_cond(sub_desc)
                ret.add_subtree(subtree)
            return ret, moves_desc
        else:
            return Parser.parse_move_condition(moves_desc[0]), moves_desc[1:]
        
    @staticmethod
    def extract_move_stack_cond(moves_desc: list[str]) -> tuple[cond.Condition[cond.MoveStackComponents], list[str]]:
        if moves_desc[0] in ['AND', 'OR']:
            ret: cond.ConditionTree[cond.MoveStackComponents] = \
                cond.AndSubTree() if moves_desc[0] == 'AND' else cond.OrSubTree()
            sub_desc, moves_desc = Parser.extract_block(moves_desc[1:])
            while len(sub_desc) > 0:
                subtree, sub_desc = Parser.extract_move_stack_cond(sub_desc)
                ret.add_subtree(subtree)
            return ret, moves_desc
        else:
            return Parser.parse_move_stack_condition(moves_desc[0]), moves_desc[1:]
        
    @staticmethod
    def parse_move_condition(s: str) -> cond.MoveCondition:
        parts = Parser.split_line(s)
        if parts[0] == 'DEST' and parts[1] == 'Empty':
            return cond.DestEmptyCondition()
        elif parts[0] == 'DEST' and parts[1] == 'Size':
            return cond.DestSizeCondition(cond.MathOp(parts[2]), Parser.parse_number(parts[3]))
        elif parts[0] == 'DESTSRC' and parts[1] == 'Suit':
            return cond.DestSrcSuitCondition(cond.MultiSuitCondition.MODE(parts[2]))
        elif parts[0] == 'DESTSRC' and parts[1] == 'Rank':
            return cond.DestSrcRankCondition(cond.MultiRankCondition.MODE(parts[2]))
        elif parts[0] == 'SRC' and parts[1] == 'Suit':
            return cond.SrcSuitCondition(Parser.parse_items(parts[2], Parser.parse_suit))
        elif parts[0] == 'SRC' and parts[1] == 'Rank':
            return cond.SrcRankCondition(Parser.parse_items(parts[2], Parser.parse_rank))
        else:
            raise Exception(f"Condition not recognized: {parts}")
        
    @staticmethod
    def parse_move_stack_condition(s: str) -> cond.MoveStackCondition|cond.MoveCondition:
        parts = Parser.split_line(s)
        if parts[0] == 'SRCSTACK' and parts[1] == 'Size':
            return cond.StackSizeCondition(cond.MathOp(parts[2]), Parser.parse_number(parts[3]))
        elif parts[0] == 'SRCSTACK' and parts[1] == 'Suit':
            return cond.StackSuitCondition(cond.MultiSuitCondition.MODE(parts[2]))
        elif parts[0] == 'SRCSTACK' and parts[1] == 'Rank':
            return cond.StackRankCondition(cond.MultiRankCondition.MODE(parts[2]))
        else:
            return Parser.parse_move_condition(s)
    
    @staticmethod
    def apply_auto(auto_desc: list[str], game: Game):
        Parser.apply_moves(auto_desc, game, True)

    @staticmethod
    def apply_win(deck_desc: list[str], game: Game):
        pass # TODO

    @staticmethod
    def parse(game_desc: str, seed: int|None = None) -> Game:
        game_desc = Parser.remove_comments(game_desc)
        lines = game_desc.splitlines()
        name = lines[0]
        game = Game(name)
        section_ind = [i for i in range(len(lines)) if '$' in lines[i]] + [len(lines)]
        sections = [lines[section_ind[i]:section_ind[i+1]] for i in range(len(section_ind)-1)]
        for section in sections:
            Parser.apply(section, game, seed)
        return game
    
    @staticmethod
    def parse_stack_position(s: str) -> StackPilePos:
        pilename, rest = s.split('[')
        ind = int(rest[:-1])
        return StackPilePos(pilename, ind)
    
    @staticmethod
    def parse_pile_position(s: str) -> PilePos:
        if s == 'DRAW':
            return DrawPilePos()
        return Parser.parse_stack_position(s)
    
    @staticmethod
    def prase_run_pos(s: str) -> RunPos:
        stack_str, ind_str = s.split(':')
        return RunPos(Parser.parse_stack_position(stack_str), Parser.parse_number(ind_str))

    @staticmethod
    def perform_action_in_game(s: str, game: Game) -> bool:
        parts = s.split()
        if parts[0] == 'draw':
            if hasattr(game, 'draw'):
                game.draw_func(True)
                return True
            return False
        elif parts[0] == 'move':
            return game.move(Parser.parse_pile_position(parts[1]), Parser.parse_stack_position(parts[2]))
        elif parts[0] == 'move_stack':
            return game.move_stack(Parser.prase_run_pos(parts[1]), Parser.parse_stack_position(parts[2]))
        else:
            print(f'[ignored] Action not recognized: {s}')
            return False

if __name__ == '__main__':
    with open('games/klondike.sgdl', 'r') as f:
    # with open('games/spider.sgdl', 'r') as f:
        game = Parser.parse(f.read(), 42)
    print("CONDITIONS")
    for move, condition in game.move_conditions.items():
        print(move)
        print(condition.summary())
    for move, condition in game.move_stack_conditions.items():
        print(move)
        print(condition.summary())

    print ("GAME START!")
    while not game.is_win():
        print(game.get_game_view())
        print(f"{len(game.get_possible_actions(False))} actions")
        valid_actions = game.get_possible_actions(True)
        print(f"{len(valid_actions)} valid actions:")
        valid_actions_str = [f"{move_func.__name__} {' '.join([str(value) for value in args.values()])}" for move_func, args in valid_actions]
        for i, valid_action_str in enumerate(valid_actions_str):
            print(f"{i}: {valid_action_str}")
        action: str = input()
        action_int = util.cast(action, int)
        if action_int is not None:
            action = valid_actions_str[action_int]
        print(Parser.perform_action_in_game(action, game))