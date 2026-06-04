from __future__ import annotations
from parser import Parser
from random import Random
from enum import Enum
from base import Stack
from base import SuitFullNames as SFN
from abc import ABC, abstractmethod
from typing import Sequence, Callable, TypeVar, cast
from evaluate_gdl import Verdict, evaluate_gdl
import condition as cond
from utility import get_seed, get_uniques

def coin_flip(rnd: Random, faces: int = 2) -> bool:
    return rnd.randint(0, faces - 1) == 0

def uniform(values: list[float]|list[int]) -> list[float]:
    total = sum(values)
    return [value/total for value in values]

class Params:
    MAX_CARD_COUNT = 8 * 13
    MAX_CARD_IN_PILE = 10
    MAX_PILE_REPEAT_COUNT = 10
    MAX_MOVE_COUNT = 2
    MAX_MOVE_STACK_COUNT = 2
    MAX_TRIES = 10
    MAX_CARD_IN_COND = 10
    MAX_COND_DEPTH = 2 #0-based
    CROSSOVER_MAX_COND_DEPTH = 2
    MAX_GLOBAL_COND_DEPTH = 0 #0-based
    MAX_COND_BRANCH = 2
    CROSSOVER_MAX_COND_BRANCH = 3
    SPECIAL_PILENAMES = ["COLUMN"]
    MAX_FACE_TYPE_PER_PILE = 2
    SIMPLE_CONDITION = True # should we prevent and of ands, or of ors
    class RanksArgType(Enum):
        KingAceOnly = 1
        SingleOnly = 2
        Any = 3
    RANKS_ARG_TYPE = RanksArgType.KingAceOnly
    WIN_COND_ALL_EMPTY_ONLY = True # win condition can only be ALL <PILE_TYPE> Empty
    GLOBAL_PILE_SIZE_GT0_ONLY = True # any pile size condition can only be > 0
    DUPLICATE_MOVE_ENDS_ALLOWED = False
    

class MaxTriesReachedException(Exception):
    pass

class MutationUnavailableException(Exception):
    pass

class CrossoverUnavailableException(Exception):
    pass

class InvalidMoveCreationDueToEndPointExclusion(Exception):
    pass

G = TypeVar('G', bound='GenoType')

class GenoType(ABC):
    @abstractmethod
    def get_gdl(self) -> str:
        raise NotImplementedError
    
    @staticmethod
    def list_to_gdl(l: list[int]|list[str]) -> str:
        if len(l) <= 1:
            return str(l[0])
        return "{" + ", ".join([str(e) for e in l]) + "}"
    
    @staticmethod
    @abstractmethod
    def get_random(rnd: Random) -> GenoType:
        raise NotImplementedError
    
    @abstractmethod
    def copy(self: G) -> G:
        raise NotImplementedError
    
    def mutate(self: G, rnd: Random) -> G:
        mutation_options = self.__class__._get_mutation_options()
        if len(mutation_options) == 0:
            raise MutationUnavailableException(str(self.__class__) + self.get_gdl())
        return rnd.choice(mutation_options)(self.copy(), rnd)

    def mutate_until_change(self: G, rnd: Random, max_tries: int=50) -> tuple[G, int]:
        my_gdl = self.get_gdl()
        for _ in range(max_tries):
            seed = get_seed(rnd)
            mutated = self.mutate(Random(seed))
            if mutated.get_gdl() != my_gdl:
                return mutated, seed
        raise Exception(f"Mutation failed: mutation resulted in the same gdl for {max_tries} tries")
    
    @staticmethod
    @abstractmethod
    # assumes input is already a copy or rvalue
    # the output may be same as the input (no validation)
    def _get_mutation_options() -> list[Callable[[G, Random], G]]:
        raise NotImplementedError
    
    def crossover(self: G, other: G, rnd: Random, double_sided: bool) -> G:
        crossover_options = self.__class__._get_crossover_options()
        if len(crossover_options) == 0:
            raise CrossoverUnavailableException(str(self.__class__) + self.get_gdl())
        c_option = rnd.choice(crossover_options)
        if double_sided and coin_flip(rnd):
            return c_option(other.copy(), self.copy(), rnd) # some crossovers favor self over other
        return c_option(self.copy(), other.copy(), rnd)
    
    @staticmethod
    @abstractmethod
    # assumes input is already a copy or rvalue
    # the output may be same as one of the inputs (no validation)
    def _get_crossover_options() -> list[Callable[[G, G, Random], G]]:
        raise NotImplementedError
    
    @staticmethod
    def get_rnd(rnd: Random) -> Random:
        return Random(get_seed(rnd, 1000000000))
    
    @staticmethod
    def get_random_name(rnd: Random):
        import string
        vowels = [v for v in "aeiou"]
        consonants = [s for s in string.ascii_lowercase if s not in vowels]
        vclusters = vowels + ["ae", "ou", "ea", "ai", "io", "ui"]
        cclusters = consonants + ["br", "cr", "dr", "gr", "pr", "fr", "st", "tr"]
        pattern: list[list[str]] = rnd.choice([
            [vowels, consonants, vowels],
            [vowels, consonants, vclusters, consonants],
            [cclusters, vclusters, consonants],
            [cclusters, vclusters, consonants, vowels],
            [cclusters, vclusters, consonants, vowels, consonants],
        ])
        return ''.join([rnd.choice(l) for l in pattern])
    
    @staticmethod
    def get_random_numbers(rnd: Random, intended_sum: int, count: int, try_positive: bool) -> list[int]:
        if try_positive and count >= intended_sum:
            brs = [0] + sorted(rnd.sample(range(1, intended_sum), count - 1)) + [intended_sum]
        else:
            brs = [0] + sorted(rnd.choices(range(0, intended_sum + 1), k=count - 1)) + [intended_sum]
        return [(brs[i + 1] - brs[i]) for i in range(count)]
    

RG = TypeVar('RG', bound='Reducible')

class Reducible(ABC):
    @abstractmethod
    def get_reduced(self: RG, rnd: Random|None, iter: int) -> RG | None:
        raise NotImplementedError

class DeckGene(GenoType):
    def __init__(self, count: int, suits: list[str], ranks: list[str]|None):
        self.count = count
        self.suits = suits
        self.ranks = ranks
        suit_count = len(suits)
        rank_count = 13 if ranks is None else len(ranks)
        self.card_count = count * suit_count * rank_count
    
    def get_gdl(self) -> str:
        suits_str = self.list_to_gdl(self.suits)
        ransk_str = "" if self.ranks is None else (" " + self.list_to_gdl(self.ranks))
        return f"$cards\nDECK {self.count} {suits_str}{ransk_str}\n\n"

    @staticmethod
    def get_random(rnd: Random) -> DeckGene:
        # count = rnd.choices([1, 2, 4, 8], [24, 6, 1, 1])
        # suits = rnd.choices(["SPADES", "{SPADES, HEARTS}", "{SPADES, HEARTS, CLUBS, DIAMONDS}"], [2, 3, 27])
        # ranks = rnd.choices(["", "{6, 7, 8, 9, 10, J, Q, K}"], [31, 1])
        # EXCLUDED: custom ranks, weird suits
        for _ in range(Params.MAX_TRIES):
            count = rnd.choice([1, 2, 4, 8])
            suits = [str(suit) for suit in rnd.choice([
                [SFN.SPADES], [SFN.SPADES, SFN.HEARTS], [SFN.SPADES, SFN.CLUBS],
                list(SFN)
            ])]
            deck = DeckGene(count, suits, None)
            if deck.card_count <= Params.MAX_CARD_COUNT:
                return deck
        raise MaxTriesReachedException

    def copy(self) -> DeckGene:
        return DeckGene(self.count, [suit for suit in self.suits], self.ranks if self.ranks is None else [rank for rank in self.ranks])
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[DeckGene, DeckGene, Random], DeckGene]]:
        return [
            lambda me, other, rnd: DeckGene(other.count, me.suits, me.ranks),
            lambda me, other, rnd: DeckGene(me.count, other.suits, me.ranks),
            lambda me, other, rnd: DeckGene(me.count, me.suits, other.ranks),
        ]

    @staticmethod
    def _get_mutation_options() -> list[Callable[[DeckGene, Random], DeckGene]]:
        return [
            lambda me, rnd, c=c_option: c(me, DeckGene.get_random(rnd), rnd)
            for c_option in DeckGene._get_crossover_options()
        ]

class DealDrawDefGene(GenoType):
    def __init__(self, card_count: int, draw_to: list[str], setup: SetupGene) -> None:
        self.card_count = card_count
        self.draw_to = draw_to
        self.setup = setup
    
    def get_gdl(self) -> str:
        return f"DRAW {self.card_count} DEAL {GenoType.list_to_gdl(self.draw_to)}\n"
    
    @staticmethod
    def get_random(rnd: Random, card_count: int = 0, setup: SetupGene|None = None) -> DealDrawDefGene:
        assert setup is not None
        draw_to_options = setup.get_pilenames(False, False)
        draw_to = [name for name in rnd.sample(draw_to_options, k=rnd.randint(1, len(draw_to_options)))] # I could instead mark each option as in or out
        return DealDrawDefGene(card_count, draw_to, setup)

    def copy(self) -> DealDrawDefGene:
        return DealDrawDefGene(self.card_count, [pile for pile in self.draw_to], self.setup)
    
    def set_setup(self, setup: SetupGene) -> None:
        self.setup = setup

    @staticmethod
    def _get_crossover_options() -> list[Callable[[DealDrawDefGene, DealDrawDefGene, Random], DealDrawDefGene]]:
        return [
            # lambda me, other, rnd: DealDrawDefGene((other.card_count if other.card_count <= me.setup.card_count else me.card_count), me.draw_to, me.setup),
            lambda me, other, rnd: DealDrawDefGene(other.card_count, me.draw_to, me.setup), # card counts will be adjusted from setup
            lambda me, other, rnd: DealDrawDefGene(me.card_count, (other.draw_to if set(other.draw_to).issubset(set(me.setup.get_pilenames(False, False))) else me.draw_to), me.setup),
        ]

    @staticmethod
    def _get_mutation_options() -> list[Callable[[DealDrawDefGene, Random], DealDrawDefGene]]:
        return [
            lambda me, rnd, c=c_option: c(me, DealDrawDefGene.get_random(rnd, me.card_count, me.setup), rnd)
            for c_option in DealDrawDefGene._get_crossover_options()
        ]
    
    def _transform_pilenames_(self, rnd: Random, new_setup: SetupGene):
        mapping: dict[str, str] = self.setup.get_pilename_mapping(rnd, new_setup, False, False)
        self.draw_to = get_uniques([mapping[p] for p in self.draw_to])
        return self


class RotateDrawDefGene(GenoType):
    def __init__(self, card_count: int, draw_count: int, display_count: int|str, redeal_count: int|str) -> None:
        self.card_count = card_count
        self.draw_count = draw_count
        self.display_count = display_count
        self.redeal_count = redeal_count

    def get_gdl(self) -> str:
        return f"DRAW {self.card_count} ROTATE {self.draw_count} {self.display_count} {self.redeal_count}\n"
    
    @staticmethod
    def get_random(rnd: Random, card_count: int = 0) -> RotateDrawDefGene:
        # EXCLUCDED: any draw of not 1 or 3 at a time, display/redeal bigger than 3 except for U
        draw_count = rnd.choice([1, 3])
        display_count = rnd.choice([str(val) for val in range(draw_count, 3)] + ["U"])
        redeal_count = rnd.choice([1, 2, 3, "U"])
        if display_count != "U" and redeal_count != "U":
            if coin_flip(rnd):
                display_count = "U"
            else:
                redeal_count = "U"
        return RotateDrawDefGene(card_count, draw_count, display_count, redeal_count)
    
    def copy(self) -> RotateDrawDefGene:
        return RotateDrawDefGene(self.card_count, self.draw_count, self.display_count, self.redeal_count)
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[RotateDrawDefGene, RotateDrawDefGene, Random], RotateDrawDefGene]]:
        return [
            lambda me, other, rnd: RotateDrawDefGene(other.card_count, me.draw_count, me.display_count, me.redeal_count), # counts will be adjusted from setup
            lambda me, other, rnd: RotateDrawDefGene(me.card_count, other.draw_count, me.display_count, me.redeal_count),
            lambda me, other, rnd: RotateDrawDefGene(me.card_count, me.draw_count, other.display_count, me.redeal_count),
            lambda me, other, rnd: RotateDrawDefGene(me.card_count, me.draw_count, me.display_count, other.redeal_count),
        ]
    
    @staticmethod
    def _get_mutation_options() -> list[Callable[[RotateDrawDefGene, Random], RotateDrawDefGene]]:
        return [
            lambda me, rnd, c=c_option: c(me, RotateDrawDefGene.get_random(rnd, me.card_count), rnd)
            for c_option in RotateDrawDefGene._get_crossover_options()
        ]
    
class PileDefGene(GenoType):
    def __init__(self, pilename: str, counts: list[int], faces: list[Stack.Face]) -> None:
        self.pilename = pilename
        self.counts = counts
        self.faces = faces
        self.card_count = sum(self.counts)
    
    def get_gdl(self) -> str:
        return ''.join([f"{self.pilename} {count} {face}\n" for count, face in zip(self.counts, self.faces)]) + "\n"

    @staticmethod
    def get_random(rnd: Random, card_count: int = 0, is_card_count_exact: bool = False, special_pilenames: list[str] = []) -> PileDefGene:
        pilename = rnd.choice(special_pilenames + [None] * 2) # twice as likely to choose a new name
        if pilename is None:
            pilename = GenoType.get_random_name(rnd).upper()
        counts = PileDefGene.get_random_counts(rnd, card_count, is_card_count_exact)
        faces = PileDefGene.get_random_faces(counts, rnd)
        return PileDefGene(pilename, counts, faces)
    
    def add_cards(self, rnd: Random, max_added: int) -> int:
        less_than_max = [i for i, count in enumerate(self.counts) if count < Params.MAX_CARD_IN_PILE]
        if len(less_than_max) > 0 and coin_flip(rnd):
            ind = rnd.choice(less_than_max)
            count_added = min(rnd.randint(1, Params.MAX_CARD_IN_PILE - self.counts[ind]), max_added)
            self.counts[ind] += count_added
        else:
            count_added = min(PileDefGene.get_random_pile_size(rnd), max_added)
            self.counts.append(count_added)
            self.faces.append(rnd.choice(self.faces))
        self.card_count += count_added
        return count_added
    
    def remove_cards(self, rnd: Random, max_removed: int) -> int:
        non_zero = [i for i, count in enumerate(self.counts) if count > 0]
        if len(non_zero) == 0:
            return 0
        ind = rnd.choice(non_zero)
        # should I check to make sure there is at least 1 pile? alternatively I can update setup and remove pilename from conditions etc.
        if len(self.counts) > 1 and self.counts[ind] > max_removed and coin_flip(rnd, 3):
            self.counts.pop(ind)
            self.faces.pop(ind)
        elif coin_flip(rnd) and self.counts[ind] > max_removed:
            self.counts[ind] = 0
        else:
            self.counts[ind] -= min(rnd.randint(1, self.counts[ind]), max_removed)
        count_removed = self.card_count - sum(self.counts)
        self.card_count -= count_removed
        return count_removed

    @staticmethod
    def get_random_pile_size(rnd: Random):
        return rnd.randint(0, Params.MAX_CARD_IN_PILE)

    @staticmethod
    def get_random_counts(rnd: Random, card_count: int, is_card_count_exact: bool) -> list[int]:
        if is_card_count_exact:
            counts = [count for count in GenoType.get_random_numbers(rnd, card_count, rnd.randint(1, Params.MAX_PILE_REPEAT_COUNT), True) if count > 0]
        else:
            counts = [PileDefGene.get_random_pile_size(rnd)
                  for i in range(rnd.randint(1, Params.MAX_PILE_REPEAT_COUNT))]
            for i in range(len(counts)):
                if counts[i] > card_count:
                    counts[i] = card_count # TODO distribute the difference
                    card_count = 0
                    counts = counts[:i+1]
                    break
                card_count -= counts[i]
        return counts
    
    @staticmethod
    def get_random_faces(counts: list[int], rnd: Random, face_types: list[Stack.Face]|None=None) -> list[Stack.Face]:
        if face_types is None:
            face_type_count = rnd.randint(1, min(len(counts), Params.MAX_FACE_TYPE_PER_PILE))
            face_types = rnd.sample(list(Stack.Face), face_type_count)
        assert len(face_types) <= len(counts)
        faces = []
        brs = [0] + sorted(rnd.sample(range(1, len(counts)), len(face_types) - 1)) + [len(counts)]
        for i in range(len(brs) - 1):
            for _ in range(brs[i], brs[i + 1]):
                faces.append(face_types[i])
        assert len(faces) == len(counts)
        return faces
    
    def _rename_(self, name: str) -> PileDefGene:
        self.pilename = name
        return self
    
    def _change_counts_(self, counts: list[int]) -> PileDefGene:
        self.counts = counts
        self.card_count = sum(self.counts)
        return self
    
    
    def _redo_card_count_(self, rnd: Random, card_count: int) -> PileDefGene:
        counts = []
        while sum(counts) < card_count:
            counts.append(PileDefGene.get_random_pile_size(rnd))
        if sum(counts) > card_count:
            counts[-1] -= sum(counts) - card_count # TODO distribute the difference
        # possibly, this won't be in Params range anymore for MAX_PILE_REPEAT_COUNT
        return self._change_counts_(counts)
    
    def _adjust_faces_(self, rnd: Random) -> PileDefGene:
        face_types = [face for face in list(Stack.Face) if face in self.faces]
        self.faces = PileDefGene.get_random_faces(self.counts, rnd, face_types)
        return self
    
    def _redo_faces_(self, rnd: Random) -> PileDefGene:
        self.faces = PileDefGene.get_random_faces(self.counts, rnd)
        return self
    
    def copy(self) -> PileDefGene:
        return PileDefGene(self.pilename, [count for count in self.counts], [face for face in self.faces])
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[PileDefGene, PileDefGene, Random], PileDefGene]]:
        # we may card counts, this change will cascade to other components only if crossover/mutation is called on a bigger component
        return [
            lambda me, other, rnd: PileDefGene(me.pilename, other.counts, me.faces)._adjust_faces_(rnd), # counts will be adjusted from outside
            lambda me, other, rnd: PileDefGene(me.pilename, me.counts, other.faces)._adjust_faces_(rnd),
        ]
    
    @staticmethod
    def _get_mutation_options() -> list[Callable[[PileDefGene, Random], PileDefGene]]:
        # return [
        #     lambda me, rnd: me._redo_card_count_(rnd, me.card_count),
        #     lambda me, rnd: me._redo_faces_(rnd),
        # ]
        return [
            lambda me, rnd, c=c_option: c(me, PileDefGene.get_random(rnd, me.card_count, True, []), rnd)
            for c_option in PileDefGene._get_crossover_options()
        ]
    
class SetupGene(GenoType):
    def __init__(self, draw: DealDrawDefGene|RotateDrawDefGene|None, piles: list[PileDefGene]) -> None:
        self.draw = draw
        if isinstance(draw, DealDrawDefGene):
            draw.set_setup(self)
        self.piles = piles
        self.card_count = (0 if self.draw is None else self.draw.card_count) + sum([pile.card_count for pile in self.piles])
    
    def get_gdl(self) -> str:
        return "$initial\n" + \
            ("" if self.draw is None else self.draw.get_gdl()) + \
            "".join([pile.get_gdl() for pile in self.piles])
    
    def get_pilenames(self, add_rotate_draw: bool, add_all_draw: bool) -> list[str]:
        ret = [pile.pilename for pile in self.piles]
        if add_rotate_draw and isinstance(self.draw, RotateDrawDefGene):
            ret.append('DRAW')
        elif add_all_draw and self.draw is not None:
            ret.append('DRAW')
        return ret

    @staticmethod
    def get_random(rnd: Random, card_count: int = 0) -> SetupGene:
        # EXCLUDED: custom starting cards in pile
        # EXCLUDED: no pile other than draw
        piles: list[PileDefGene] = []
        draw: DealDrawDefGene|RotateDrawDefGene|None = None
        # special_pile_names = ["FOUNDATION", "COLUMN", "CELL", "DISCARD", "TALON"]
        special_pilenames = [name for name in Params.SPECIAL_PILENAMES]
        while card_count > 0:
            choice = rnd.randint(0, 5)
            if choice == 0 and len(piles) > 0:
                fake_setup = SetupGene(None, piles)
                draw = DealDrawDefGene.get_random(rnd, card_count, fake_setup)
                card_count -= draw.card_count
            elif choice == 1 and len(piles) > 0:
                draw = RotateDrawDefGene.get_random(rnd, card_count)
                card_count -= draw.card_count
            else: # four times the chance
                piles.append(PileDefGene.get_random(rnd, card_count, False, special_pilenames))
                if piles[-1].pilename in special_pilenames:
                    special_pilenames.remove(piles[-1].pilename)
                card_count -= piles[-1].card_count
        return SetupGene(draw, piles) # will readjust fake_setup for draw pile
    
    def copy(self) -> SetupGene:
        # will readjust setup for draw pile
        return SetupGene(self.draw if self.draw is None else self.draw.copy(), [pile.copy() for pile in self.piles])
    
    def _adjust_card_count_(self, intended_card_count: int, rnd: Random) -> SetupGene: # TODO make it better
        self.card_count = sum([pile.card_count for pile in self.piles]) + (0 if self.draw is None else self.draw.card_count)
        # add/expand piles if needed
        while intended_card_count > self.card_count:
            if self.draw is not None and coin_flip(rnd, len(self.piles) + 1):
                self.draw.card_count += intended_card_count - self.card_count
                self.card_count = intended_card_count
            else:
                self.card_count += rnd.choice(self.piles).add_cards(rnd, intended_card_count - self.card_count)
        # remove/trim piles if needed
        while intended_card_count < self.card_count:
            if self.draw is not None and self.draw.card_count > 0 and coin_flip(rnd, len(self.piles) + 1):
                remove_count = min(self.card_count - intended_card_count, self.draw.card_count)
                self.draw.card_count -= remove_count
                self.card_count -= remove_count
                # TODO possibly remove draw if empty?
            else:
                self.card_count -= rnd.choice(self.piles).remove_cards(rnd, self.card_count - intended_card_count)
        self.card_count = intended_card_count
        return self
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[SetupGene, SetupGene, Random], SetupGene]]:
        # there should be no need for adjustments, becuase other should have the same card count
        return [
            # will readjust setup for draw pile
            lambda me, other, rnd: SetupGene(other.draw._transform_pilenames_(rnd, me) if isinstance(other.draw, DealDrawDefGene) else other.draw, me.piles)._adjust_card_count_(me.card_count, rnd),
            lambda me, other, rnd: SetupGene(me.draw, other.piles)._adjust_card_count_(me.card_count, rnd),
        ]
    
    @staticmethod
    def _get_mutation_options() -> list[Callable[[SetupGene, Random], SetupGene]]:
        crossover_mutations: list[Callable[[SetupGene, Random], SetupGene]] = [
            lambda me, rnd, c=c_option: c(me, SetupGene.get_random(rnd, me.card_count), rnd)
            for c_option in SetupGene._get_crossover_options()
        ]
        return crossover_mutations
    
    def get_pilename_mapping(self, rnd: Random, new_setup: SetupGene, include_rotate_draw: bool, include_draw: bool):
        mapping: dict[str, str] = {}
        my_pilenames: list[str] = self.get_pilenames(include_rotate_draw, include_draw)
        new_pilenames: list[str] = new_setup.get_pilenames(include_rotate_draw, include_draw)
        new_uncommon = [p for p in new_pilenames if p not in my_pilenames]
        my_uncommon = [p for p in my_pilenames if p not in new_pilenames]
        if len(new_uncommon) < len(my_uncommon):
            new_uncommon += rnd.choices(new_pilenames, k=len(my_uncommon) - len(new_uncommon))
        rnd.shuffle(new_uncommon)
        for i, pilename in enumerate(my_uncommon):
            mapping[pilename] = new_uncommon[i]
        for pilename in new_pilenames:
            mapping[pilename] = pilename
        return mapping

class ConditionGene(GenoType, Reducible):
    # could be implemented with inheritance, but I want to keep this simple
    class CondType(Enum):
        MOVE = 1
        MOVE_STACK = 2
        GLOBAL = 3
        WIN = 4 # technically same as global, might have different rules
    
    T = TypeVar('T', bound='Arg')

    class Arg(GenoType):
        def __init__(self, value: str) -> None:
            self.value = value
        
        def get_gdl(self) -> str:
            return self.value

        def copy(self: ConditionGene.T) -> ConditionGene.T:
            return self.__class__(self.value)
        
        @staticmethod
        def _get_crossover_options() -> list[Callable[[ConditionGene.T, ConditionGene.T, Random], ConditionGene.T]]:
            return [
                lambda me, other, rnd: me,
                lambda me, other, rnd: other,
            ]

    class Op(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.Op:
            return ConditionGene.Op(str(rnd.choice(list(cond.MathOp))))
        
        @staticmethod
        def _get_mutation_options() -> list[Callable[[ConditionGene.Op, Random], ConditionGene.Op]]:
            return [lambda me, rnd: ConditionGene.Op.get_random(rnd)]
    
    class Count(Arg):
        @staticmethod
        def get_random(rnd: Random, max: int = Params.MAX_CARD_IN_COND) -> ConditionGene.Count:
            return ConditionGene.Count(str(rnd.randint(0, max)))
        
        @staticmethod
        def _get_mutation_options() -> list[Callable[[ConditionGene.Count, Random], ConditionGene.Count]]:
            return [lambda me, rnd: ConditionGene.Count.get_random(rnd)]
    
    class Suits(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.Suits:
            all_suits = [str(suit) for suit in SFN]
            suits: list[str] = rnd.sample(all_suits, rnd.randint(1, len(all_suits)))
            return ConditionGene.Suits("{" + ", ".join(suits) + "}")
        
        @staticmethod
        def _get_mutation_options() -> list[Callable[[ConditionGene.Suits, Random], ConditionGene.Suits]]:
            return [lambda me, rnd: ConditionGene.Suits.get_random(rnd)]
    
    class Ranks(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.Ranks:
            all_ranks = [str(i) for i in range(1, 10)] + ["J", "Q", "K"]
            if Params.RANKS_ARG_TYPE == Params.RanksArgType.Any:
                ranks: list[str] = rnd.sample(all_ranks, rnd.randint(1, len(all_ranks)))
            elif Params.RANKS_ARG_TYPE == Params.RanksArgType.SingleOnly:
                ranks: list[str] = [rnd.choice(all_ranks)]
            else:
                ranks: list[str] = [rnd.choice(['1', 'K'])]
            if len(ranks) == 1:
                return ConditionGene.Ranks(ranks[0])
            return ConditionGene.Ranks("{" + ", ".join(ranks) + "}")
        
        @staticmethod
        def _get_mutation_options() -> list[Callable[[ConditionGene.Ranks, Random], ConditionGene.Ranks]]:
            return [lambda me, rnd: ConditionGene.Ranks.get_random(rnd)]
    
    class Pileset(Arg):
        def __init__(self, value: str, setup: SetupGene) -> None:
            super().__init__(value)
            self.setup = setup
        
        @staticmethod
        def get_random(rnd: Random, setup: SetupGene|None = None) -> ConditionGene.Pileset:
            assert setup is not None
            options = setup.get_pilenames(False, True)
            return ConditionGene.Pileset(rnd.choice(options), setup)
        
        @staticmethod
        def _get_mutation_options() -> list[Callable[[ConditionGene.Pileset, Random], ConditionGene.Pileset]]:
            return [lambda me, rnd: ConditionGene.Pileset.get_random(rnd, me.setup)]
        
        def copy(self: ConditionGene.Pileset) -> ConditionGene.Pileset:
            return ConditionGene.Pileset(self.value, self.setup)
        
        def set_setup(self, setup: SetupGene) -> None:
            self.setup = setup

    class RankCond(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.RankCond:
            return ConditionGene.RankCond(rnd.choice([str(val) for val in cond.MultiRankCondition.MODE]))
        
        @staticmethod
        def _get_mutation_options() -> list[Callable[[ConditionGene.RankCond, Random], ConditionGene.RankCond]]:
            return [lambda me, rnd: ConditionGene.RankCond.get_random(rnd)]
    
    class SuitCond(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.SuitCond:
            return ConditionGene.SuitCond(rnd.choice([str(val) for val in cond.MultiSuitCondition.MODE]))
        
        @staticmethod
        def _get_mutation_options() -> list[Callable[[ConditionGene.SuitCond, Random], ConditionGene.SuitCond]]:
            return [lambda me, rnd: ConditionGene.SuitCond.get_random(rnd)]

    def __init__(self, root: str, root_args: list[tuple[Arg, int, int]], subconds: Sequence[ConditionGene],
                 type: ConditionGene.CondType, setup: SetupGene) -> None:
        self.root = root
        self.subconds = subconds
        self.root_args = root_args
        self.type = type
        self.set_setup(setup)
        self.size = 1 if self.is_base() else sum([subcond.size for subcond in self.subconds])

    def is_base(self) -> bool:
        return len(self.subconds) == 0

    def get_gdl(self) -> str:
        root_gdl = self.root
        offset = 0
        for arg, st, end in self.root_args:
            val = arg.get_gdl()
            root_gdl = root_gdl[:st+offset] + val + root_gdl[end+offset:]
            offset += len(val) - (end - st)
        if self.is_base():
            return root_gdl
        return root_gdl + "\n" + \
            "\n".join(["    " + "\n    ".join(subcond.get_gdl().split("\n")) for subcond in self.subconds])
    
    @staticmethod
    def get_random_base(rnd: Random, type: CondType) -> str:
        possible: list[str] = []
        if type == ConditionGene.CondType.MOVE or type == ConditionGene.CondType.MOVE_STACK:
            possible += [
                "DEST Empty",
                "DEST Size <op> <count>",
                "DEST Suit <suits>",
                "DEST Rank <ranks>",
                "SRC Suit <suits>",
                "SRC Rank <ranks>",
                "DESTSRC Suit <suitcond>",
                "DESTSRC Rank <rankcond>",
            ]
        if type == ConditionGene.CondType.MOVE_STACK:
            possible += [
                "SRCSTACK Suit <suitcond>",
                "SRCSTACK Rank <rankcond>",
                "SRCSTACK Size <op> <count>",
            ]
        if type == ConditionGene.CondType.WIN and Params.WIN_COND_ALL_EMPTY_ONLY:
            return "PILE ALL <pileset> Empty"
        if type in [ConditionGene.CondType.GLOBAL, ConditionGene.CondType.WIN]:
            possible = [
                "PILE ALL <pileset> Empty",
                "PILE ANY <pileset> Empty",
                "PILE ALL <pileset> Size > 0" if Params.GLOBAL_PILE_SIZE_GT0_ONLY else "PILE ALL <pileset> Size <op> <count>",
                "PILE ANY <pileset> Size > 0" if Params.GLOBAL_PILE_SIZE_GT0_ONLY else "PILE ANY <pileset> Size <op> <count>",
            ]
        return rnd.choice(possible)
    
    @staticmethod
    def get_random_base_condition(rnd: Random, type: CondType, setup: SetupGene) -> ConditionGene:
        base = ConditionGene.get_random_base(rnd, type)
        args: list[tuple[ConditionGene.Arg, int, int]] = []
        def check_arg(s: str, i: int, val: str, factory: Callable[[], ConditionGene.Arg]):
            if s[i:i+len(val)] == val:
                args.append((factory(), i, i+len(val)))
        for i in range(len(base)):
            check_arg(base, i, "<op>", lambda: ConditionGene.Op.get_random(rnd))
            check_arg(base, i, "<count>", lambda: ConditionGene.Count.get_random(rnd, Params.MAX_CARD_IN_COND))
            check_arg(base, i, "<suits>", lambda: ConditionGene.Suits.get_random(rnd))
            check_arg(base, i, "<ranks>", lambda: ConditionGene.Ranks.get_random(rnd))
            check_arg(base, i, "<pileset>", lambda: ConditionGene.Pileset.get_random(rnd, setup))
            check_arg(base, i, "<rankcond>", lambda: ConditionGene.RankCond.get_random(rnd))
            check_arg(base, i, "<suitcond>", lambda: ConditionGene.SuitCond.get_random(rnd))
        return ConditionGene(base, args, [], type, setup)

    @staticmethod
    def get_random(rnd: Random, type: CondType = CondType.MOVE, setup: SetupGene|None = None, exclude: str|None = None, depth: int = 0) -> ConditionGene:
        assert setup is not None
        max_depth = Params.MAX_COND_DEPTH if type != ConditionGene.CondType.GLOBAL else Params.MAX_GLOBAL_COND_DEPTH
        choice = rnd.randint(0, 4) if depth < max_depth else 0
        if choice in [0, 1]:
            return ConditionGene.get_random_base_condition(rnd, type, setup)
        root = "AND" if (choice == 2 or exclude == "OR") else "OR"
        exclude = root if Params.SIMPLE_CONDITION else None
        subcount = rnd.randint(2, Params.MAX_COND_BRANCH)
        return ConditionGene(root, [], [
            ConditionGene.get_random(rnd, type, setup, exclude, depth+1)
            for _ in range(subcount)], type, setup)
    
    def copy(self) -> ConditionGene:
        return ConditionGene(self.root, [(arg.copy(), s, e) for arg, s, e in self.root_args], [subcond.copy() for subcond in self.subconds], self.type, self.setup)

    def set_setup(self, setup: SetupGene) -> None:
        self.setup = setup
        for subcond in self.subconds:
            subcond.set_setup(setup)
    
    def _find_subcond(self, iter: int) -> tuple[None|ConditionGene, int]:
        new_iter = 0
        to_reduce = None
        for subcond in self.subconds:
            if new_iter + subcond.size > iter:
                to_reduce = subcond
                break
            new_iter += subcond.size
        if to_reduce is None:
            return None, iter
        return to_reduce, iter - new_iter
    
    def get_reduced(self: ConditionGene, rnd: Random|None, iter: int) -> ConditionGene | None:
        if self.is_base():
            return None
        ret = self.copy()
        weights = [subcond.size/ret.size for subcond in ret.subconds]
        if rnd is not None:
            to_reduce = rnd.choices(ret.subconds, weights)[0]
        else:
            to_reduce, iter = ret._find_subcond(iter)
            if to_reduce is None:
                return None
        reduced = to_reduce.get_reduced(rnd, iter)
        if reduced is not None:
            ret.subconds = [subcond if subcond != to_reduce else reduced for subcond in ret.subconds]
        else:
            ret.subconds = [subcond for subcond in ret.subconds if subcond != to_reduce]
            if len(ret.subconds) == 1:
                return ret.subconds[0]
        ret.size = sum([subcond.size for subcond in ret.subconds])
        return ret

    def _become_(self, other: ConditionGene) -> ConditionGene:
        self.root = other.root
        self.subconds = other.subconds
        self.root_args = other.root_args
        self.type = other.type
        self.setup = other.setup
        self.size = other.size
        return self
    
    def _mutate_single_(self, rnd: Random) -> ConditionGene:
        if not self.is_base():
            return rnd.choice(self.subconds)._mutate_single_(rnd)
        if len(self.root_args) == 0 or coin_flip(rnd):
            return self._become_(ConditionGene.get_random_base_condition(rnd, self.type, self.setup))
        arg_index = rnd.randint(0, len(self.root_args) - 1)
        arg, s, e = self.root_args[arg_index]
        self.root_args[arg_index] = (arg.mutate(rnd), s, e)
        return self
    
    def _add_one_condition_(self, rnd: Random, exclude: str|None, depth: int = 0, cond: ConditionGene|None = None) -> ConditionGene:
        if self.is_base():
            if depth < Params.CROSSOVER_MAX_COND_DEPTH:
                copy = self.copy()
                root = "AND" if (coin_flip(rnd) or exclude == "OR") else "OR"
                exclude = root if Params.SIMPLE_CONDITION else None
                if cond is None:
                    cond = ConditionGene.get_random(rnd, self.type, self.setup, exclude, depth+1)
                self._become_(ConditionGene(root, [], [
                    copy,
                    cond,
                ], self.type, self.setup))
            # else: nothing we can do but to retry and end up in another branch
        else: # AND or OR
            if depth == (Params.CROSSOVER_MAX_COND_DEPTH - 1) or (coin_flip(rnd) == 0 and len(self.subconds) < Params.MAX_COND_BRANCH):
                if len(self.subconds) < Params.CROSSOVER_MAX_COND_BRANCH:
                    exclude = self.root if Params.SIMPLE_CONDITION else None
                    if cond is None:
                        cond = ConditionGene.get_random(rnd, self.type, self.setup, exclude, depth+1)
                    self.subconds = [subcond for subcond in self.subconds] + [cond]
                # else: both max depth and max branch is reached, adding conditions is not possible
            else:
                exclude = self.root if Params.SIMPLE_CONDITION else None
                rnd.choice(self.subconds)._add_one_condition_(rnd, exclude, depth + 1, cond)
        return self
    
    def _remove_one_condition_(self, rnd: Random) -> ConditionGene:
        if self.is_base():
            return self # nothing we can do
        else:
            subcond = rnd.choice(self.subconds)
            if subcond.is_base():
                self.subconds = [s for s in self.subconds if s != subcond]
                if len(self.subconds) == 1:
                    self._become_(self.subconds[0])
            else:
                subcond._remove_one_condition_(rnd)
        return self
    
    def _get_random_subtree(self, rnd: Random) -> ConditionGene:
        if self.is_base():
            return self
        else:
            if coin_flip(rnd, self.size):
                return self
            weights = [subcond.size/self.size for subcond in self.subconds]
            subcond = rnd.choices(self.subconds, weights)[0]
            return subcond._get_random_subtree(rnd)
        
    def get_depth(self):
        if self.is_base():
            return 1
        return max([subcond.get_depth() for subcond in self.subconds]) + 1
    
    def _stitch_subtree_randomly_(self, rnd: Random, subtree: ConditionGene) -> ConditionGene:
        if coin_flip(rnd):
            subtree_depth = subtree.get_depth() # we can possibly check if the depth is too much not to use this coin flip
            self._add_one_condition_(rnd, None, subtree_depth, subtree)
        else:
            self._get_random_subtree(rnd)._become_(subtree)
        return self
    
    def transform_pilenames_from_mapping(self, mapping: dict[str, str]):
        if self.is_base():
            for arg, _, _ in self.root_args:
                if isinstance(arg, ConditionGene.Pileset):
                    arg.value = mapping[arg.value]
        else:
            for subcond in self.subconds:
                subcond.transform_pilenames_from_mapping(mapping)
    
    def _transform_pilenames_(self, rnd: Random, new_setup: SetupGene):
        mapping: dict[str, str] = self.setup.get_pilename_mapping(rnd, new_setup, False, True)
        self.transform_pilenames_from_mapping(mapping)
        return self

    @staticmethod
    def _get_crossover_options() -> list[Callable[[ConditionGene, ConditionGene, Random], ConditionGene]]:
        return [
            lambda me, other, rnd: me._stitch_subtree_randomly_(rnd, other._get_random_subtree(rnd)._transform_pilenames_(rnd, me.setup)),
            lambda me, other, rnd: other._transform_pilenames_(rnd, me.setup)._stitch_subtree_randomly_(rnd, me._get_random_subtree(rnd)),
        ]
    
    @staticmethod
    def _get_mutation_options() -> list[Callable[[ConditionGene, Random], ConditionGene]]:
        # this is not used unless mutation is directly called on the condition and not on the parent compornts
        return [
            lambda me, rnd: me._add_one_condition_(rnd, None, 0, None),
            lambda me, rnd: me._remove_one_condition_(rnd)
        ]

E = TypeVar('E', bound='EndToEndAction')
class EndToEndAction(GenoType, Reducible):
    def __init__(self, starts: list[str], ends: list[str], cond: ConditionGene, setup: SetupGene) -> None:
        self.starts = starts
        self.ends = ends
        self.cond = cond
        self.set_setup(setup)
    
    def get_ends(self):
        return [(s, e) for s in self.starts for e in self.ends]
    
    def set_setup(self, setup: SetupGene) -> None:
        self.setup = setup
        self.cond.set_setup(setup)
    
    @staticmethod
    def get_random_endpoints(rnd: Random, end_options: list[tuple[str, str]]):
        start, end = rnd.choice(end_options)
        starts = [start]
        ends = [end]
        other_end_options = [(s, e) for (s, e) in end_options if not (s == start and e == end)]
        expand_action = rnd.randint(0, 4) # 2 chance of no expand
        if expand_action == 0 or expand_action == 4:
            extra_starts = [s for (s, e) in other_end_options if e == end]
            starts += rnd.sample(extra_starts, rnd.randint(0, len(extra_starts))) # 0 is an option
        elif expand_action == 1 or expand_action == 4:
            extra_ends = [e for (s, e) in other_end_options if s == start]
            ends += rnd.sample(extra_ends, rnd.randint(0, len(extra_ends))) # 0 is an option
        return starts, ends
    
    @staticmethod
    def get_endpoint_options(setup: SetupGene, exclude: list[tuple[str, str]]):
        pilenames = setup.get_pilenames(False, False)
        move_from_pilenames = setup.get_pilenames(True, False)
        move_options = [(pilename_or_D, pilename) for pilename in pilenames for pilename_or_D in move_from_pilenames if (pilename_or_D, pilename) not in exclude]
        move_stack_options = [(pilename, pilename2) for pilename2 in pilenames for pilename in pilenames if (pilename, pilename2) not in exclude]
        return move_options, move_stack_options
    
    @staticmethod
    @abstractmethod
    def get_random(rnd: Random, setup: SetupGene|None = None, exclude: list[tuple[str, str]] = []) -> EndToEndAction:
        raise NotImplementedError
    
    @staticmethod
    def _transform_endpoints_(ends: list[str], rnd: Random, old_setup: SetupGene, new_setup: SetupGene, include_ratote_draw: bool, include_draw: bool):
        mapping = old_setup.get_pilename_mapping(rnd, new_setup, include_ratote_draw, include_draw)
        new_pilenames = set(mapping.values())
        return get_uniques([(end if end in new_pilenames else mapping[end]) for end in ends])
    
    @classmethod
    def _get_crossover_options_for_class(cls: type[E]) -> list[Callable[[E, E, Random], E]]:
        is_move_gene = issubclass(cls, MoveGene)
        ends_crossover: list[Callable[[E, E, Random], E]] = [
            lambda me, other, rnd: cls(EndToEndAction._transform_endpoints_(other.starts, rnd, other.setup, me.setup, is_move_gene, False), me.ends, me.cond, me.setup), # this will possibly result in duplicate moves
            lambda me, other, rnd: cls(me.starts, EndToEndAction._transform_endpoints_(other.ends, rnd, other.setup, me.setup, False, False), me.cond, me.setup), # this will possibly result in duplicate moves
        ]
        conds_crossover: list[Callable[[E, E, Random], E]] = [
            lambda me, other, rnd, c=c_option: cls(me.starts, me.ends, c(me.cond, other.cond, rnd), me.setup)
            for c_option in ConditionGene._get_crossover_options()
        ]
        return (ends_crossover if Params.DUPLICATE_MOVE_ENDS_ALLOWED else []) + conds_crossover

    @classmethod
    def _get_mutation_options_for_class(cls: type[E]) -> list[Callable[[E, Random], E]]:
        return [
            lambda me, rnd, c=c_option: c(me, cls.get_random(rnd, me.setup, []), rnd)
            for c_option in cls._get_crossover_options()
        ]
    
    @classmethod
    def get_list_of_randoms(cls: type[E], rnd: Random, count: int, setup: SetupGene) -> list[E]:
        moves: list[E] = []
        excluded_end_points: list[tuple[str, str]] = []
        for _ in range(count):
            try:
                new_move = cast(E, cls.get_random(rnd, setup, excluded_end_points))
                moves.append(new_move)
                excluded_end_points += moves[-1].get_ends()
            except InvalidMoveCreationDueToEndPointExclusion as e:
                break
        return moves
    
    def _transform_pilenames_(self, rnd: Random, new_setup: SetupGene):
        is_move_gene = isinstance(self, MoveGene)
        self.cond._transform_pilenames_(rnd, new_setup)
        self.starts = EndToEndAction._transform_endpoints_(self.starts, rnd, self.setup, new_setup, is_move_gene, False)
        self.ends = EndToEndAction._transform_endpoints_(self.ends, rnd, self.setup, new_setup, False, False)
        return self

class MoveGene(EndToEndAction):
    def get_gdl(self) -> str:
        return f"MOVE {GenoType.list_to_gdl(self.starts)} {GenoType.list_to_gdl(self.ends)}\n" + \
            self.cond.get_gdl() + "\n"
    
    @staticmethod
    def get_random(rnd: Random, setup: SetupGene|None = None, exclude: list[tuple[str, str]] = []) -> MoveGene:
        assert setup is not None
        move_options, _ = MoveGene.get_endpoint_options(setup, exclude)
        if len(move_options) == 0: raise InvalidMoveCreationDueToEndPointExclusion()
        starts, ends = MoveGene.get_random_endpoints(rnd, move_options)
        return MoveGene(starts, ends, ConditionGene.get_random(rnd, ConditionGene.CondType.MOVE, setup), setup)
    
    def copy(self) -> MoveGene:
        return MoveGene([pile for pile in self.starts], [pile for pile in self.ends], self.cond.copy(), self.setup)
    
    def get_reduced(self: MoveGene, rnd: Random|None, iter: int) -> MoveGene | None:
        reduced_cond = self.cond.get_reduced(rnd, iter)
        if reduced_cond is None:
            return None
        return MoveGene([pile for pile in self.starts], [pile for pile in self.ends], reduced_cond, self.setup)
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[MoveGene, MoveGene, Random], MoveGene]]:
        return MoveGene._get_crossover_options_for_class()

    @staticmethod
    def _get_mutation_options() -> list[Callable[[MoveGene, Random], MoveGene]]:
        return MoveGene._get_mutation_options_for_class()

class MoveStackGene(EndToEndAction):
    def get_gdl(self) -> str:
        return f"MOVE_STACK {GenoType.list_to_gdl(self.starts)} {GenoType.list_to_gdl(self.ends)}\n" + \
            self.cond.get_gdl() + "\n"
    
    @staticmethod
    def get_random(rnd: Random, setup: SetupGene|None = None, exclude: list[tuple[str, str]] = []) -> MoveStackGene:
        assert setup is not None
        _, move_stack_options = MoveStackGene.get_endpoint_options(setup, exclude)
        if len(move_stack_options) == 0: raise InvalidMoveCreationDueToEndPointExclusion()
        starts, ends = MoveStackGene.get_random_endpoints(rnd, move_stack_options)
        return MoveStackGene(starts, ends, ConditionGene.get_random(rnd, ConditionGene.CondType.MOVE_STACK, setup), setup)
    
    def copy(self) -> MoveStackGene:
        return MoveStackGene([pile for pile in self.starts], [pile for pile in self.ends], self.cond.copy(), self.setup)
    
    def get_reduced(self: MoveStackGene, rnd: Random|None, iter: int) -> MoveStackGene | None:
        reduced_cond = self.cond.get_reduced(rnd, iter)
        if reduced_cond is None:
            return None
        return MoveStackGene([pile for pile in self.starts], [pile for pile in self.ends], reduced_cond, self.setup)
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[MoveStackGene, MoveStackGene, Random], MoveStackGene]]:
        return MoveStackGene._get_crossover_options_for_class()

    @staticmethod
    def _get_mutation_options() -> list[Callable[[MoveStackGene, Random], MoveStackGene]]:
        return MoveStackGene._get_mutation_options_for_class()

class DrawMoveGene(GenoType, Reducible):
    def __init__(self, cond: ConditionGene, setup: SetupGene) -> None:
        self.cond = cond
        self.set_setup(setup)

    def get_gdl(self) -> str:
        return "DRAW\n" + self.cond.get_gdl() + "\n"
    
    @staticmethod
    def get_random(rnd: Random, setup: SetupGene|None = None) -> DrawMoveGene:
        assert setup is not None
        return DrawMoveGene(ConditionGene.get_random(rnd, ConditionGene.CondType.GLOBAL, setup), setup)
    
    def copy(self) -> DrawMoveGene:
        return DrawMoveGene(self.cond.copy(), self.setup)

    def set_setup(self, setup: SetupGene) -> None:
        self.setup = setup
        self.cond.set_setup(setup)
    
    def get_reduced(self: DrawMoveGene, rnd: Random|None, iter: int) -> DrawMoveGene | None:
        reduced_cond = self.cond.get_reduced(rnd, iter)
        if reduced_cond is None:
            return None
        return DrawMoveGene(reduced_cond, self.setup)
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[DrawMoveGene, DrawMoveGene, Random], DrawMoveGene]]:
        return [
            lambda me, other, rnd, c=c_option: DrawMoveGene(c(me.cond, other.cond, rnd), me.setup)
            for c_option in ConditionGene._get_crossover_options()
        ]

    @staticmethod
    def _get_mutation_options() -> list[Callable[[DrawMoveGene, Random], DrawMoveGene]]:
        return [
            lambda me, rnd, c=c_option: c(me, DrawMoveGene.get_random(rnd, me.setup), rnd)
            for c_option in DrawMoveGene._get_crossover_options()
        ]
    
    def _transform_pilenames_(self, rnd: Random, new_setup: SetupGene):
        self.cond._transform_pilenames_(rnd, new_setup)
    
class MovesGene(GenoType, Reducible):
    def __init__(self, moves: list[MoveGene], move_stacks: list[MoveStackGene], draw_move: DrawMoveGene|None, setup: SetupGene) -> None:
        self.moves = moves
        self.move_stacks = move_stacks
        self.draw_move = draw_move
        self.set_setup(setup)
    
    def get_gdl(self) -> str:
        return "$moves\n" + \
            "".join([move.get_gdl() for move in self.moves]) + \
            "".join([move_stack.get_gdl() for move_stack in self.move_stacks]) + \
            ("" if self.draw_move is None else self.draw_move.get_gdl())
    
    @staticmethod
    def get_random(rnd: Random, setup: SetupGene|None=None) -> MovesGene:
        assert setup is not None
        # EXCLUDE: more than 2 move or move_stack
        while True:
            move_count = rnd.randint(0, Params.MAX_MOVE_COUNT)
            move_stack_count = rnd.randint(0, Params.MAX_MOVE_STACK_COUNT)
            if move_count + move_stack_count != 0 or Params.MAX_MOVE_COUNT + Params.MAX_MOVE_STACK_COUNT == 0:
                break
        moves = MoveGene.get_list_of_randoms(rnd, move_count, setup)
        move_stacks = MoveStackGene.get_list_of_randoms(rnd, move_stack_count, setup)
        draw_move = None
        if isinstance(setup.draw, DealDrawDefGene) and coin_flip(rnd):
            draw_move = DrawMoveGene.get_random(rnd, setup)
        return MovesGene(moves, move_stacks, draw_move, setup)
    
    def copy(self) -> MovesGene:
        return MovesGene(
            [move.copy() for move in self.moves],
            [move_stack.copy() for move_stack in self.move_stacks],
            self.draw_move if self.draw_move is None else self.draw_move.copy(), self.setup
        )
    
    def set_setup(self, setup: SetupGene) -> None:
        self.setup = setup
        for move in self.moves:
            move.set_setup(setup)
        for move_stack in self.move_stacks:
            move_stack.set_setup(setup)
        if self.draw_move is not None:
            self.draw_move.set_setup(setup)
    
    def _find_move(self, iter: int, moves: list[MoveGene]|list[MoveStackGene]) -> tuple[None|MoveGene|MoveStackGene, int]:
        new_iter = 0
        to_reduce = None
        for move in moves:
            if new_iter + move.cond.size > iter:
                to_reduce = move
                break
            new_iter += move.cond.size
        return to_reduce, iter - new_iter
    
    def get_reduced(self: MovesGene, rnd: Random|None, iter: int) -> MovesGene | None:
        ret = self.copy()
        target_choices = [1, 2, 3]
        if rnd is not None:
            rnd.shuffle(target_choices)
        if len(ret.moves) == 0: target_choices.remove(1)
        if len(ret.move_stacks) == 0: target_choices.remove(2)
        if ret.draw_move is None: target_choices.remove(3)
        for target_choice in target_choices: # TODO make this look nicer
            if target_choice == 1:
                if rnd is not None:
                    p = uniform([move.cond.size for move in ret.moves])
                    to_reduce = rnd.choices(ret.moves, p)[0]
                else:
                    to_reduce, iter = self._find_move(iter, ret.moves)
                    if to_reduce is None:
                        continue
                reduced = to_reduce.get_reduced(rnd, iter)
                if reduced is not None:
                    ret.moves = [move if move != to_reduce else reduced for move in ret.moves]
                    return ret
                assert len(ret.moves) > 0
                ret.moves = [move for move in ret.moves if move != to_reduce]
                return ret
            elif target_choice == 2:
                if rnd is not None:
                    p = uniform([move.cond.size for move in ret.move_stacks])
                    to_reduce = rnd.choices(ret.move_stacks, p)[0]
                else:
                    to_reduce, iter = self._find_move(iter, ret.move_stacks)
                    if to_reduce is None:
                        continue
                reduced = to_reduce.get_reduced(rnd, iter)
                if reduced is not None:
                    ret.move_stacks = [move if move != to_reduce else reduced for move in ret.move_stacks]
                    return ret
                assert len(ret.move_stacks) > 0
                ret.move_stacks = [move for move in ret.move_stacks if move != to_reduce]
                return ret
            elif target_choice == 3:
                assert ret.draw_move is not None
                ret.draw_move = ret.draw_move.get_reduced(rnd, iter)
                return ret
        return None
    
    def _crossover_move(self, other: MovesGene, rnd: Random, c_option: Callable[[MoveGene, MoveGene, Random], MoveGene]) -> MovesGene:
        ind = rnd.randint(0, len(self.moves) - 1) if len(self.moves) > 0 else 0
        other_ind = rnd.randint(0, len(other.moves) - 1) if len(other.moves) > 0 else 0
        if len(self.moves) == 0 and len(other.moves) == 0:
            return self
        if len(self.moves) == 0:
            self.moves.append(other.moves[other_ind]) 
            return self
        if len(other.moves) == 0:
            self.moves.pop(ind)
            return self
        ind = rnd.randint(0, len(self.moves) - 1)
        other_ind = rnd.randint(0, len(other.moves) - 1)
        self.moves[ind] = c_option(self.moves[ind], other.moves[other_ind], rnd)
        return self

    def _crossover_move_stack(self, other: MovesGene, rnd: Random, c_option: Callable[[MoveStackGene, MoveStackGene, Random], MoveStackGene]) -> MovesGene:
        ind = rnd.randint(0, len(self.move_stacks) - 1) if len(self.move_stacks) > 0 else 0
        other_ind = rnd.randint(0, len(other.move_stacks) - 1) if len(other.move_stacks) > 0 else 0
        if len(self.move_stacks) == 0 and len(other.move_stacks) == 0:
            return self
        if len(self.move_stacks) == 0:
            self.move_stacks.append(other.move_stacks[other_ind])
            return self
        if len(other.move_stacks) == 0:
            self.move_stacks.pop(ind)
            return self
        self.move_stacks[ind] = c_option(self.move_stacks[ind], other.move_stacks[other_ind], rnd)
        return self
    
    def _crossover_draw(self, other: MovesGene, rnd: Random, c_option: Callable[[DrawMoveGene, DrawMoveGene, Random], DrawMoveGene]) -> MovesGene:
        if self.draw_move is not None and other.draw_move is not None:
            self.draw_move = c_option(self.draw_move, other.draw_move, rnd)
        elif self.draw_move is not None:
            self.draw_move = None
        elif other.draw_move is not None:
            if isinstance(self.setup.draw, DealDrawDefGene):
                self.draw_move = other.draw_move
        return self
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[MovesGene, MovesGene, Random], MovesGene]]:
        move_crossovers: list[Callable[[MovesGene, MovesGene, Random], MovesGene]] = [
            lambda me, other, rnd, c=c_option: me._crossover_move(other, rnd, c)
            for c_option in MoveGene._get_crossover_options()
        ]
        move_stack_crossovers: list[Callable[[MovesGene, MovesGene, Random], MovesGene]] = [
            lambda me, other, rnd, c=c_option: me._crossover_move_stack(other, rnd, c)
            for c_option in MoveStackGene._get_crossover_options()
        ]
        draw_crossovers: list[Callable[[MovesGene, MovesGene, Random], MovesGene]] = [
            lambda me, other, rnd, c=c_option: me._crossover_draw(other, rnd, c)
            for c_option in DrawMoveGene._get_crossover_options()
        ]
        return move_crossovers + move_stack_crossovers + draw_crossovers

    @staticmethod
    def _get_mutation_options() -> list[Callable[[MovesGene, Random], MovesGene]]:
        return [
            lambda me, rnd, c=c_option: c(me, MovesGene.get_random(rnd, me.setup), rnd)
            for c_option in MovesGene._get_crossover_options()
        ]

    def _transform_pilenames_(self, rnd: Random, new_setup: SetupGene):
        for move in self.moves:
            move._transform_pilenames_(rnd, new_setup)
        for move_stack in self.move_stacks:
            move_stack._transform_pilenames_(rnd, new_setup)
        if self.draw_move is not None:
            self.draw_move._transform_pilenames_(rnd, new_setup)

class WinGene(GenoType, Reducible):
    def __init__(self, cond: ConditionGene, setup: SetupGene) -> None:
        self.cond = cond
        self.set_setup(setup)
    
    def get_gdl(self) -> str:
        return "$win\n" + self.cond.get_gdl() + "\n"
    
    @staticmethod
    def get_random(rnd: Random, setup: SetupGene|None = None) -> WinGene:
        assert setup is not None
        return WinGene(ConditionGene.get_random(rnd, ConditionGene.CondType.WIN, setup), setup)
    
    def copy(self) -> WinGene:
        return WinGene(self.cond.copy(), self.setup)
    
    def set_setup(self, setup: SetupGene) -> None:
        self.setup = setup
        self.cond.set_setup(setup)
    
    def get_reduced(self: WinGene, rnd: Random|None, iter: int) -> WinGene | None:
        reduced_cond = self.cond.get_reduced(rnd, iter)
        if reduced_cond is None:
            return None
        return WinGene(reduced_cond, self.setup)
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[WinGene, WinGene, Random], WinGene]]:
        return [
            lambda me, other, rnd, c=c_option: WinGene(c(me.cond, other.cond, rnd), me.setup)
            for c_option in ConditionGene._get_crossover_options()
        ]
    
    @staticmethod
    def _get_mutation_options() -> list[Callable[[WinGene, Random], WinGene]]:
        return [
            lambda me, rnd, c=c_option: c(me, WinGene.get_random(rnd, me.setup), rnd)
            for c_option in WinGene._get_crossover_options()
        ]
    
    def _transform_pilenames_(self, rnd: Random, new_setup: SetupGene):
        self.cond._transform_pilenames_(rnd, new_setup)

class SGDLGene(GenoType, Reducible):
    def __init__(self, deck: DeckGene, setup: SetupGene, moves: MovesGene, win: WinGene):
        self.deck = deck
        self.setup = setup
        self.moves = moves
        self.moves.set_setup(setup)
        self.win = win
        self.win.set_setup(setup)
        # check
        Parser.parse(self.get_gdl(), None, False, False)

    def get_gdl_without_name(self) -> str:
        return self.deck.get_gdl() + self.setup.get_gdl() + self.moves.get_gdl() + self.win.get_gdl()
    
    def get_gdl(self) -> str:
        gdl = self.get_gdl_without_name()
        name = self._get_deterministic_name(gdl)
        return name + "\n" + gdl
    
    # TODO from GDL

    @staticmethod
    def get_random(rnd: Random) -> SGDLGene:
        deck = DeckGene.get_random(GenoType.get_rnd(rnd))
        initial = SetupGene.get_random(GenoType.get_rnd(rnd), deck.card_count)
        moves = MovesGene.get_random(GenoType.get_rnd(rnd), initial)
        win = WinGene.get_random(GenoType.get_rnd(rnd), initial)
        return SGDLGene(deck, initial, moves, win)

    def copy(self) -> SGDLGene:
        return SGDLGene(self.deck.copy(), self.setup.copy(), self.moves.copy(), self.win.copy())

    def get_reduced(self, rnd: Random|None, iter: int) -> SGDLGene | None:
        choices = [1, 2]
        if rnd is not None:
            rnd.shuffle(choices)
        else:
            choices = [2, 1] # because it's easier to know if win size is not big enough for iter
        for choice in choices:
            if choice == 1:
                moves = self.moves.get_reduced(rnd, iter)
                if moves is not None:
                    return SGDLGene(self.deck.copy(), self.setup.copy(), moves, self.win.copy())
            elif choice == 2:
                if rnd is not None or iter < self.win.cond.size:
                    win = self.win.get_reduced(rnd, iter)
                else:
                    iter -= self.win.cond.size
                    continue
                if win is not None:
                    return SGDLGene(self.deck.copy(), self.setup.copy(), self.moves.copy(), win)
        return None

    def get_hash(self):
        gdl_without_name = self.get_gdl_without_name()
        return Parser.get_deterministic_hash_from_body(gdl_without_name)
    
    @staticmethod
    def _get_deterministic_name(gdl_without_name: str):
        name_seed = Parser.get_deterministic_hash_from_body(gdl_without_name)
        return GenoType.get_random_name(Random(name_seed)).capitalize()
    
    def _get_all_reductions(self) -> list[SGDLGene]:
        all_reductions = []
        iter = 0
        while True:
            new_gene = self.get_reduced(None, iter)
            iter += 1
            if new_gene is None:
                break
            all_reductions.append(new_gene)
        return all_reductions
    
    def get_reduced_to_core(self, rnd: Random|None, should_log: bool, target_verdict: Verdict, move_count: int = 1000, game_count: int = 10) -> SGDLGene:
        if should_log:
            print(self.get_gdl())
            print("***")
        all_reductions = self._get_all_reductions()
        if rnd is not None:
            rnd.shuffle(all_reductions)
        for reduction in all_reductions:
            gdl = reduction.get_gdl()
            verdict = evaluate_gdl(gdl, False, move_count, game_count)
            if should_log:
                print(f"&&& evaluated {gdl.split()[0]} as {verdict}")
            if verdict == target_verdict:
                return reduction.get_reduced_to_core(rnd, should_log, target_verdict, move_count, game_count)
        return self
    
    def _crossover_deck(self, other: SGDLGene, rnd: Random, c_option: Callable[[DeckGene, DeckGene, Random], DeckGene]) -> SGDLGene:
        self.deck = c_option(self.deck, other.deck, rnd)
        if self.deck.card_count != self.setup.card_count:
            new_setup = self.setup.copy() # to be able to change pilename mappings TODO there is a better way without saving the last setup
            new_setup._adjust_card_count_(self.deck.card_count, rnd)
            self.moves._transform_pilenames_(rnd, new_setup) # in case some piles end up getting removed
            self.win._transform_pilenames_(rnd, new_setup) # in case some piles end up getting removed
            self.setup = new_setup
        return self
    
    def _crossover_setup(self, other: SGDLGene, rnd: Random, c_option: Callable[[SetupGene, SetupGene, Random], SetupGene]) -> SGDLGene:
        self.setup = c_option(self.setup, other.setup, rnd)
        self.moves._transform_pilenames_(rnd, self.setup) # in case some piles end up getting removed/added
        self.win._transform_pilenames_(rnd, self.setup) # in case some piles end up getting removed/added
        self.moves.set_setup(self.setup)
        self.win.set_setup(self.setup)
        return self
    
    def _crossover_moves(self, other: SGDLGene, rnd: Random, c_option: Callable[[MovesGene, MovesGene, Random], MovesGene]) -> SGDLGene:
        self.moves = c_option(self.moves, other.moves, rnd)
        return self
    
    def _crossover_win(self, other: SGDLGene, rnd: Random, c_option: Callable[[WinGene, WinGene, Random], WinGene]) -> SGDLGene:
        self.win = c_option(self.win, other.win, rnd)
        return self
    
    @staticmethod
    def _get_crossover_options() -> list[Callable[[SGDLGene, SGDLGene, Random], SGDLGene]]:
        deck_crossovers: list[Callable[[SGDLGene, SGDLGene, Random], SGDLGene]] = [
            lambda me, other, rnd, c=c_option: me._crossover_deck(other, rnd, c)
            for c_option in DeckGene._get_crossover_options()
        ]
        setup_crossovers: list[Callable[[SGDLGene, SGDLGene, Random], SGDLGene]] = [
            lambda me, other, rnd, c=c_option: me._crossover_setup(other, rnd, c)
            for c_option in SetupGene._get_crossover_options()
        ]
        moves_crossovers: list[Callable[[SGDLGene, SGDLGene, Random], SGDLGene]] = [
            lambda me, other, rnd, c=c_option: me._crossover_moves(other, rnd, c)
            for c_option in MovesGene._get_crossover_options()
        ]
        win_crossovers: list[Callable[[SGDLGene, SGDLGene, Random], SGDLGene]] = [
            lambda me, other, rnd, c=c_option: me._crossover_win(other, rnd, c)
            for c_option in WinGene._get_crossover_options()
        ]
        return deck_crossovers + setup_crossovers + moves_crossovers + win_crossovers

    @staticmethod
    def _get_mutation_options() -> list[Callable[[SGDLGene, Random], SGDLGene]]:
        return [
            lambda me, rnd, c=c_option: c(me, SGDLGene.get_random(rnd), rnd)
            for c_option in SGDLGene._get_crossover_options()
        ]

# Can be used inside mutation/crossover options for printing purposes without disrupting lambda
def print_and_pass(inp: GenoType, additional_info: str=""):
    print(additional_info)
    print(":::::::", inp.get_gdl())
    return inp

if __name__ == "__main__":
    # win_percentages = []
    # exhausted_percentages = []
    trivial_count = 0
    bipolar_count = 0
    impossible_count = 0
    unkonwn_count = 0
    ok_count = 0
    total_count = 10
    import time
    experiment_seed = int(time.time())
    print(f"EXPERIMENT_SEED = {experiment_seed}")
    exper_rnd = Random(experiment_seed)
    import inspect
    print(f"Params:\n***\n{inspect.getsource(Params)}\n***")
    for _ in range(total_count):
        gdl_seed = get_seed(exper_rnd, 1000000000)
        print(f"---\nGDL_SEED={gdl_seed}\n---\n")
        gdl = SGDLGene.get_random(Random(gdl_seed)).get_gdl()
        print(gdl)
        print("-----")
        verdict = evaluate_gdl(gdl, True)
        if verdict == Verdict.UNKNOWN:
            unkonwn_count += 1
        elif verdict == Verdict.IMPOSSIBLE:
            impossible_count += 1
        elif verdict == Verdict.TRIVIAL:
            trivial_count += 1
        elif verdict == Verdict.BIPOLAR:
            bipolar_count += 1
        elif verdict == Verdict.OK:
            ok_count += 1
        else:
            print(f"unknwon verdict: {verdict}")
        print("-----")
    print(f"# trivial: {trivial_count} ({100*trivial_count/total_count}%)")
    print(f"# bipolar: {bipolar_count} ({100*bipolar_count/total_count}%)")
    print(f"# unknwon: {unkonwn_count} ({100*unkonwn_count/total_count}%)")
    print(f"# impossible: {impossible_count} ({100*impossible_count/total_count}%)")
    print(f"# ok: {ok_count} ({100*ok_count/total_count}%)")
    print(f"# total: {total_count}")

# TODO automoves ?