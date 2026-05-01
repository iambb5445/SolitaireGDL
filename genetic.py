from __future__ import annotations
from parser import Parser
from random import Random
from enum import Enum
from base import Suit, Stack
from abc import ABC, abstractmethod
from typing import Sequence, Type, Callable, TypeVar

def coin_flip(rnd: Random) -> bool:
    return rnd.randint(0, 1) == 0

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
    MAX_GLOBAL_COND_DEPTH = 0 #0-based
    MAX_COND_BRANCH = 2
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
    

class MaxTriesReachedException(Exception):
    pass

class MutationUnavailableException(Exception):
    pass

class CrossoverUnavailableException(Exception):
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
        mutation_options = self.__class__.get_mutation_options()
        if len(mutation_options) == 0:
            raise MutationUnavailableException(str(self.__class__) + self.get_gdl())
        return rnd.choice(mutation_options)(self, rnd)
    
    @staticmethod
    def get_mutation_options() -> list[Callable[[G, Random], G]]:
        raise NotImplementedError
    
    def crossover(self: G, other: G, rnd: Random) -> G:
        crossover_options = self.__class__.get_crossover_options()
        if len(crossover_options) == 0:
            raise CrossoverUnavailableException(str(self.__class__) + self.get_gdl())
        return rnd.choice(crossover_options)(self.copy(), other.copy(), rnd)
    
    @staticmethod
    def get_crossover_options() -> list[Callable[[G, G, Random], G]]:
        raise NotImplementedError
    
    @staticmethod
    def get_rnd(rnd: Random) -> Random:
        return Random(rnd.randint(0, 1000000000))
    
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
            suits = rnd.choice([
                ["SPADES"], ["SPADES", "HEARTS"], ["SPADES", "CLUBS"],
                ["SPADES", "HEARTS", "CLUBS", "DIAMONDS"]
            ])
            deck = DeckGene(count, suits, None)
            if deck.card_count <= Params.MAX_CARD_COUNT:
                return deck
        raise MaxTriesReachedException

    def copy(self) -> DeckGene:
        return DeckGene(self.count, [suit for suit in self.suits], self.ranks if self.ranks is None else [rank for rank in self.ranks])
    
    @staticmethod
    def get_crossover_options() -> list[Callable[[DeckGene, DeckGene, Random], DeckGene]]:
        return [
            lambda me, other, rnd: DeckGene(other.count, me.suits, me.ranks),
            lambda me, other, rnd: DeckGene(me.count, other.suits, me.ranks),
            lambda me, other, rnd: DeckGene(me.count, me.suits, other.ranks),
        ]

    @staticmethod
    def get_mutation_options() -> list[Callable[[DeckGene, Random], DeckGene]]:
        return [lambda me, rnd: DeckGene.get_random(rnd)] + [
            lambda me, rnd: c_option(me.copy(), DeckGene.get_random(rnd), rnd)
            for c_option in DeckGene.get_crossover_options()
        ]

class DealDrawDefGene(GenoType):
    def __init__(self, card_count: int, draw_to: list[str], draw_to_options: list[str]) -> None:
        self.card_count = card_count
        self.draw_to = draw_to
        self.draw_to_options = draw_to_options
    
    def get_gdl(self) -> str:
        return f"DRAW {self.card_count} DEAL {GenoType.list_to_gdl(self.draw_to)}\n"
    
    @staticmethod
    def get_random(rnd: Random, card_count: int = 0, pilenames: list[str] = []) -> DealDrawDefGene:
        draw_to = [name for name in rnd.sample(pilenames, k=rnd.randint(1, len(pilenames)))]
        return DealDrawDefGene(card_count, draw_to, pilenames)

    def copy(self) -> DealDrawDefGene:
        return DealDrawDefGene(self.card_count, [pile for pile in self.draw_to], self.draw_to_options)

    @staticmethod
    def get_crossover_options() -> list[Callable[[DealDrawDefGene, DealDrawDefGene, Random], DealDrawDefGene]]:
        return [
            lambda me, other, rnd: DealDrawDefGene(me.card_count, other.draw_to, me.draw_to_options),
        ]

    @staticmethod
    def get_mutation_options() -> list[Callable[[DealDrawDefGene, Random], DealDrawDefGene]]:
        return [lambda me, rnd: DealDrawDefGene.get_random(rnd, me.card_count, me.draw_to_options)] + [
            lambda me, rnd: c_option(me.copy(), DealDrawDefGene.get_random(rnd, me.card_count, me.draw_to_options), rnd)
            for c_option in DealDrawDefGene.get_crossover_options()
        ]

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
    def get_crossover_options() -> list[Callable[[RotateDrawDefGene, RotateDrawDefGene, Random], RotateDrawDefGene]]:
        return [
            lambda me, other, rnd: RotateDrawDefGene(me.card_count, other.draw_count, me.display_count, me.redeal_count),
            lambda me, other, rnd: RotateDrawDefGene(me.card_count, me.draw_count, other.display_count, me.redeal_count),
            lambda me, other, rnd: RotateDrawDefGene(me.card_count, me.draw_count, me.display_count, other.redeal_count),
        ]
    
    @staticmethod
    def get_mutation_options() -> list[Callable[[RotateDrawDefGene, Random], RotateDrawDefGene]]:
        return [lambda me, rnd: RotateDrawDefGene.get_random(rnd, me.card_count)] + [
            lambda me, rnd: c_option(me.copy(), RotateDrawDefGene.get_random(rnd, me.card_count), rnd)
            for c_option in RotateDrawDefGene.get_crossover_options()
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
        if is_card_count_exact:
            counts = [count for count in GenoType.get_random_numbers(rnd, card_count, rnd.randint(1, Params.MAX_PILE_REPEAT_COUNT), True) if count > 0]
        else:
            counts = [rnd.randint(0, Params.MAX_CARD_IN_PILE)
                  for i in range(rnd.randint(1, Params.MAX_PILE_REPEAT_COUNT))]
            for i in range(len(counts)):
                if counts[i] > card_count:
                    counts[i] = card_count # TODO distribute the difference
                    card_count = 0
                    counts = counts[:i+1]
                    break
                card_count -= counts[i]
        faces = PileDefGene.get_random_faces(counts, rnd)
        return PileDefGene(pilename, counts, faces)
    
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
    
    def _redo_card_count_(self, card_count: int, rnd: Random) -> PileDefGene:
        counts = []
        while sum(counts) < card_count:
            counts.append(rnd.randint(0, Params.MAX_CARD_IN_PILE))
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
    def get_crossover_options() -> list[Callable[[PileDefGene, PileDefGene, Random], PileDefGene]]:
        # in theory, this is only card on the same card_counts. If not, we want to keep the card count the same
        return [
            lambda me, other, rnd: PileDefGene(me.pilename, other.counts, me.faces)._redo_card_count_(me.card_count, rnd), # TODO find a nicer way to adjust counts without overriding them
            lambda me, other, rnd: PileDefGene(me.pilename, me.counts, other.faces)._adjust_faces_(rnd),
        ]
    
    @staticmethod
    def get_mutation_options() -> list[Callable[[PileDefGene, Random], PileDefGene]]:
        return [
            lambda me, rnd: PileDefGene.get_random(rnd, me.card_count, True, []),
            lambda me, rnd: me._redo_card_count_(me.card_count, rnd),
            lambda me, rnd: me._redo_faces_(rnd),
        ]
        # similar results, but more complicated and also a bit biased
        return [lambda me, rnd: PileDefGene.get_random(rnd, me.card_count, True, [])] + [
            lambda me, rnd: c_option(me.copy(), PileDefGene.get_random(rnd, me.card_count, True, []), rnd)
            for c_option in PileDefGene.get_crossover_options()
        ]
    
class SetupGene(GenoType):
    def __init__(self, draw: DealDrawDefGene|RotateDrawDefGene|None, piles: list[PileDefGene]) -> None:
        self.draw = draw
        self.piles = piles
        self.card_count = 0 if self.draw is None else self.draw.card_count + sum([pile.card_count for pile in self.piles])
    
    def get_gdl(self) -> str:
        return "$initial\n" + \
            ("" if self.draw is None else self.draw.get_gdl()) + \
            "".join([pile.get_gdl() for pile in self.piles])
    
    def get_pilenames(self) -> list[str]:
        return [pile.pilename for pile in self.piles]
    
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
                draw = DealDrawDefGene.get_random(rnd, card_count, [pile.pilename for pile in piles])
                card_count -= draw.card_count
            elif choice == 1 and len(piles) > 0:
                draw = RotateDrawDefGene.get_random(rnd, card_count)
                card_count -= draw.card_count
            else: # four times the chance
                piles.append(PileDefGene.get_random(rnd, card_count, False, special_pilenames))
                if piles[-1].pilename in special_pilenames:
                    special_pilenames.remove(piles[-1].pilename)
                card_count -= piles[-1].card_count
        return SetupGene(draw, piles)
    
    def copy(self) -> SetupGene:
        return SetupGene(self.draw if self.draw is None else self.draw.copy(), [pile.copy() for pile in self.piles])
    
    def _adjust_card_count_(self, intended_card_count: int, rnd: Random) -> SetupGene:
        current_card_counts = [pile.card_count for pile in self.piles] + [] if self.draw is None else [self.draw.card_count]
        card_counts = GenoType.get_random_numbers(rnd, intended_card_count, len(current_card_counts), True)
        for i in range(len(self.piles)):
            # possibly, this won't be in Params range anymore for pile sizes
            self.piles[i]._redo_card_count_(card_counts[i], rnd)
        self.piles = [pile for pile in self.piles if pile.card_count != 0]
        if self.draw is not None:
            self.draw.card_count = card_counts[-1]
            if card_counts[-1] == 0:
                self.draw = None
        self.card_count = intended_card_count
        return self
    
    def _mutate_a_pile_(self, rnd: Random) -> SetupGene:
        pile_index = rnd.randint(0, len(self.piles) + (0 if self.draw is None else 2))
        if pile_index < len(self.piles):
            self.piles[pile_index].mutate(rnd)
        elif pile_index == len(self.piles):
            assert self.draw is not None
            if isinstance(self.draw, RotateDrawDefGene):
                self.draw = DealDrawDefGene.get_random(rnd, self.draw.card_count, self.get_pilenames())
            else:
                self.draw = RotateDrawDefGene.get_random(rnd, self.draw.card_count)
        else:
            assert self.draw is not None
            self.draw.mutate(rnd)
        return self

    def _add_a_pile_(self, rnd: Random)-> SetupGene:
        if self.draw is None and coin_flip(rnd):
            if coin_flip(rnd):
                self.draw = DealDrawDefGene.get_random(rnd, self.card_count//2, self.get_pilenames())
            else:
                self.draw = RotateDrawDefGene.get_random(rnd, self.card_count//2)
        else:
            special_pilenames = [name for name in Params.SPECIAL_PILENAMES if name not in self.get_pilenames()]
            self.piles.append(PileDefGene.get_random(rnd, self.card_count//2, False, special_pilenames)) # //2 is a rough estimate
        self._adjust_card_count_(self.card_count, rnd)
        return self

    def _remove_a_pile_(self, rnd: Random) -> SetupGene:
        if self.draw is not None and (coin_flip(rnd) or len(self.piles) == 0):
            self.draw = None
        else:
            self.piles.pop(rnd.randint(0, len(self.piles) - 1))
        self._adjust_card_count_(self.card_count, rnd)
        return self
    
    @staticmethod
    def get_crossover_options() -> list[Callable[[SetupGene, SetupGene, Random], SetupGene]]:
        # there should be no need for adjustments, becuase other should have the same card count
        return [
            lambda me, other, rnd: SetupGene(other.draw, me.piles)._adjust_card_count_(me.card_count, rnd),
            lambda me, other, rnd: SetupGene(me.draw, other.piles)._adjust_card_count_(me.card_count, rnd),
        ]
    
    @staticmethod
    def get_mutation_options() -> list[Callable[[SetupGene, Random], SetupGene]]:
        return [
            lambda me, rnd: SetupGene.get_random(rnd, me.card_count),
            lambda me, rnd: me.copy()._mutate_a_pile_(rnd),
            lambda me, rnd: me.copy()._add_a_pile_(rnd),
            lambda me, rnd: me.copy()._remove_a_pile_(rnd),
        ] + [
            lambda me, rnd: c_option(me.copy(), SetupGene.get_random(rnd, me.card_count), rnd)
            for c_option in SetupGene.get_crossover_options()
        ]

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
        def get_crossover_options() -> list[Callable[[ConditionGene.T, ConditionGene.T, Random], ConditionGene.T]]:
            return [
                lambda me, other, rnd: me,
                lambda me, other, rnd: other,
            ]

    class Op(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.Op:
            return ConditionGene.Op(rnd.choice([ "==", ">", "<", ">=", "<="]))
        
        @staticmethod
        def get_mutation_options() -> list[Callable[[ConditionGene.Op, Random], ConditionGene.Op]]:
            return [lambda me, rnd: ConditionGene.Op.get_random(rnd)]
    
    class Count(Arg):
        @staticmethod
        def get_random(rnd: Random, max: int = Params.MAX_CARD_IN_COND) -> ConditionGene.Count:
            return ConditionGene.Count(str(rnd.randint(0, max)))
        
        @staticmethod
        def get_mutation_options() -> list[Callable[[ConditionGene.Count, Random], ConditionGene.Count]]:
            return [lambda me, rnd: ConditionGene.Count.get_random(rnd)]
    
    class Suits(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.Suits:
            all_suits = ["SPADES", "HEARTS", "CLUBS", "DIAMONDS"]
            suits: list[str] = rnd.sample(all_suits, rnd.randint(1, len(all_suits)))
            return ConditionGene.Suits("{" + ", ".join(suits) + "}")
        
        @staticmethod
        def get_mutation_options() -> list[Callable[[ConditionGene.Suits, Random], ConditionGene.Suits]]:
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
        def get_mutation_options() -> list[Callable[[ConditionGene.Ranks, Random], ConditionGene.Ranks]]:
            return [lambda me, rnd: ConditionGene.Ranks.get_random(rnd)]
    
    class Pileset(Arg):
        def __init__(self, value: str, get_options: Callable[[], list[str]]) -> None:
            super().__init__(value)
            self.get_options = get_options
        
        @staticmethod
        def get_random(rnd: Random, get_options: Callable[[], list[str]] = lambda: []) -> ConditionGene.Pileset:
            return ConditionGene.Pileset(rnd.choice(get_options()), get_options)
        
        @staticmethod
        def get_mutation_options() -> list[Callable[[ConditionGene.Pileset, Random], ConditionGene.Pileset]]:
            return [lambda me, rnd: ConditionGene.Pileset.get_random(rnd, me.get_options)]
        
        def copy(self: ConditionGene.Pileset) -> ConditionGene.Pileset:
            return ConditionGene.Pileset(self.value, self.get_options)

    class RankCond(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.RankCond:
            return ConditionGene.RankCond(rnd.choice(["ascending", "descending", "equal", "add_13", "add_14"]))
        
        @staticmethod
        def get_mutation_options() -> list[Callable[[ConditionGene.RankCond, Random], ConditionGene.RankCond]]:
            return [lambda me, rnd: ConditionGene.RankCond.get_random(rnd)]
    
    class SuitCond(Arg):
        @staticmethod
        def get_random(rnd: Random) -> ConditionGene.SuitCond:
            return ConditionGene.SuitCond(rnd.choice(["alternate_color", "match_color", "match"]))
        
        @staticmethod
        def get_mutation_options() -> list[Callable[[ConditionGene.SuitCond, Random], ConditionGene.SuitCond]]:
            return [lambda me, rnd: ConditionGene.SuitCond.get_random(rnd)]

    def __init__(self, root: str, root_args: list[tuple[Arg, int, int]], subconds: Sequence[ConditionGene],
                 type: ConditionGene.CondType, get_pileset: Callable[[], list[str]]) -> None:
        self.root = root
        self.subconds = subconds
        self.root_args = root_args
        self.type = type
        self.get_pileset = get_pileset
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
    def get_random_base_condition(rnd: Random, type: CondType, get_pileset: Callable[[], list[str]]) -> ConditionGene:
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
            check_arg(base, i, "<pileset>", lambda: ConditionGene.Pileset.get_random(rnd, get_pileset))
            check_arg(base, i, "<rankcond>", lambda: ConditionGene.RankCond.get_random(rnd))
            check_arg(base, i, "<suitcond>", lambda: ConditionGene.SuitCond.get_random(rnd))
        return ConditionGene(base, args, [], type, get_pileset)

    @staticmethod
    def get_random(rnd: Random, type: CondType = CondType.MOVE, get_pileset: Callable[[], list[str]] = lambda: [], exclude: str|None = None, depth: int = 0) -> ConditionGene:
        max_depth = Params.MAX_COND_DEPTH if type != ConditionGene.CondType.GLOBAL else Params.MAX_GLOBAL_COND_DEPTH
        choice = rnd.randint(0, 4) if depth < max_depth else 0
        if choice in [0, 1]:
            return ConditionGene.get_random_base_condition(rnd, type, get_pileset)
        root = "AND" if (choice == 2 or exclude == "OR") else "OR"
        exclude = root if Params.SIMPLE_CONDITION else None
        subcount = rnd.randint(2, Params.MAX_COND_BRANCH)
        return ConditionGene(root, [], [
            ConditionGene.get_random(rnd, type, get_pileset, exclude, depth+1)
            for _ in range(subcount)], type, get_pileset)
    
    def copy(self) -> ConditionGene:
        return ConditionGene(self.root, [(arg.copy(), s, e) for arg, s, e in self.root_args], [subcond.copy() for subcond in self.subconds], self.type, self.get_pileset)
    
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
        self.get_pileset = other.get_pileset
        return self
    
    def _mutate_single_(self, rnd: Random) -> ConditionGene:
        if not self.is_base():
            return rnd.choice(self.subconds)._mutate_single_(rnd)
        if len(self.root_args) == 0 or coin_flip(rnd):
            return self._become_(ConditionGene.get_random_base_condition(rnd, self.type, self.get_pileset))
        arg_index = rnd.randint(0, len(self.root_args) - 1)
        arg, s, e = self.root_args[arg_index]
        self.root_args[arg_index] = (arg.mutate(rnd), s, e)
        return self
    
    def _add_one_condition_(self, rnd: Random, exclude: str|None, depth: int = 0) -> ConditionGene:
        if self.is_base():
            if depth < Params.MAX_COND_DEPTH:
                copy = self.copy()
                root = "AND" if (coin_flip(rnd) or exclude == "OR") else "OR"
                exclude = root if Params.SIMPLE_CONDITION else None
                self._become_(ConditionGene(root, [], [
                    copy,
                    ConditionGene.get_random(rnd, self.type, self.get_pileset, exclude, depth+1),
                ], self.type, self.get_pileset))
            # else: nothing we can do but to retry and end up in another branch
        else: # AND or OR
            if depth == (Params.MAX_COND_DEPTH - 1) or (coin_flip(rnd) == 0 and len(self.subconds) < Params.MAX_COND_BRANCH):
                if len(self.subconds) < Params.MAX_COND_BRANCH:
                    exclude = self.root if Params.SIMPLE_CONDITION else None
                    self.subconds = [subcond for subcond in self.subconds] + [ConditionGene.get_random(rnd, self.type, self.get_pileset, exclude, depth+1)]
                # else: both max depth and max branch is reached, adding conditions is not possible
            else:
                exclude = self.root if Params.SIMPLE_CONDITION else None
                rnd.choice(self.subconds)._add_one_condition_(rnd, exclude, depth + 1)
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

    @staticmethod
    def get_crossover_options() -> list[Callable[[ConditionGene, ConditionGene, Random], ConditionGene]]:
        # TODO
        return [
            lambda me, other, rnd: ConditionGene(me.root, me.root_args, me.subconds, me.type, me.get_pileset)
        ]
    
    @staticmethod
    def get_mutation_options() -> list[Callable[[ConditionGene, Random], ConditionGene]]:
        return [
            lambda me, rnd: me._mutate_single_(rnd),
            lambda me, rnd: me._add_one_condition_(rnd, None, 0),
            lambda me, rnd: me._remove_one_condition_(rnd)
        ]

class MoveGene(GenoType, Reducible):
    def __init__(self, starts: list[str], ends: list[str], cond: ConditionGene) -> None:
        self.starts = starts
        self.ends = ends
        self.cond = cond

    def get_gdl(self) -> str:
        return f"MOVE {GenoType.list_to_gdl(self.starts)} {GenoType.list_to_gdl(self.ends)}\n" + \
            self.cond.get_gdl() + "\n"
    
    @staticmethod
    def get_random(rnd: Random, starts: list[str] = [], ends: list[str] = [], get_pilenames: Callable[[], list[str]] = lambda: []) -> MoveGene:
        return MoveGene(starts, ends, ConditionGene.get_random(rnd, ConditionGene.CondType.MOVE, get_pilenames))
    
    def copy(self) -> MoveGene:
        return MoveGene([pile for pile in self.starts], [pile for pile in self.ends], self.cond.copy())
    
    def get_reduced(self: MoveGene, rnd: Random|None, iter: int) -> MoveGene | None:
        reduced_cond = self.cond.get_reduced(rnd, iter)
        if reduced_cond is None:
            return None
        return MoveGene([pile for pile in self.starts], [pile for pile in self.ends], reduced_cond)
    
    @staticmethod
    def get_crossover_options() -> list[Callable[[MoveGene, MoveGene, Random], MoveGene]]:
        return [

        ]

    @staticmethod
    def get_mutation_options() -> list[Callable[[MoveGene, Random], MoveGene]]:
        return []
    
class MoveStackGene(GenoType, Reducible):
    def __init__(self, starts: list[str], ends: list[str], cond: ConditionGene) -> None:
        self.starts = starts
        self.ends = ends
        self.cond = cond

    def get_gdl(self) -> str:
        return f"MOVE_STACK {GenoType.list_to_gdl(self.starts)} {GenoType.list_to_gdl(self.ends)}\n" + \
            self.cond.get_gdl() + "\n"
    
    @staticmethod
    def get_random(rnd: Random, starts: list[str] = [], ends: list[str] = [], get_pilenames: Callable[[], list[str]] = lambda: []) -> MoveStackGene:
        return MoveStackGene(starts, ends, ConditionGene.get_random(rnd, ConditionGene.CondType.MOVE_STACK, get_pilenames))
    
    def copy(self) -> MoveStackGene:
        return MoveStackGene([pile for pile in self.starts], [pile for pile in self.ends], self.cond.copy())
    
    def get_reduced(self: MoveStackGene, rnd: Random|None, iter: int) -> MoveStackGene | None:
        reduced_cond = self.cond.get_reduced(rnd, iter)
        if reduced_cond is None:
            return None
        return MoveStackGene([pile for pile in self.starts], [pile for pile in self.ends], reduced_cond)

class DrawMoveGene(GenoType, Reducible):
    def __init__(self, cond: ConditionGene) -> None:
        self.cond = cond

    def get_gdl(self) -> str:
        return "DRAW\n" + self.cond.get_gdl() + "\n"
    
    @staticmethod
    def get_random(rnd: Random, get_pilenames: Callable[[], list[str]] = lambda: []) -> DrawMoveGene:
        return DrawMoveGene(ConditionGene.get_random(rnd, ConditionGene.CondType.GLOBAL, get_pilenames))
    
    def copy(self) -> DrawMoveGene:
        return DrawMoveGene(self.cond.copy())
    
    def get_reduced(self: DrawMoveGene, rnd: Random|None, iter: int) -> DrawMoveGene | None:
        reduced_cond = self.cond.get_reduced(rnd, iter)
        if reduced_cond is None:
            return None
        return DrawMoveGene(reduced_cond)
    
class MovesGene(GenoType, Reducible):
    def __init__(self, moves: list[MoveGene], move_stacks: list[MoveStackGene], draw_move: DrawMoveGene|None) -> None:
        self.moves = moves
        self.move_stacks = move_stacks
        self.draw_move = draw_move
    
    def get_gdl(self) -> str:
        return "$moves\n" + \
            "".join([move.get_gdl() for move in self.moves]) + \
            "".join([move_stack.get_gdl() for move_stack in self.move_stacks]) + \
            ("" if self.draw_move is None else self.draw_move.get_gdl())
    
    @staticmethod
    def get_action_ends(rnd: Random, end_options: list[tuple[str, str]]):
        start, end = rnd.choice(end_options)
        starts = [start]
        ends = [end]
        end_options.remove((start, end))
        expand_action = rnd.randint(0, 4) # 2 chance of no expand
        if expand_action == 0 or expand_action == 4:
            extra_starts = [s for (s, e) in end_options if e == end]
            starts += rnd.sample(extra_starts, rnd.randint(0, len(extra_starts))) # 0 is an option
        elif expand_action == 1 or expand_action == 4:
            extra_ends = [e for (s, e) in end_options if s == start]
            ends += rnd.sample(extra_ends, rnd.randint(0, len(extra_ends))) # 0 is an option
        for s in starts:
            for e in ends:
                if s != start or e != end:
                    end_options.remove((s, e)) # we can also not remove duplicates
        return starts, ends
    
    @staticmethod
    def get_random(rnd: Random, get_pilenames: Callable[[], list[str]] = lambda: [], draw: DealDrawDefGene|RotateDrawDefGene|None = None) -> MovesGene:
        # EXCLUDE: more than 2 move or move_stack
        pilenames = get_pilenames()
        pilenames_or_D = pilenames + (["DRAW"] if isinstance(draw, RotateDrawDefGene) else [])
        move_options = [(pilename_or_D, pilename) for pilename in pilenames for pilename_or_D in pilenames_or_D]
        move_stack_options = [(pilename, pilename2) for pilename2 in pilenames for pilename in pilenames]
        while True:
            move_count = rnd.randint(0, Params.MAX_MOVE_COUNT)
            move_stack_count = rnd.randint(0, Params.MAX_MOVE_STACK_COUNT)
            if move_count + move_stack_count != 0 or Params.MAX_MOVE_COUNT + Params.MAX_MOVE_STACK_COUNT == 0:
                break
        moves, move_stacks = [], []
        for _ in range(move_count):
            if len(move_options) > 0:
                starts, ends = MovesGene.get_action_ends(rnd, move_options)
                moves.append(MoveGene.get_random(rnd, starts, ends, get_pilenames))
        for _ in range(move_stack_count):
            if len(move_stack_options) > 0:
                starts, ends = MovesGene.get_action_ends(rnd, move_stack_options)
                move_stacks.append(MoveStackGene.get_random(rnd, starts, ends, get_pilenames))
        draw_move = None
        if isinstance(draw, DealDrawDefGene) and coin_flip(rnd):
            draw_move = DrawMoveGene.get_random(rnd, get_pilenames)
        return MovesGene(moves, move_stacks, draw_move)
    
    def copy(self) -> MovesGene:
        return MovesGene(
            [move.copy() for move in self.moves],
            [move_stack.copy() for move_stack in self.move_stacks],
            self.draw_move if self.draw_move is None else self.draw_move.copy()
        )
    
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

class WinGene(GenoType, Reducible):
    def __init__(self, cond: ConditionGene) -> None:
        self.cond = cond
    
    def get_gdl(self) -> str:
        return "$win\n" + self.cond.get_gdl() + "\n"
    
    @staticmethod
    def get_random(rnd: Random, get_pilenames: Callable[[], list[str]] = lambda: []) -> WinGene:
        return WinGene(ConditionGene.get_random(rnd, ConditionGene.CondType.WIN, get_pilenames))
    
    def copy(self) -> WinGene:
        return WinGene(self.cond.copy())
    
    def get_reduced(self: WinGene, rnd: Random|None, iter: int) -> WinGene | None:
        reduced_cond = self.cond.get_reduced(rnd, iter)
        if reduced_cond is None:
            return None
        return WinGene(reduced_cond)
    
    def _crossover_(self, other: WinGene, rnd: Random) -> WinGene:
        self.cond.crossover(other.cond, rnd)
        return self
    
    def _mutate_(self, rnd: Random) -> WinGene:
        self.cond.mutate(rnd)
        return self
    
    @staticmethod
    def get_crossover_options() -> list[Callable[[WinGene, WinGene, Random], WinGene]]:
        return [lambda me, other, rnd: me._crossover_(other, rnd)]
    
    @staticmethod
    def get_mutation_options() -> list[Callable[[WinGene, Random], WinGene]]:
        return [lambda me, rnd: me.mutate(rnd)]

class SGDLGene(GenoType, Reducible):
    def __init__(self, deck: DeckGene, setup: SetupGene, moves: MovesGene, win: WinGene):
        self.deck = deck
        self.setup = setup
        self.moves = moves
        self.win = win
        # check
        Parser.parse(self.get_gdl(), None, False, False)

    def get_gdl(self) -> str:
        gdl = self.deck.get_gdl() + self.setup.get_gdl() + self.moves.get_gdl() + self.win.get_gdl()
        name = self.get_deterministic_name(gdl)
        return name + "\n" + gdl
    
    # TODO from GDL

    @staticmethod
    def get_random(rnd: Random) -> SGDLGene:
        deck = DeckGene.get_random(GenoType.get_rnd(rnd))
        initial = SetupGene.get_random(GenoType.get_rnd(rnd), deck.card_count)
        moves = MovesGene.get_random(GenoType.get_rnd(rnd), initial.get_pilenames, initial.draw)
        win = WinGene.get_random(GenoType.get_rnd(rnd), initial.get_pilenames)
        gdl = ""
        gdl = SGDLGene.get_deterministic_name(gdl) + "\n" + gdl
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
    
    @staticmethod
    def get_deterministic_name(gdl_without_name: str):
        gdl = Parser.remove_comments(gdl_without_name)
        name_seed = 0
        for c in gdl:
            name_seed *= 256
            name_seed += ord(c)
            name_seed %= 1000000007
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

from enum import StrEnum
from utility import Logger
from simulate_many import simulate_for_player, players
class Verdict(StrEnum):
    UNKNOWN = "UNKNOWN"
    IMPOSSIBLE = "IMPOSSIBLE"
    TRIVIAL = "TRIVIAL"
    BIPOLAR = "BIPOLAR"
    OK = "OK"

def evaluate_gdl(gdl: str, should_log: bool, max_move_count: int = 1000, game_count: int = 10) -> Verdict:
    logger = Logger(should_log)
    games, move_counts, samples = simulate_for_player(
        game_count, max_move_count, True, gdl, lambda: players["dfs-heuristic"](None),
        0, 0, 0, 0, 1
    )
    wins: list[bool] = [game.is_win() for game in games]
    win_percentage = sum(wins)/len(wins)
    win_move_counts = [move_count for win, move_count in zip(wins, move_counts) if win]
    exhausted = [move_count == max_move_count for move_count in move_counts]
    exhausted_percentage = sum(exhausted)/len(exhausted)
    logger.info("result for " + games[0].name)
    logger.info(f"wins: {wins}")
    logger.info(f"win percentage: {win_percentage}, exhausted: {exhausted_percentage}")
    logger.info(f"move counts: {move_counts}")
    logger.info(f"average move count: {sum(move_counts)/len(move_counts)}")
    logger.info(f"win move count: {win_move_counts}")
    logger.info(f"average win move count: {(sum(win_move_counts)/len(win_move_counts)) if len(win_move_counts) > 0 else 'NaN'}")
    # win_percentages.append(win_percentage)
    # exhausted_percentages.append(exhausted_percentage)
    if exhausted_percentage > 0.9:
        verdict = Verdict.UNKNOWN
    elif sum(wins) == 0:
        verdict = Verdict.IMPOSSIBLE
    elif sum(wins) == len(wins) and sum(win_move_counts)/len(win_move_counts) < 20:
        verdict = Verdict.TRIVIAL
    elif sum(win_move_counts)/len(win_move_counts) < 20:
        verdict = Verdict.BIPOLAR
    else:
        verdict = Verdict.OK
    logger.info(f"VERDICT: {str(verdict)}")
    return verdict

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
        gdl_seed = exper_rnd.randint(0, 1000000000)
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