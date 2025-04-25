from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from base import BaseStrEnum, Card, Stack, Suit
from utility import TextUtil

# GENERAL CONDITIONS
# You cannot move a card or a stack containing a card that is face down.
# You cannot move a stack from a draw (deal) pile.
# You cannot move a card to a draw pile.
# Move stack needs the stack to be at least 2 card long (else: ambiguity in interpreting gui and counting the moves, etc, the rest works fine)
# Destination cannot be empty for a destsrc rule

class MathOp(BaseStrEnum):
    EQ = '=='
    GT = '>'
    LT = '<'
    GTE = '>='
    LTE = '<='

class ConditionComponents(ABC):
    pass

class MoveCardComponents(ConditionComponents):
    def __init__(self, source: Card, destination: Stack) -> None:
        self.source = source
        self.destination = destination
    
class MoveStackComponents(MoveCardComponents):
    def __init__(self, stack: list[Card], destination: Stack) -> None:
        source = stack[0]
        super().__init__(source, destination)
        self.stack = stack

class WinCondCompoenents(ConditionComponents):
    def __init__(self) -> None:
        pass

T = TypeVar('T', bound=ConditionComponents, contravariant=True)
class Condition(Generic[T], ABC):
    @abstractmethod
    def evaluate(self, components: T) -> bool:
        raise NotImplementedError

    @abstractmethod
    def summary(self, components: T|None=None) -> str:
        raise NotImplementedError
    
    def TFText(self, components: T|None) -> str:
        if components is None:
            return ''
        elif self.evaluate(components):
            return TextUtil.get_colored_text('[T]', TextUtil.TEXT_COLOR.Green)
        else:
            return TextUtil.get_colored_text('[F]', TextUtil.TEXT_COLOR.Red)

class ConditionTree(Condition[T]):
    def __init__(self) -> None:
        self.subtrees: list[Condition[T]] = []

    def add_subtree(self, subtree: Condition[T]):
        self.subtrees.append(subtree)

    @abstractmethod
    def get_modular_summary(self, components: T|None) -> tuple[str, list]:
        raise NotImplementedError

    def _get_sub_modular_summaries(self, components: T|None) -> list[tuple|str]:
        subs= []
        for subtree in self.subtrees:
            if isinstance(subtree, ConditionTree):
                subs.append(subtree.get_modular_summary(components))
            else:
                subs.append(subtree.summary(components))
        return subs
    
    @staticmethod
    def _index_text(index: list[int]):
        return len(index) * '    ' + '.'.join([str(i) for i in index]) + ('. ' if len(index) != 0 else '')
    
    @staticmethod
    def _inner_summary(subsummaries: str|tuple, index: list[int]) -> str:
        ret = ''
        if isinstance(subsummaries, tuple):
            ret += ConditionTree._index_text(index) + subsummaries[0] + '\n'
            for i, part in enumerate(subsummaries[1]):
                ret += ConditionTree._inner_summary(part, index + [i+1])
            return ret
        return ret + ConditionTree._index_text(index) + subsummaries + '\n'
    
    def summary(self, components: T|None=None) -> str:
        subsummaries = self.get_modular_summary(components)
        return ConditionTree._inner_summary(subsummaries, [])

class AndSubTree(ConditionTree[T]):
    def evaluate(self, components: T) -> bool:
        for subtree in self.subtrees:
            if not subtree.evaluate(components):
                return False
        return True
    
    def get_modular_summary(self, components: T|None) -> tuple[str, list]:
        return ('All of the following should be true: ' + self.TFText(components), super()._get_sub_modular_summaries(components))
    
class OrSubTree(ConditionTree[T]):
    def evaluate(self, components: T) -> bool:
        for subtree in self.subtrees:
            if subtree.evaluate(components):
                return True
        return False
    
    def get_modular_summary(self, components: T|None) -> tuple[str, list]:
        return ('At least one of the following should be true: ' + self.TFText(components), super()._get_sub_modular_summaries(components))
    
class PlainCondition(Condition[T]):
    def summary(self, components: T|None=None) -> str:
        return self.unsigned_summary() + ' ' + self.TFText(components)
    
    @abstractmethod
    def unsigned_summary(self) -> str:
        raise NotImplementedError
    
class MoveStackCondition(PlainCondition[MoveStackComponents]):
    @abstractmethod
    def evaluate(self, components: MoveStackComponents) -> bool:
        raise NotImplementedError
    
class MoveCondition(PlainCondition[MoveCardComponents]):
    @abstractmethod
    def evaluate(self, components: MoveCardComponents) -> bool:
        raise NotImplementedError

class SizeCondition(Condition[T]):
    def __init__(self, math_op: MathOp, threshold: int) -> None:
        self.math_op = math_op
        self.threshold = threshold

    def comp_to_str(self) -> str:
        if self.math_op == MathOp.EQ:
            return f"equal to {self.threshold}"
        elif self.math_op == MathOp.LT:
            return f"less than {self.threshold}"
        elif self.math_op == MathOp.LTE:
            return f"less than or equal to {self.threshold}"
        elif self.math_op == MathOp.GT:
            return f"greater than {self.threshold}"
        elif self.math_op == MathOp.GTE:
            return f"greater than or equal to {self.threshold}"
        else:
            raise Exception(f"MathOperation logic not implemented: {self.math_op}")
    
    def comp(self, val: int):
        if self.math_op == MathOp.EQ:
            return val == self.threshold
        elif self.math_op == MathOp.LT:
            return val < self.threshold
        elif self.math_op == MathOp.LTE:
            return val <= self.threshold
        elif self.math_op == MathOp.GT:
            return val > self.threshold
        elif self.math_op == MathOp.GTE:
            return val >= self.threshold
        else:
            raise Exception(f"MathOperation logic not implemented: {self.math_op}")
        
class SuitCondition(Condition[T]):
    def __init__(self, acceptable_suits: list[Suit]) -> None:
        assert len(acceptable_suits) > 0, 'Cannot create suit condition with no suits'
        self.suits = acceptable_suits

    def comp_to_str(self) -> str:
        if len(self.suits) == 0:
            return f'suit {self.suits[0]}'
        return f'one of the suits {{{", ".join(self.suits)}}}'
    
    def comp(self, suit: Suit) -> bool:
        return suit in self.suits

class RankCondition(Condition[T]):
    def __init__(self, acceptable_ranks: list[int]) -> None:
        self.ranks = acceptable_ranks

    def comp_to_str(self) -> str:
        if len(self.ranks) == 1:
            return f'rank {Card.rank_to_str(self.ranks[0])}'
        return f'one of the ranks {{{", ".join([Card.rank_to_str(rank) for rank in self.ranks])}}}'
    
    def comp(self, rank: int) -> bool:
        return rank in self.ranks
    
class MultiSuitCondition(Condition[T]):
    class MODE(BaseStrEnum):
        ALTERNATE_COL = 'alternate_color'
        MATCH = 'match'

    def __init__(self, mode: MODE) -> None:
        self.mode = mode

    def comp_to_str(self) -> str:
        if self.mode == MultiSuitCondition.MODE.ALTERNATE_COL:
            return "alternating suit colors"
        elif self.mode == MultiSuitCondition.MODE.MATCH:
            return "matching suits"
        raise Exception(f"Suit comparison mode not recognized: {self.mode}")

    def _pair_comp(self, suit1: Suit, suit2: Suit) -> bool:
        if self.mode == MultiSuitCondition.MODE.ALTERNATE_COL:
            return Suit.get_col(suit1) != Suit.get_col(suit2)
        elif self.mode == MultiSuitCondition.MODE.MATCH:
            return Suit.get_col(suit1) == Suit.get_col(suit2)
        raise Exception(f"Suit comparison mode not recognized: {self.mode}")
    
    def comp(self, suits: list[Suit]) -> bool:
        for i in range(1, len(suits)):
            if not self._pair_comp(suits[i - 1], suits[i]):
                return False
        return True
    
class MultiRankCondition(Condition[T]):
    class MODE(BaseStrEnum):
        ASC = 'ascending'
        DES = 'descending'

    def __init__(self, mode: MODE) -> None:
        self.mode = mode

    def comp_to_str(self) -> str:
        if self.mode == MultiRankCondition.MODE.ASC:
            # return '[consecutive] [strictly] ascending ranks (no gaps or equals)'
            return '[consecutive] ascending ranks'
        elif self.mode == MultiRankCondition.MODE.DES:
            # return '[consecutive] [strictly] descending ranks (no gaps or equals)'
            return '[consecutive] descending ranks'
        raise Exception(f"Rank comparison mode not recognized: {self.mode}")

    def _pair_comp(self, rank1: int, rank2: int) -> bool:
        if self.mode == MultiRankCondition.MODE.ASC:
            return rank1 + 1 == rank2
        elif self.mode == MultiRankCondition.MODE.DES:
            return rank1 == rank2 + 1
        raise Exception(f"Rank comparison mode not recognized: {self.mode}")
    
    def comp(self, ranks: list[int]) -> bool:
        for i in range(1, len(ranks)):
            if not self._pair_comp(ranks[i - 1], ranks[i]):
                return False
        return True

class DestEmptyCondition(MoveCondition):
    def unsigned_summary(self) -> str:
        return 'destiantion should be empty'

    def evaluate(self, components: MoveCardComponents) -> bool:
        return components.destination.empty()

class DestSizeCondition(SizeCondition, MoveCondition):
    def unsigned_summary(self) -> str:
        return f'destination should have a size {self.comp_to_str()}'

    def evaluate(self, components: MoveCardComponents) -> bool:
        return self.comp(components.destination.len())

class SrcSuitCondition(SuitCondition, MoveCondition):
    def unsigned_summary(self) -> str:
        return f'source should have {self.comp_to_str()}'

    def evaluate(self, components: MoveCardComponents) -> bool:
        return self.comp(components.source.suit)

class SrcRankCondition(RankCondition, MoveCondition):
    def unsigned_summary(self) -> str:
        return f'source should have {self.comp_to_str()}'
    
    def evaluate(self, components: MoveCardComponents) -> bool:
        return self.comp(components.source.rank)

class DestSrcSuitCondition(MultiSuitCondition, MoveCondition):
    def unsigned_summary(self) -> str:
        # return f'destination shouldn\'t be empty and top card of destination and source card should have {self.comp_to_str()}'
        return f'top card of destination and source card should have {self.comp_to_str()}'
    
    def evaluate(self, components: MoveCardComponents) -> bool:
        return components.destination.len() > 0 and self.comp([components.destination.peak().suit, components.source.suit])

class DestSrcRankCondition(MultiRankCondition, MoveCondition):
    def unsigned_summary(self) -> str:
        # return f'destination shouldn\'t be empty and top card of destination and source card should make {self.comp_to_str()}'
        return f'top card of destination and source card should make {self.comp_to_str()}'
    
    def evaluate(self, components: MoveCardComponents) -> bool:
        return components.destination.len() > 0 and self.comp([components.destination.peak().rank, components.source.rank])
    
class StackSuitCondition(MultiSuitCondition, MoveStackCondition):
    def unsigned_summary(self) -> str:
        return f'cards in the stack should have {self.comp_to_str()}'
    
    def evaluate(self, components: MoveStackComponents) -> bool:
        return self.comp([card.suit for card in components.stack])
    
class StackRankCondition(MultiRankCondition, MoveStackCondition):
    def unsigned_summary(self) -> str:
        return f'cards in the stack should have {self.comp_to_str()}'

    def evaluate(self, components: MoveStackComponents) -> bool:
        return self.comp([card.rank for card in components.stack])
    
class StackSizeCondition(SizeCondition, MoveStackCondition):
    def unsigned_summary(self) -> str:
        return f'stack should have a size {self.comp_to_str()}'
    
    def evaluate(self, components: MoveStackComponents) -> bool:
        return self.comp(len(components.stack))