from parser import Parser
from genetic import DeckGene, SetupGene, DealDrawDefGene, RotateDrawDefGene, PileDefGene,\
    MovesGene, MoveGene, MoveStackGene, DrawMoveGene, ConditionGene, WinGene, SGDLGene
from base import Stack, Card
from typing import Callable
import condition as cond

class GeneParser:
    @staticmethod
    def get_setup_gene(initial_desc: list[str]) -> SetupGene:
        draw_gene = None
        draw_def_line: list[str]|None = None
        pile_args: dict[str, list[tuple[int, Stack.Face, list[Card]|None]]] = {}
        for initial in initial_desc:
            parts = Parser.split_line(initial)
            if parts[0] == 'DRAW':
                assert draw_def_line is None, f"Cannot define multiple draw piles: {draw_def_line} {parts}"
                draw_def_line = parts
            else:
                pilename, count, face, cards = Parser.get_pile_args(parts)
                assert cards is None, "initial card positions is not supported for genes yet" # TODO
                pile_args[pilename] = pile_args.get(pilename, []) + [(count, face, cards)]
        pile_genes = [PileDefGene(pilename,
                                  [count for count, face, cards in args],
                                  [face for count, face, cards in args])
                                  for pilename, args in pile_args.items()]
        if draw_def_line is not None:
            pilenames = list(pile_args.keys())
            if draw_def_line[2] == 'DEAL':
                count, targets = Parser.get_deal_draw_args(draw_def_line, pilenames)
                draw_gene = DealDrawDefGene(count, list(targets), SetupGene(None, pile_genes))
            elif draw_def_line[2] == 'ROTATE':
                count, draw_count, view_count, max_redeals = Parser.get_rotate_draw_args(draw_def_line)
                draw_gene = RotateDrawDefGene(count, draw_count, view_count if view_count is not None else 'U', max_redeals if max_redeals is not None else 'U')
        
        return SetupGene(draw_gene, pile_genes)
    
    @staticmethod
    def get_deck_gene(deck_desc: list[str]) -> DeckGene:
        count, suits, ranks = Parser.get_deck_args(deck_desc)
        ranks = [str(rank) for rank in ranks] if ranks is not None else None
        suits = [Parser.suit_to_full_name(suit) for suit in suits]
        return DeckGene(count, suits, ranks)
    
    @staticmethod
    def get_moves_gene(moves_desc: list[str], auto: bool, setup: SetupGene) -> MovesGene:
        moves: list[MoveGene] = []
        move_stacks: list[MoveStackGene] = []
        draw_move: DrawMoveGene|None = None
        pilenames = setup.get_pilenames(False, False)
        has_rotate_draw = isinstance(setup.draw, RotateDrawDefGene)
        while len(moves_desc) > 0:
            move_def = Parser.split_line(moves_desc[0])
            if move_def[0] == 'MOVE':
                assert len(move_def) == 3, f"MOVE arguments missing or extra: {moves_desc[0]}"
                src_pilenames, dst_pilenames = Parser.get_move_args(move_def, pilenames, has_rotate_draw)
                cond, moves_desc = GeneParser.extract_cond(moves_desc[1:], setup, ConditionGene.CondType.MOVE)
                assert auto == False, "Auto moves not supported for genes yet" # TODO
                moves.append(MoveGene(src_pilenames, dst_pilenames, cond, setup))
            elif move_def[0] == 'MOVE_STACK':
                assert len(move_def) == 3, f"MOVE_STACK arguments missing or extra: {moves_desc[0]}"
                src_pilenames, dst_pilenames = Parser.get_move_args(move_def, pilenames, False)
                cond, moves_desc = GeneParser.extract_cond(moves_desc[1:], setup, ConditionGene.CondType.MOVE_STACK)
                assert auto == False, "Auto moves not supported for genes yet" # TODO
                move_stacks.append(MoveStackGene(src_pilenames, dst_pilenames, cond, setup))
            elif move_def[0] == 'DRAW':
                assert len(move_def) == 1, f"DRAW argument extra: {moves_desc[0]}"
                cond, moves_desc = GeneParser.extract_cond(moves_desc[1:], setup, ConditionGene.CondType.GLOBAL)
                draw_move = DrawMoveGene(cond, setup)
            else:
                raise Exception(f"Cannot recognize move type of {move_def}")
        return MovesGene(moves, move_stacks, draw_move, setup)

    @staticmethod
    def get_win_gene(win_desc: list[str], setup: SetupGene) -> WinGene:
        cond, win_desc = GeneParser.extract_cond(win_desc, setup, ConditionGene.CondType.WIN)
        assert len(win_desc) == 0, f"Extra lines remained after extracting win conditions: {win_desc}"
        return WinGene(cond, setup)
    
    @staticmethod
    def make_base_condition(base: str, parts: list[str], setup: SetupGene, cond_type: ConditionGene.CondType):
        mapping: dict[str, Callable[[str], tuple[ConditionGene.Arg, bool]]] = {
            "<op>": lambda s: (ConditionGene.Op(s), isinstance(str(Parser.parse_op(s)), str)),
            "<count>": lambda s: (ConditionGene.Count(s), isinstance(Parser.parse_number(s), int)),
            "<suits>": lambda s: (ConditionGene.Suits(s), isinstance(Parser.parse_items(s, Parser.parse_suit), list)),
            "<ranks>": lambda s: (ConditionGene.Ranks(s), isinstance(Parser.parse_items(s, Parser.parse_rank), list)),
            "<pileset>": lambda s: (ConditionGene.Pileset(s, setup), len(Parser.parse_items(s, Parser.get_pilename_parser(setup.get_pilenames(False, True)))) > 0),
            "<rankcond>": lambda s: (ConditionGene.RankCond(s), s in cond.MultiRankCondition.MODE),
            "<suitcond>": lambda s: (ConditionGene.SuitCond(s), s in cond.MultiSuitCondition.MODE),
        }
        arg_positions: list[tuple[int, str]] = []
        for arg_keyword in mapping.keys():
            ind = base.find(arg_keyword)
            if ind >= 0:
                arg_positions.append((ind, arg_keyword))
        arg_positions.sort()
        part_index = 0
        condition_args: list[tuple[ConditionGene.Arg, int, int]] = []
        for ind, arg_keyword in arg_positions:
            arg, valid = mapping[arg_keyword](parts[part_index])
            if not valid:
                raise Exception(f"Invalid arg {parts[part_index]} is attempting to replace {arg_keyword} in condition {base}")
            condition_args.append((arg, ind, ind+len(arg_keyword)))
            part_index += 1
        return ConditionGene(base, condition_args, [], cond_type, setup)

    
    @staticmethod
    def parse_move_condition(s: str, setup: SetupGene) -> ConditionGene:
        parts = Parser.split_line(s)
        if parts[0] == 'DEST' and parts[1] == 'Empty':
            base = "DEST Empty"
        elif parts[0] == 'DEST' and parts[1] == 'Size':
            base = "DEST Size <op> <count>"
        elif parts[0] == 'DEST' and parts[1] == 'Suit':
            base = "DEST Suit <suits>"
        elif parts[0] == 'DEST' and parts[1] == 'Rank':
            base = "DEST Rank <ranks>"
        elif parts[0] == 'DESTSRC' and parts[1] == 'Suit':
            base = "DESTSRC Suit <suitcond>"
        elif parts[0] == 'DESTSRC' and parts[1] == 'Rank':
            base = "DESTSRC Rank <rankcond>"
        elif parts[0] == 'SRC' and parts[1] == 'Suit':
            base = "SRC Suit <suits>"
        elif parts[0] == 'SRC' and parts[1] == 'Rank':
            base = "SRC Rank <ranks>"
        else:
            raise Exception(f"Condition not recognized: {parts}")
        return GeneParser.make_base_condition(base, parts[2:], setup, ConditionGene.CondType.MOVE)
    
    @staticmethod
    def parse_move_stack_condition(s: str, setup: SetupGene) -> ConditionGene:
        parts = Parser.split_line(s)
        if parts[0] == 'SRCSTACK' and parts[1] == 'Size':
            base = "SRCSTACK Size <op> <count>"
        elif parts[0] == 'SRCSTACK' and parts[1] == 'Suit':
            base = "SRCSTACK Suit <suitcond>"
        elif parts[0] == 'SRCSTACK' and parts[1] == 'Rank':
            base = "SRCSTACK Rank <rankcond>"
        else:
            return GeneParser.parse_move_condition(s, setup)
        return GeneParser.make_base_condition(base, parts[2:], setup, ConditionGene.CondType.MOVE_STACK)

    @staticmethod
    def parse_general_condition(s: str, setup: SetupGene, is_win_cond: bool) -> ConditionGene:
        # for now there is no difference between parsing global and win, just the type
        cond_type = ConditionGene.CondType.GLOBAL if not is_win_cond else ConditionGene.CondType.WIN
        # TODO move this out
        # TODO fix in .get_random
        parts = Parser.split_line(s)
        if parts[0] == 'PILE':
            assert parts[1] in cond.PileCondition.MODE, f"Unrecognized PileCondition MODE: {parts[1]}"
            mode: cond.PileCondition.MODE = cond.PileCondition.MODE(parts[1])
            arg_parts = [parts[2]] + parts[4:]
            if parts[3] == 'Empty':
                return GeneParser.make_base_condition(f"PILE {mode} <pileset> Empty", arg_parts, setup, cond_type)
            elif parts[3] == 'Size':
                return GeneParser.make_base_condition(f"PILE {mode} <pileset> Size <op> <count>", arg_parts, setup, cond_type)
            else:
                raise Exception(f"Pile Condition not recognized: {parts}")
        else:
            raise Exception(f"Condition not recognized: {parts}")
        
    @staticmethod
    def extract_cond(moves_desc: list[str], setup: SetupGene, type: ConditionGene.CondType) -> tuple[ConditionGene, list[str]]:
        if moves_desc[0] in ['AND', 'OR']:
            root = moves_desc[0]
            sub_desc, moves_desc = Parser.extract_block(moves_desc[1:])
            subtrees: list[ConditionGene] = []
            while len(sub_desc) > 0:
                subtree, sub_desc = GeneParser.extract_cond(sub_desc, setup, type)
                subtrees.append(subtree)
            return ConditionGene(root, [], subtrees, type, setup), moves_desc
        else:
            if type == ConditionGene.CondType.GLOBAL:
                return GeneParser.parse_general_condition(moves_desc[0], setup, False), moves_desc[1:]
            elif type == ConditionGene.CondType.WIN:
                return GeneParser.parse_general_condition(moves_desc[0], setup, True), moves_desc[1:]
            elif type == ConditionGene.CondType.MOVE:
                return GeneParser.parse_move_condition(moves_desc[0], setup), moves_desc[1:]
            elif type == ConditionGene.CondType.MOVE_STACK:
                return GeneParser.parse_move_stack_condition(moves_desc[0], setup), moves_desc[1:]
            raise Exception(f"Condition type not recognized: {type}")

    @staticmethod
    def parse(game_desc: str):
        name, sections = Parser.split_parts(game_desc)
        section_dict: dict[str, list[str]] = dict([(section[0], section[1:]) for section in sections])
        assert '$cards' in section_dict, "$\'cards\' section is missing"
        deck_gene = GeneParser.get_deck_gene(section_dict['$cards'])
        assert '$initial' in section_dict, "$\'initial\' section is missing"
        setup_gene = GeneParser.get_setup_gene(section_dict['$initial'])
        assert '$moves' in section_dict, "$\'moves\' section is missing"
        moves_gene = GeneParser.get_moves_gene(section_dict['$moves'], False, setup_gene)
        if '$auto' in section_dict: # not supported yet
            moves_gene = GeneParser.get_moves_gene(section_dict['$moves'], True, setup_gene)
        assert '$win' in section_dict, "$\'win\' section is missing"
        win_gene = GeneParser.get_win_gene(section_dict['$win'], setup_gene)
        for section_title in section_dict.keys():
            if section_title not in ['$cards', '$initial','$moves', '$auto', '$win']:
                raise Exception(f"Invalid section title: {section_title}")
        return SGDLGene(deck_gene, setup_gene, moves_gene, win_gene)

    @staticmethod
    def from_file(filename: str) -> SGDLGene:
        with open(filename, 'r') as f:
            game = GeneParser.parse(f.read())
        return game

if __name__ == '__main__':
    import sys
    import argparse
    from random import Random
    from simulate_many import get_seed
    parser = argparse.ArgumentParser()
    parser.add_argument('in_filename', type=str, help="Name of the input file to be mutated.")
    # parser.add_argument('out_filename', type=str, help="Name of the file to save the mutated SGDL.")
    parser.add_argument('--seed', type=int, default=None, help="Integer seed to be used for the mutation.")
    args = parser.parse_args(sys.argv[1:])
    in_filename = args.in_filename
    # out_filename = args.out_filename
    seed: int = args.seed
    if seed is None:
        seed = get_seed(None)
    gene = GeneParser.from_file(in_filename)
    print("Input SGDL:")
    print(gene.get_gdl())
    print(f"Output SGDL (seed={seed})")
    gene = gene.mutate(Random(seed))
    print(gene.get_gdl())