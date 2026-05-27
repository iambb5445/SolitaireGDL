from game import Game, PilePos, StackPilePos, RunPos, DrawPilePos
from typing import TypeVar, List, Callable
from base import Deck, Suit, Card, Stack, SuitFullNames, suit_full_name_mapping, BaseStrEnum
import condition as cond

class Parser:
    @staticmethod
    def parse_str(s: str) -> str:
        return s
    
    @staticmethod
    def get_pilename_parser(pilenames: list[str]) -> Callable[[str], str]:
        def parse_pilename(s: str):
            assert s in pilenames, f"Pilename {s} is not among valid piles for this part: {pilenames}"
            return s
        return parse_pilename
    
    @staticmethod
    def get_enum_parser(enum: BaseStrEnum) -> Callable[[str], str]:
        def parse_enum(s: str):
            assert s in enum, f"Value {s} is not a valid name among: {[str(val) for val in enum]}"
            return s
        return parse_enum

    @staticmethod
    def parse_number(s: str) -> int:
        try:
            val = int(s)
            return val
        except Exception as e:
            raise Exception(f"Cannot parse value as a number: {s}")
    
    @staticmethod
    def parse_suit(s: str) -> Suit:
        for suit in SuitFullNames:
            if s == str(suit):
                return suit_full_name_mapping[suit]
        raise Exception(f"Suit not recognized: {s}")
    
    @staticmethod
    def parse_op(s: str) -> cond.MathOp: # alternatively use enum_parser
        if s in cond.MathOp:
            return cond.MathOp(s)
        raise Exception(f"Math operator not recognized: {s}")
    
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
    def get_deck_args(deck_desc: list[str]) -> tuple[int, list[Suit], list[int]|None]:
        assert len(deck_desc) == 1, "deck description not recognized [invalid line count]"
        # finds = re.findall(r"^\s*DECK\s+(\d+)\s+\{\s*([A-Za-z, ]+)\s*\}\s*$", deck_desc[1])
        # assert len(finds) == 1, "deck description does not match with the expected format"
        # count, suits_text = finds[0]
        parts = Parser.split_line(deck_desc[0])
        ranks = None
        if len(parts) == 4:
            ranks = Parser.parse_items(parts[-1], Parser.parse_rank)
            parts = parts[:-1]
        _, count_text, suits_text = parts
        count = Parser.parse_number(count_text)
        suits = Parser.parse_items(suits_text, Parser.parse_suit)
        return count, suits, ranks

    @staticmethod
    def apply_deck(deck_desc: list[str], game: Game, seed: int|None) -> None:
        count, suits, ranks = Parser.get_deck_args(deck_desc)
        game.deck = Deck(count, suits, ranks)
        game.deck.shuffle(seed)

    @staticmethod
    def get_pile_args(parts: list[str]) -> tuple[str, int, Stack.Face, list[Card]|None]:
        pilename = parts[0]
        count = Parser.parse_number(parts[1])
        face = Stack.Face.FACE_LAST # default value is here because it's a property of the gdl to have this for default, not a property of the game or base
        cards: list[Card]|None = None
        if len(parts) > 2 and parts[2] in Stack.Face:
            face = Parser.parse_pile_face(parts[2])
        if len(parts) > 2 and (parts[2] not in Stack.Face or len(parts) > 3):
            cards = Parser.parse_items(parts[-1], Parser.parse_card)
        return pilename, count, face, cards

    @staticmethod
    def get_deal_draw_args(parts: list[str], valid_pilenames: list[str]) -> tuple[int, set[str]]:
        count = Parser.parse_number(parts[1])
        targets = set(Parser.parse_items(parts[3], Parser.get_pilename_parser(valid_pilenames)))
        return count, targets
    
    @staticmethod
    def get_rotate_draw_args(parts: list[str]) -> tuple[int, int, int|None, int|None]:
        count = Parser.parse_number(parts[1])
        draw_count = Parser.parse_number(parts[3])
        view_count = Parser.parse_number(parts[4]) if parts[4] != 'U' else None
        max_redeals = Parser.parse_number(parts[5]) if parts[5] != 'U' else None
        return count, draw_count, view_count, max_redeals

    @staticmethod
    def apply_initial(initial_desc: list[str], game: Game):
        draw_def_line: list[str]|None = None
        for initial in initial_desc:
            parts = Parser.split_line(initial)
            if parts[0] == 'DRAW':
                draw_def_line = parts
            else:
                pilename, count, face, cards = Parser.get_pile_args(parts)
                game.define_pile(pilename, count, face, cards)
        if draw_def_line is not None:
            if draw_def_line[2] == 'DEAL':
                count, targets = Parser.get_deal_draw_args(draw_def_line, list(game.name_to_piles.keys()))
                game.define_deal_draw(count, targets)
            elif draw_def_line[2] == 'ROTATE':
                count, draw_count, view_count, max_redeals = Parser.get_rotate_draw_args(draw_def_line)
                game.define_rotate_draw(count, draw_count, view_count, max_redeals)

    @staticmethod
    def get_move_args(move_def: list[str], valid_pilenames: list[str], accept_draw_src: bool) -> tuple[list[str], list[str]]:
        valid_src_pilenames = valid_pilenames + (['DRAW'] if accept_draw_src else [])
        src_pilenames = Parser.parse_items(move_def[1], Parser.get_pilename_parser(valid_src_pilenames))
        dst_pilenames = Parser.parse_items(move_def[2], Parser.get_pilename_parser(valid_pilenames))
        return src_pilenames, dst_pilenames

    @staticmethod
    def apply_moves(moves_desc: list[str], game: Game, auto: bool = False):
        pilenames = list(game.name_to_piles.keys())
        while len(moves_desc) > 0:
            move_def = Parser.split_line(moves_desc[0])
            if move_def[0] == 'MOVE':
                assert len(move_def) == 3, f"MOVE arguments missing or extra: {moves_desc[0]}"
                src_pilenames, dst_pilenames = Parser.get_move_args(move_def, pilenames, game.has_rotate_draw_pile())
                cond, moves_desc = Parser.extract_move_cond(moves_desc[1:])
                for src_pilename in src_pilenames:
                    for dst_pilename in dst_pilenames:
                        if auto:
                            game.define_auto_move(src_pilename, dst_pilename, cond)
                        else:
                            game.define_move(src_pilename, dst_pilename, cond)
            elif move_def[0] == 'MOVE_STACK':
                assert len(move_def) == 3, f"MOVE_STACK arguments missing or extra: {moves_desc[0]}"
                src_pilenames, dst_pilenames = Parser.get_move_args(move_def, pilenames, False)
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
            return cond.DestSizeCondition(Parser.parse_op(parts[2]), Parser.parse_number(parts[3]))
        elif parts[0] == 'DEST' and parts[1] == 'Suit':
            return cond.DestSuitCondition(Parser.parse_items(parts[2], Parser.parse_suit))
        elif parts[0] == 'DEST' and parts[1] == 'Rank':
            return cond.DestRankCondition(Parser.parse_items(parts[2], Parser.parse_rank))
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
            return cond.StackSizeCondition(Parser.parse_op(parts[2]), Parser.parse_number(parts[3]))
        elif parts[0] == 'SRCSTACK' and parts[1] == 'Suit':
            return cond.StackSuitCondition(cond.MultiSuitCondition.MODE(parts[2]))
        elif parts[0] == 'SRCSTACK' and parts[1] == 'Rank':
            return cond.StackRankCondition(cond.MultiRankCondition.MODE(parts[2]))
        else:
            return Parser.parse_move_condition(s)
        
    @staticmethod
    def parse_general_condition(s: str, game: Game) -> cond.GeneralCondition:
        all_pilenames = list(game.name_to_piles.keys())
        if game.draw_pile is not None:
            all_pilenames += ["DRAW"]
        parts = Parser.split_line(s)
        if parts[0] == 'PILE':
            assert parts[1] in cond.PileCondition.MODE, f"Unrecognized PileCondition MODE: {parts[1]}"
            mode: cond.PileCondition.MODE = cond.PileCondition.MODE(parts[1])
            pilenames: list[str] = Parser.parse_items(parts[2], Parser.get_pilename_parser(all_pilenames))
            if parts[3] == 'Empty':
                return cond.PileEmptyCondition(pilenames, mode)
            elif parts[3] == 'Size':
                return cond.PileSizeCondition(pilenames, mode, Parser.parse_op(parts[4]), Parser.parse_number(parts[5]))
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
    def get_name(game_desc: str) -> str:
        return Parser.split_parts(game_desc)[0]
    
    @staticmethod
    def split_parts(game_desc) -> tuple[str, list[list[str]]]:
        game_desc = Parser.remove_comments(game_desc)
        lines = game_desc.splitlines()
        name = lines[0]
        section_ind = [i for i in range(len(lines)) if '$' in lines[i]] + [len(lines)]
        sections = [lines[section_ind[i]:section_ind[i+1]] for i in range(len(section_ind)-1)]
        return name, sections

    @staticmethod
    def parse(game_desc: str, seed: int|None, should_log: bool, should_start: bool) -> Game:
        name, sections = Parser.split_parts(game_desc)
        game = Game(name, should_log)
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
        
    @staticmethod
    def get_cards_of_action_in_game(s: str, game: Game) -> list[Card]:
        from game import MoveArgs, MoveStackArgs
        parts = s.split()
        if parts[0] == 'draw':
            return []
        elif parts[0] == 'move':
            args = MoveArgs.from_pos(game, Parser.parse_pile_position(parts[1]), Parser.parse_stack_position(parts[2]), False)
            return [args.src_pile.peak()]
        elif parts[0] == 'move_stack':
            src_pos = Parser.prase_run_pos(parts[1])
            args = MoveStackArgs.from_pos(game, src_pos, Parser.parse_stack_position(parts[2]), False)
            return args.src_pile.get_many(src_pos.from_ind)
        else:
            raise Exception(f"Action not recognized: {s}")
        
    @staticmethod
    def get_piles_of_action_in_game(s: str) -> list[str]:
        parts = s.split()
        if parts[0] == 'draw':
            return [DrawPilePos().__str__()] # technically draw targets are also used, but it's fine not to count them
        elif parts[0] == 'move':
            return [parts[1], parts[2]] # I can convert these to stackpilepos and back to string, but it would be the same
        elif parts[0] == 'move_stack':
            stack_str, ind_str = parts[1].split(':')
            return [stack_str, parts[2]]
        else:
            raise Exception(f"Action not recognized: {s}")
        
    @staticmethod
    def get_action_summary(s: str, game: Game, all_resolutions: bool = True, explain: bool = True) -> str:
        parts = s.split()
        if parts[0] == 'draw':
            return game.get_draw_summary(all_resolutions, explain)
        elif parts[0] == 'move':
            return game.get_move_summary(all_resolutions, explain, Parser.parse_pile_position(parts[1]), Parser.parse_stack_position(parts[2]))
        elif parts[0] == 'move_stack':
            return game.get_move_stack_summary(all_resolutions, explain, Parser.prase_run_pos(parts[1]), Parser.parse_stack_position(parts[2]))
        else:
            raise Exception(f"Action not recognized: {s}")