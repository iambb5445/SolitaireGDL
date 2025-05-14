from game import Game, PilePos, StackPilePos, RunPos, DrawPilePos
from typing import TypeVar, List, Callable
from base import Deck, Suit, Card, Stack
import condition as cond

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
    
    T = TypeVar('T')
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
                if len(parts) > 2 and (parts[2] not in Stack.Face or len(parts) > 3):
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
            elif move_def[0] == 'DRAW':
                assert len(move_def) == 1, f"DRAW argument extra: {moves_desc[0]}"
                cond, moves_desc = Parser.extract_general_cond(moves_desc[1:], game)
                game.define_draw_cond(cond)
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
    def extract_general_cond(moves_desc: list[str], game: Game) -> tuple[cond.Condition[cond.GeneralConditionComponents], list[str]]:
        if moves_desc[0] in ['AND', 'OR']:
            ret: cond.ConditionTree[cond.GeneralConditionComponents] = \
                cond.AndSubTree() if moves_desc[0] == 'AND' else cond.OrSubTree()
            sub_desc, moves_desc = Parser.extract_block(moves_desc[1:])
            while len(sub_desc) > 0:
                subtree, sub_desc = Parser.extract_general_cond(sub_desc, game)
                ret.add_subtree(subtree)
            return ret, moves_desc
        else:
            return Parser.parse_general_condition(moves_desc[0], game), moves_desc[1:]
        
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
    def parse_general_condition(s: str, game: Game) -> cond.GeneralCondition:
        parts = Parser.split_line(s)
        if parts[0] == 'PILE':
            assert parts[1] in cond.PileCondition.MODE, f"Unrecognized PileCondition MODE: {parts[1]}"
            mode: cond.PileCondition.MODE = cond.PileCondition.MODE(parts[1])
            pilenames: list[str] = Parser.parse_items(parts[2], Parser.parse_str)
            for pilename in pilenames:
                if pilename == 'DRAW':
                    assert game.draw_pile is not None, "Cannot define pile condition on non-existent draw pile"
                else:
                    assert pilename in game.name_to_piles.keys(), f"Cannot define pile conditions on non_existent pile {pilename}"
            if parts[3] == 'Empty':
                return cond.PileEmptyCondition(pilenames, mode)
            elif parts[3] == 'Size':
                return cond.PileSizeCondition(pilenames, mode, cond.MathOp(parts[4]), Parser.parse_number(parts[5]))
            else:
                raise Exception(f"Pile Condition not recognized: {parts}")
        else:
            raise Exception(f"Condition not recognized: {parts}")
    
    @staticmethod
    def apply_auto(auto_desc: list[str], game: Game):
        Parser.apply_moves(auto_desc, game, True)

    @staticmethod
    def apply_win(win_desc: list[str], game: Game):
        cond, win_desc = Parser.extract_general_cond(win_desc, game)
        assert len(win_desc) == 0, f"Extra lines remained after extracting win conditions: {win_desc}"
        game.define_win_cond(cond)

    @staticmethod
    def parse(game_desc: str, seed: int|None, should_log: bool, should_start: bool) -> Game:
        game_desc = Parser.remove_comments(game_desc)
        lines = game_desc.splitlines()
        name = lines[0]
        game = Game(name, should_log)
        section_ind = [i for i in range(len(lines)) if '$' in lines[i]] + [len(lines)]
        sections = [lines[section_ind[i]:section_ind[i+1]] for i in range(len(section_ind)-1)]
        for section in sections:
            Parser.apply(section, game, seed)
        if should_start:
            game.start()
        return game
    
    @staticmethod
    def from_file(filename: str, seed: int|None, should_log: bool, should_start: bool) -> Game:
        with open(filename, 'r') as f:
            game = Parser.parse(f.read(), seed, should_log, should_start)
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
    def perform_action_in_game(s: str, game: Game, perform: bool = True) -> bool:
        parts = s.split()
        if parts[0] == 'draw':
            return game.draw(perform)
        elif parts[0] == 'move':
            return game.move(Parser.parse_pile_position(parts[1]), Parser.parse_stack_position(parts[2]), perform)
        elif parts[0] == 'move_stack':
            return game.move_stack(Parser.prase_run_pos(parts[1]), Parser.parse_stack_position(parts[2]), perform)
        else:
            raise Exception(f"Action not recognized: {s}")