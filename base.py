from __future__ import annotations
from enum import StrEnum, EnumMeta
import random
from abc import ABC, abstractmethod
from diffs import Diffs

# General rules:
# top of a stack of cards always automatically turns face up

class MetaEnum(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True

class BaseStrEnum(StrEnum, metaclass=MetaEnum):
    pass

class Suit(BaseStrEnum):
    Spades = 'S'
    Hearts = 'H'
    Clubs = 'C'
    Diamonds = 'D'
    @staticmethod
    def get_col(suit: Suit):
        if suit in [Suit.Spades, Suit.Clubs]:
            return 'Black'
        elif suit in [Suit.Hearts, Suit.Diamonds]:
            return 'Red'
        else:
            raise Exception(f"Suit color not recognized: {suit}")

class Hashable(ABC):
    MOD = 1000000007

    @abstractmethod
    def get_hash_view(self) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def get_efficient_hash(self) -> int:
        raise NotImplementedError
    
    @staticmethod
    @abstractmethod
    def get_max_efficient_hash() -> int:
        raise NotImplementedError
    
    @staticmethod
    def get_str_hash(s: str) -> int:
        num = 0
        for c in s:
            num *= 256
            num += ord(c)
            num %= Hashable.MOD
        return num

class Viewable(ABC):
    @abstractmethod
    def get_game_view(self) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def get_state_view(self) -> str:
        raise NotImplementedError

class Card(Viewable, Hashable):
    def __init__(self, suit: Suit, rank: int, is_face_down: bool) -> None:
        assert rank >= 1 and rank <= 13
        self.suit = suit
        self.rank = rank
        self.face_down = is_face_down

    def face(self, is_up:bool = True) -> None:
        self.face_down = not is_up

    @staticmethod
    def rank_to_str(value: int) -> str:
        if value == 13:
            return 'K'
        elif value == 12:
            return 'Q'
        elif value == 11:
            return 'J'
        return str(value)
    
    def __str__(self) -> str:
        s = Card.rank_to_str(self.rank) + str(self.suit)
        if self.face_down:
            return f'[{s}]'
        return s
    
    def copy(self) -> Card:
        return Card(self.suit, self.rank, self.face_down)
    
    @staticmethod
    def extract_from_list(target: Card, cards: list[Card], replace: Card|None) -> Card|None: # can be not staticmethod, but doesn't make sense
        for i in range(len(cards)):
            card = cards[i]
            if card.rank == target.rank and card.suit == target.suit: # ignoring face
                card.face_down = target.face_down
                cards.remove(card)
                if replace is not None:
                    cards.insert(i, replace)
                return card
        return None

    def get_game_view(self) -> str:
        if self.face_down:
            return '[?]'
        return str(self)

    def get_state_view(self) -> str:
        return str(self)
    
    def get_hash_view(self) -> str:
        return str(self)
    
    def get_efficient_hash(self) -> int:
        suit_number: int|None =\
            0 if self.suit == Suit.Clubs else\
            1 if self.suit == Suit.Diamonds else\
            2 if self.suit == Suit.Hearts else\
            3 if self.suit == Suit.Spades else None
        assert suit_number is not None, "Suit not found"
        num = suit_number * 13 + (self.rank - 1)
        return (num * 2 + (1 if self.face_down else 0)) % Hashable.MOD
    
    @staticmethod
    def get_max_efficient_hash() -> int:
        return ((3 * 13 + 12) * 2 + 1) % Hashable.MOD

class Deck:
    def __init__(self, times:int=1, suits:list[Suit]|None=None, ranks:list[int]|None=None) -> None:
        is_face_down = True
        self.cards: list[Card] = []
        for _ in range(times):
            for suit in (Suit if suits is None else suits):
                for rank in (range(1, 14) if ranks is None else ranks):
                    self.cards.append(Card(suit, rank, is_face_down))
    
    def shuffle(self, seed:int|None=None) -> None:
        random.Random(seed).shuffle(self.cards)

    def deal(self, num: int):
        ret = self.cards[:num]
        self.cards = self.cards[num:]
        return ret
    
    def extract(self, card: Card) -> Card|None:
        return Card.extract_from_list(card, self.cards, None)
    
    def __str__(self) -> str:
        return ' '.join([str(card) for card in self.cards])
    
    def copy(self) -> Deck:
        deck = Deck(0)
        deck.cards = [card.copy() for card in self.cards]
        return deck
    
class Pile(Viewable, Hashable):
    def __init__(self, cards: list[Card], name: str) -> None:
        self.cards: list[Card] = cards
        self.name = name
    
    def get_all_cards(self) -> list[Card]:
        return self.cards

    @abstractmethod
    def copy(self) -> Pile:
        raise NotImplementedError

    @abstractmethod    
    def diff(self, other: Pile) -> Diffs:
        raise NotImplementedError
    
    def extract(self, card: Card, replace: Card|None) -> Card|None:
        return Card.extract_from_list(card, self.cards, replace)
    
    def get_game_view(self) -> str:
        return ', '.join([card.get_game_view() for card in self.cards])

    def get_state_view(self) -> str:
        return ', '.join([card.get_state_view() for card in self.cards])
    
    def get_hash_view(self) -> str:
        return ', '.join([card.get_hash_view() for card in self.cards])
    
    def get_efficient_hash(self) -> int:
        return self._get_efficient_hash(self.cards)

    @staticmethod
    def _get_efficient_hash(cards: list[Card]) -> int:
        num = 0
        for card in cards:
            num *= Card.get_max_efficient_hash() + 1
            num += card.get_efficient_hash()
            num %= Hashable.MOD
        return num
    
    @staticmethod
    def get_max_efficient_hash() -> int: # todo save this
        num = 0
        for _ in range(100):
            num *= Card.get_max_efficient_hash() + 1
            num += Card.get_max_efficient_hash()
            num %= Hashable.MOD
        return num
    
    def len(self) -> int:
        return len(self.get_all_cards())
    
    def empty(self) -> bool:
        return self.len() == 0
    
    def viewable_len(self) -> int:
        return len(self.cards)

    def gettable(self) -> bool:
        return len(self.cards) > 0

    def get(self) -> Card:
        assert self.gettable(), "Cannot get card from empty pile"
        return self.cards.pop(-1)
    
    def peak(self) -> Card:
        assert self.gettable(), "Cannot peak card from empty pile"
        return self.cards[-1]
    
    def get_tag(self) -> str:
        return self.name
    
class DealPile(Pile):
    def __init__(self, cards: list[Card], target_names: set[str]) -> None:
        super().__init__(cards, 'DRAW')
        self.target_names = target_names

    def get(self) -> Card:
        self.peak().face()
        return super().get()
    
    def diff(self, other: Pile) -> Diffs:
        if not isinstance(other, DealPile):
            return Diffs().add(1, 1)
        diff = Diffs().add(0, 1)
        # TODO this is not completely right. We should get the diff of those piles, not how different the names are
        # the diff should be name invariant
        diff.add_set_diff(self.target_names, other.target_names)
        diff.add_count_diff(self.len(), other.len())
        return diff
    
    def get_game_view(self) -> str:
        return f'Draw Pile (DEAL): {len(self.cards)} cards'

    def get_state_view(self) -> str:
        return f'Draw Pile (DEAL): {super().get_state_view()}'
    
    def get_hash_view(self) -> str:
        return f'Draw Pile (DEAL): {super().get_hash_view()}'
    
    def get_efficient_hash(self) -> int:
        name_hash = Hashable.get_str_hash('Draw Pile (DEAL)')
        return (super().get_efficient_hash() * name_hash + Pile.get_max_efficient_hash()) % Hashable.MOD
    
    def copy(self) -> DealPile:
        cards_copy = [card.copy() for card in self.cards]
        return DealPile(cards_copy, self.target_names)
    
# possibly, RotateDrawPile can be represented using 3 separate piles.
# However, this representation can make things too complicated, since it can't inherit from pile anymore.
# One important difference is that this is a (circular) queue, not a stack.
class RotateDrawPile(Pile):
    def __init__(self, cards: list[Card], draw_count: int, view_count: int|None, max_redeals: int|None) -> None:
        super().__init__([], 'DRAW')
        self.draw_count = draw_count
        self.view_count = view_count
        self.max_redeals = max_redeals
        self.backpile: list[Card] = cards
        self.drawn: list[Card] = []
        self.redeals = 0
        assert draw_count > 0, "In Rotate Draw, draw count should be positive"
        assert view_count is None or view_count > 0, "In Rotate Draw, view count should be positive (or unlimited)"
        assert max_redeals is None or max_redeals >= 0, "In Rotate Draw, max redeals cannot be negative"
        if max_redeals is None and view_count is None:
            print("[Warning] A limited view count with limited redeals can make cards inaccessible")

    def diff(self, other: Pile) -> Diffs:
        if not isinstance(other, RotateDrawPile):
            return Diffs().add(1, 1)
        diff = Diffs().add(0, 1)
        diff.add(1 if self.draw_count != other.draw_count else 0, 1)
        diff.add(1 if self.view_count != other.view_count else 0, 1)
        diff.add(1 if self.max_redeals != other.max_redeals else 0, 1)
        diff.add_count_diff(self.len(), other.len())
        return diff

    def get_all_cards(self) -> list[Card]:
        return self.cards + self.backpile + self.drawn
    
    def extract(self, card: Card, replace: Card|None) -> Card|None:
        ret: Card|None = Card.extract_from_list(card, self.cards, replace)
        if ret is None:
            ret = Card.extract_from_list(card, self.backpile, replace)
        if ret is None:
            ret = Card.extract_from_list(card, self.drawn, replace)
        return ret
    
    def copy(self) -> RotateDrawPile:
        copy = RotateDrawPile([], self.draw_count, self.view_count, self.max_redeals)
        copy.cards = [card.copy() for card in self.cards]
        copy.backpile = [card.copy() for card in self.backpile]
        copy.drawn = [card.copy() for card in self.drawn]
        copy.redeals = self.redeals
        return copy

    def rotate(self, perform: bool = True) -> bool:
        if len(self.backpile) > 0:
            if not perform:
                return True
            for _ in range(min(self.draw_count, len(self.backpile))):
                self.cards.append(self.backpile.pop(0))
                self.cards[-1].face()
                if self.view_count is not None and len(self.cards) > self.view_count:
                    self.drawn.append(self.cards.pop(0))
        elif self.max_redeals is None or self.redeals < self.max_redeals:
            if not perform:
                return True
            self.redeals += 1
            self.backpile = self.drawn + self.cards
            for card in self.backpile:
                card.face(False)
            self.cards = []
            self.drawn = []
        else:
            # print(f"[Warning] Max redeals reached: {self.redeals}/{self.max_redeals} redeals")
            return False
        return True
    
    def get_game_view(self) -> str:
        return f'Draw Pile (ROTATE): {self.len()} cards, {self.redeals}/{self.max_redeals if self.max_redeals is not None else "infinite"} redeals'\
            + f'\nDraw View: {", ".join([card.get_state_view() for card in self.cards])}[top]'
            # + f'\nDraw View: [top]{str(self)}' reversed

    def get_state_view(self) -> str:
        return f'Draw Pile (ROTATE): {self.len()} cards, {self.redeals}/{self.max_redeals if self.max_redeals is not None else "infinite"} redeals'\
            + f'\nBackPile: {", ".join([card.get_state_view() for card in self.backpile])}[top]'\
            + f'\nDraw View: {", ".join([card.get_state_view() for card in self.cards])}[top]'\
            + f'\nDrawn: {", ".join([card.get_state_view() for card in self.drawn])}[top]'
    
    def get_hash_view(self) -> str:
        return f'Draw Pile (ROTATE): {self.len()} cards'\
            + f'\nBackPile: {", ".join([card.get_state_view() for card in self.backpile])}[top]'\
            + f'\nDraw View: {", ".join([card.get_state_view() for card in self.cards])}[top]'\
            + f'\nDrawn: {", ".join([card.get_state_view() for card in self.drawn])}[top]'
    
    def get_efficient_hash(self) -> int:
        name_hash = Hashable.get_str_hash('Draw Pile (ROTATE)')
        num = name_hash
        for pile in [self.backpile, self.cards, self.drawn]:
            num *= Pile.get_max_efficient_hash()
            num += Pile._get_efficient_hash(pile)
            num %= Hashable.MOD
        return num

class Stack(Pile):
    class Face(BaseStrEnum):
        FACE_LAST = 'FACE_LAST'
        FACE_ALL = 'FACE_ALL'
        FACE_ALTERNATE_TOP = 'FACE_ALTERNATE_LAST'
        FACE_HALF = 'FACE_HALF' # TODO make this FACE_SOME_<num>
    
    def __init__(self, cards: list[Card], name:str, ind: int) -> None:
        super().__init__(cards, name)
        self.ind = ind

    def diff(self, other: Pile) -> Diffs:
        if not isinstance(other, Stack):
            return Diffs().add(1, 1)
        diff = Diffs().add(0, 1)
        diff.add_count_diff(self.len(), other.len())
        return diff

    def apply_face(self, face: Face):
        for card in self.cards:
            card.face(False)
        if face == Stack.Face.FACE_ALL:
            for card in self.cards:
                card.face()
        elif face == Stack.Face.FACE_LAST:
            if self.gettable():
                self.peak().face()
        elif face == Stack.Face.FACE_ALTERNATE_TOP:
            should_face = True
            for card in reversed(self.cards):
                if should_face:
                    card.face()
                should_face = not should_face
        elif face == Stack.Face.FACE_HALF:
            for card in self.cards[self.len()//2:]:
                card.face()
        else:
            raise Exception(f"Unknown face {face} for pile {self.get_tag()}")

    def get(self) -> Card:
        ret = super().get()
        if self.gettable():
            self.peak().face()
        return ret
    
    def get_many(self, from_ind: int) -> list[Card]:
        cards = self.peak_many(from_ind)
        self.cards = self.cards[:from_ind]
        if self.gettable():
            self.peak().face()
        return cards
    
    def peak_many(self, from_ind: int) -> list[Card]:
        assert from_ind < self.len(), f"Not enough card to get from index {from_ind}"
        return self.cards[from_ind:]
    
    def pop_from(self, ind:int) -> list[Card]:
        assert ind >= 0 and ind < self.len()
        ret = self.cards[ind:]
        self.cards = self.cards[:ind]
        return ret

    def add(self, cards: list[Card]) -> None:
        self.cards += cards
    
    def copy(self) -> Stack:
        return Stack([card.copy() for card in self.cards], self.name, self.ind)
    
    def get_tag(self) -> str:
        return f'{self.name}{f"[{self.ind}]" if self.ind is not None else ""}'
    
    def get_game_view(self) -> str:
        return f'{self.get_tag()}: {super().get_game_view()}'

    def get_state_view(self) -> str:
        return f'{self.get_tag()}: {super().get_state_view()}'
    
    def get_hash_view(self) -> str:
        return f'{self.get_tag()}: {super().get_hash_view()}'
    
    def get_efficient_hash(self) -> int:
        name_hash = Hashable.get_str_hash(self.name) # NOT TAG, because this is invariant
        return (super().get_efficient_hash() * name_hash + Pile.get_max_efficient_hash()) % Hashable.MOD