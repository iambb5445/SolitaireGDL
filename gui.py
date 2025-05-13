from __future__ import annotations
import pygame
from parser import Parser
import sys
import os
from base import Suit, Card, Pile, RotateDrawPile, DealPile
from abc import ABC, abstractmethod
from game import Game
import math
from utility import Logger

ANIMATION = False
ANIMATION_SPEED = 1000
DELTA_TIME = 1/120.0

def log_valid_actions(game: Game):
    logger = Logger(True)
    valid_actions = game.get_possible_actions(True)
    logger.info(f"{len(valid_actions)} valid actions:")
    for i, valid_action in enumerate(valid_actions):
        logger.info(f"{i}: {valid_action}")

Color = tuple[int, int, int]

class Vec2D:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    @staticmethod
    def from_tuple(val: tuple[int, int]) -> Vec2D:
        return Vec2D(val[0], val[1])

    def add(self, v: Vec2D) -> Vec2D:
        return Vec2D(self.x  + v.x, self.y + v.y)
    
    def sub(self, v: Vec2D) -> Vec2D:
        # return self.add(v.mult(-1)) # alternatively
        return Vec2D(self.x - v.x, self.y - v.y)
    
    def mult(self, scale: float) -> Vec2D:
        return Vec2D(self.x * scale, self.y * scale)
    
    def div(self, scale: float) -> Vec2D:
        # return self.mult(1/scale) # alternatively
        return Vec2D(self.x / scale, self.y / scale)
    
    def pairwise_mult(self, v: Vec2D) -> Vec2D:
        return Vec2D(self.x * v.x, self.y * v.y)
    
    def dot(self, v: Vec2D) -> float:
        return self.x * v.x + self.y * v.y
    
    def magnitude(self) -> float:
        if self.x == 0 or self.y == 0:
            return self.x + self.y # to avoid precison loss
        return math.sqrt(self.dot(self))
    
    def normalize(self) -> Vec2D:
        return self.div(self.magnitude())
    
    def int_tuple(self) -> tuple[int, int]:
        return (round(self.x), round(self.y))
    
    def copy(self) -> Vec2D:
        return Vec2D(self.x, self.y)
    
    def twist(self) -> Vec2D:
        return Vec2D(self.y, self.x)
    
    def min(self, v: Vec2D):
        return Vec2D(min(self.x, v.x), min(self.y, v.y))
    
    def __str__(self) -> str:
        return f'Vec2D({self.x}, {self.y})'

SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
CARD_WIDTH_SCALE = 0.09
OFFSET_SCALE = Vec2D(0.1, 0.08)

class TextureRepo:
    TEX_DIR: str = os.path.join('resources', 'textures')
    card_size: Vec2D
    offset: Vec2D
    card_textures: dict[str, pygame.Surface] = {}
    
    @staticmethod
    def _get_tex(filename: str) -> pygame.Surface:
        return pygame.image.load(os.path.join(TextureRepo.TEX_DIR, filename))

    @staticmethod
    def load_textures():
        suit_to_str = {
            Suit.Clubs: 'C',
            Suit.Diamonds: 'D',
            Suit.Hearts: 'H',
            Suit.Spades: 'S'
        }
        rank_to_str = {1: 'A', 10: 'T', 11: 'J', 12: 'Q', 13: 'K'} | dict([(i, str(i)) for i in range(2, 10)])
        for suit, suit_str in suit_to_str.items():
            for rank, rank_str in rank_to_str.items():
                filename = f'{rank_str}{suit_str}.png'
                TextureRepo.card_textures[Card(suit, rank, False).get_game_view()] = TextureRepo._get_tex(filename)
        sample = Card(Suit.Clubs, 1, True)
        TextureRepo.card_textures[sample.get_game_view()] = TextureRepo._get_tex('1B.png')
        card_width = SCREEN_WIDTH * CARD_WIDTH_SCALE
        card_scale = card_width / TextureRepo.card_textures[sample.get_game_view()].get_width()
        for name, card_tex in TextureRepo.card_textures.items():
            TextureRepo.card_textures[name] = pygame.transform.smoothscale_by(card_tex, card_scale)
        card_height = TextureRepo.card_textures[sample.get_game_view()].get_height()
        TextureRepo.card_size = Vec2D(SCREEN_WIDTH * CARD_WIDTH_SCALE, card_height)
        TextureRepo.offset = TextureRepo.card_size.pairwise_mult(OFFSET_SCALE)

class ColorRepo:
    Green = (150, 250, 50)
    Orange = (200, 100, 0)
    LightGray = (230, 230, 230)

class Graphic(ABC):
    @abstractmethod
    def render(self, screen: pygame.Surface):
        raise NotImplementedError

class GraphicElement:
    def __init__(self, pos: Vec2D, tex: pygame.Surface) -> None:
        self.pos = pos
        self.tex = tex
        self.target_pos = pos

    def move(self, new_pos: Vec2D, instant: bool = False) -> None:
        if ANIMATION and not instant:
            dir = new_pos.sub(self.pos)
            if dir.magnitude() > 5:
                dir = dir.normalize()
                self.pos = self.pos.add(dir.mult(ANIMATION_SPEED * DELTA_TIME))
                return
        self.pos = new_pos.copy()
    
    def render(self, screen: pygame.Surface):
        self.update() # allow elements to change their texture, if needed
        screen.blit(self.tex, self.pos.int_tuple())

    def update(self):
        pass

    def get_size(self) -> Vec2D:
        size = self.tex.get_size()
        return Vec2D(size[0], size[1])
    
    def contains(self, pos: Vec2D) -> bool:
        if pos.x < self.pos.x or pos.x > (self.pos.x + self.get_size().x):
            return False
        if pos.y < self.pos.y or pos.y > (self.pos.y + self.get_size().y):
            return False
        return True

class CardGE(GraphicElement):
    def __init__(self, pos: Vec2D, card: Card) -> None:
        self.card = card
        self.current_tex_str: str = card.get_game_view()
        super().__init__(pos, TextureRepo.card_textures[self.current_tex_str])

    def _retex(self):
        self.current_tex_str = self.card.get_game_view()
        self.tex = TextureRepo.card_textures[self.current_tex_str]
        
    def update(self):
        if self.current_tex_str != self.card.get_game_view():
            self._retex()

class RectGE(GraphicElement):
    def __init__(self, pos: Vec2D, size: Vec2D, color: Color) -> None:
        tex: pygame.Surface = pygame.Surface(size.int_tuple())
        tex.fill(color)
        super().__init__(pos, tex)

class TextGE(GraphicElement):
    def __init__(self, pos: Vec2D, text: str, text_color: Color, font_size: int, rotated:bool=False) -> None:
        font = pygame.font.SysFont('Corbel',font_size)
        tex = font.render(text, False, text_color)
        if rotated:
            tex = pygame.transform.rotate(tex, 90)
        super().__init__(pos, tex)

    @staticmethod
    def biggest_font(available_space: Vec2D, text: str, rotated: bool=False) -> int:
        font_size = 1
        for font_size in range(1, 500):
            text_ge = TextGE(Vec2D(0, 0), text, (0, 0, 0), font_size, rotated)
            text_size = text_ge.tex.get_size()
            if text_size[0] > available_space.x or text_size[1] > available_space.y:
                return font_size - 1
        return 500 # max reached

class LabelGE(RectGE):
    def __init__(self, pos: Vec2D, size: Vec2D, color: Color, text: str, text_color: Color = (0, 0, 0), font_size: int|None=None, rotated:bool=False) -> None:
        super().__init__(pos, size, color)
        available_space = Vec2D.from_tuple(self.tex.get_size()).sub(TextureRepo.offset.mult(0.2))
        font_size = TextGE.biggest_font(available_space, text, rotated)
        text_pos = TextureRepo.offset.mult(0.2)
        if rotated:
            text_tex = TextGE(Vec2D(0, 0), text, text_color, font_size, rotated).tex
            text_pos = text_pos.add(Vec2D(0, self.tex.get_size()[1] - text_tex.get_size()[1] - text_pos.y * 2))
        self.tex.blit(TextGE(Vec2D(0, 0), text, text_color, font_size, rotated).tex, text_pos.int_tuple())

class PileGraphic(Graphic):
    LABEL_SCALE_BY_OFFSET = 3
    CARD_SPACING_BY_OFFSET = 1.5

    def __init__(self, pos: Vec2D, length: int, game_graphic: GameGraphic, pile: Pile, no_label:bool=False) -> None:
        self.pile = pile
        self.pos = pos
        self.length = length
        self.game_graphics = game_graphic
        self.instantiate_vectors()
        self.label_ge = None if no_label else self.initiate_label_ge()
        self.background_ge = RectGE(pos.add(self.label_offset), TextureRepo.card_size.add(self.available), ColorRepo.LightGray)
        self.moving_cards: list[Card] = []

    def instantiate_vectors(self) -> None:
        self.delta_dir = self.get_delta_dir()
        self.label_delta_dir = self.get_label_delta_dir()
        self.label_offset = self.label_delta_dir.mult(PileGraphic.LABEL_SCALE_BY_OFFSET).pairwise_mult(TextureRepo.offset)
        self.label_size = self.label_offset.add(self.label_delta_dir.twist().pairwise_mult(TextureRepo.card_size))
        cards_length = self.length - self.label_offset.magnitude()
        card_offset = self.label_delta_dir.pairwise_mult(TextureRepo.card_size)
        self.available = self.label_delta_dir.mult(cards_length).sub(card_offset)
        if self.available.x < 0 or self.available.y < 0:
            print(f"[Warning] pile created with less available space than card + label: {self.pile.get_tag()}")

    def initiate_label_ge(self) -> LabelGE:
        return LabelGE(self.pos, self.label_size, ColorRepo.Orange, self.pile.get_tag())
        
    @abstractmethod
    def get_delta_dir(self) -> Vec2D:
        raise NotImplementedError
    
    def get_label_delta_dir(self) -> Vec2D:
        return self.get_delta_dir()
    
    @abstractmethod
    def get_size(self) -> Vec2D:
        raise NotImplementedError
    
    def label_contains(self, pos: Vec2D) -> bool:
        if self.label_ge is not None:
            return self.label_ge.contains(pos)
        return False
    
    def cards_contains(self, pos: Vec2D) -> Card|None:
        for card in reversed(self.pile.cards): # top card prioritized
            if self.game_graphics.card_to_graphic[card].contains(pos):
                return card
        return None
    
    def background_contains(self, pos: Vec2D) -> bool:
        return self.background_ge.contains(pos)
    
    def card_is_moving(self, card: Card):
        if ANIMATION:
            self.moving_cards.append(card)
    
    def card_stopped_moving(self, card: Card):
        if ANIMATION:
            self.moving_cards.remove(card)

    def render(self, screen: pygame.Surface):
        card_spacing = self.delta_dir.pairwise_mult(TextureRepo.offset.mult(PileGraphic.CARD_SPACING_BY_OFFSET))
        if self.pile.len() > 1:
            card_spacing = card_spacing.min(self.available.div(self.pile.len() - 1))
        pos = self.pos
        if self.label_ge is not None:
            self.label_ge.move(pos)
            self.label_ge.render(screen)
            pos = pos.add(self.label_size.pairwise_mult(self.label_delta_dir))
        self.background_ge.move(pos)
        self.background_ge.render(screen)
        for card in self.pile.cards:
            card_graphic = self.game_graphics.card_to_graphic[card]
            if card not in self.moving_cards:
                card_graphic.move(pos)
            card_graphic.render(screen)
            pos = pos.add(card_spacing)

class VerticalPileGraphic(PileGraphic):
    def get_delta_dir(self) -> Vec2D:
        return Vec2D(0, 1)
    
    def get_size(self) -> Vec2D:
        return Vec2D(TextureRepo.card_size.x, self.length)

class HorizontalPileGraphic(PileGraphic):
    def initiate_label_ge(self) -> LabelGE:
        return LabelGE(self.pos, self.label_size, ColorRepo.Orange, self.pile.get_tag(), rotated=True)

    def get_delta_dir(self) -> Vec2D:
        return Vec2D(1, 0)
    
    def get_size(self) -> Vec2D:
        return Vec2D(self.length, TextureRepo.card_size.y)
    
class StackedPileGraphic(PileGraphic):
    def __init__(self, pos: Vec2D, game_graphic: GameGraphic, pile: Pile, no_label: bool = False) -> None:
        label_offset = PileGraphic.LABEL_SCALE_BY_OFFSET * TextureRepo.offset.y
        super().__init__(pos, int(label_offset + TextureRepo.card_size.y + 0.999), game_graphic, pile, no_label)
        self.available = Vec2D(0, 0)

    def get_label_delta_dir(self) -> Vec2D:
        return Vec2D(0, 1)

    def get_delta_dir(self) ->Vec2D:
        return Vec2D(0, 0)
    
    def get_size(self) -> Vec2D:
        return Vec2D(TextureRepo.card_size.x, self.length)

class GameGraphic(Graphic):
    def __init__(self, game: Game) -> None:
        self.game = game
        self.card_to_graphic: dict[Card, CardGE] = {}
        self.pile_graphics: dict[Pile, PileGraphic] = {}
        self.render_order: list[Pile] = []
        # self.draw_button: # TODO
        self.initiate()

    # @staticmethod
    # def get_pos(row: int) -> Coord:
    #     height: int = int(TextureRepo.height_offset * (row + 1) + TextureRepo.card_height * row)
    #     width: int = int(TextureRepo.width_offset)
    #     return Coord(width, height)
    
    # assuming:
    # foundation/deal are StackedPileGraphics
    # rotate draw is HorizontalPileGraphics
    # anything else is VerticalPileGraphics
    def get_pile_graphic_groups(self, piles: list[Pile]):
        pile_graphic_groups: dict[type[PileGraphic], list[Pile]] = {
            VerticalPileGraphic: [],
            HorizontalPileGraphic: [],
            StackedPileGraphic: [],
        }
        for pile in piles:
            if isinstance(pile, RotateDrawPile):
                pile_graphic_groups[HorizontalPileGraphic].append(pile)
            elif isinstance(pile, DealPile) or pile.name == 'FOUNDATION':
                pile_graphic_groups[StackedPileGraphic].append(pile)
            else:
                pile_graphic_groups[VerticalPileGraphic].append(pile)
        return pile_graphic_groups

    def initiate(self) -> None:
        for card in self.game.get_all_cards():
            self.card_to_graphic[card] = CardGE(Vec2D(0, 0), card)
        pg_groups = self.get_pile_graphic_groups(self.game.get_all_piles())
        horizontal_width = int((SCREEN_WIDTH - TextureRepo.offset.x * 3) / 2)
        for i, pile in enumerate(pg_groups[HorizontalPileGraphic]):
            if isinstance(pile, RotateDrawPile): # TODO remove this block, this is just for testing purposes
                pile.rotate()
            x = TextureRepo.offset.x + (horizontal_width + TextureRepo.offset.x) * (i % 2)
            y = TextureRepo.offset.y + (TextureRepo.card_size.y + TextureRepo.offset.y) * (i // 2)
            self.pile_graphics[pile] = HorizontalPileGraphic(Vec2D(x, y), horizontal_width, self, pile)
        horizontal_y_consumed = (TextureRepo.card_size.y + TextureRepo.offset.y) * ((len(pg_groups[HorizontalPileGraphic]) + 1) // 2)
        cards_per_row = int((SCREEN_WIDTH - TextureRepo.offset.x) / (TextureRepo.card_size.x + TextureRepo.offset.x))
        one_stacked_y = 0
        for i, pile in enumerate(pg_groups[StackedPileGraphic]):
            x = TextureRepo.offset.x + (TextureRepo.card_size.x + TextureRepo.offset.x) * (i % cards_per_row)
            y = TextureRepo.offset.y + (TextureRepo.card_size.y + TextureRepo.offset.y) * (i // cards_per_row)
            y += horizontal_y_consumed
            self.pile_graphics[pile] = StackedPileGraphic(Vec2D(x, y), self, pile)
            one_stacked_y = self.pile_graphics[pile].get_size().y
        # stacked_y_consumed = (TextureRepo.card_size.y + TextureRepo.offset.y) * ((len(pg_groups[StackedPileGraphic]) + cards_per_row - 1) // cards_per_row) # this assumes label on the right side, not top
        stacked_y_consumed = (one_stacked_y + TextureRepo.offset.y) * ((len(pg_groups[StackedPileGraphic]) + cards_per_row - 1) // cards_per_row)
        vertical_y = horizontal_y_consumed + stacked_y_consumed
        vertical_per_col = (len(pg_groups[VerticalPileGraphic]) + cards_per_row - 1) // cards_per_row
        available_height = (SCREEN_HEIGHT - vertical_y - TextureRepo.offset.y)
        vertical_length = int(available_height / vertical_per_col - TextureRepo.offset.y)
        for i, pile in enumerate(pg_groups[VerticalPileGraphic]):
            x = TextureRepo.offset.x + (TextureRepo.card_size.x + TextureRepo.offset.x) * (i % cards_per_row)
            y = TextureRepo.offset.y + (vertical_length + TextureRepo.offset.y) * (i // cards_per_row)
            y += vertical_y
            self.pile_graphics[pile] = VerticalPileGraphic(Vec2D(x, y), vertical_length, self, pile)
        if ANIMATION:
            self.render_order = [pile for pile in self.pile_graphics.keys()]

    def prioritize_render(self, pile: Pile):
        if ANIMATION:
            self.render_order.remove(pile)
            self.render_order.append(pile)
    
    def render(self, screen: pygame.Surface):
        if ANIMATION:
            for pile in self.render_order:
                self.pile_graphics[pile].render(screen)
        else:
            for pile_graphic in self.pile_graphics.values():
                pile_graphic.render(screen)

    def element_at(self, pos: Vec2D) -> tuple[PileGraphic|None, LabelGE|CardGE|None]:
        for pile_g in self.pile_graphics.values():
            if pile_g.label_contains(pos):
                assert pile_g.label_ge is not None
                return pile_g, pile_g.label_ge
            card = pile_g.cards_contains(pos)
            if card is not None:
                return pile_g, self.card_to_graphic[card]
            if pile_g.background_contains(pos):
                return pile_g, None
        return None, None

if __name__ == '__main__':
    pygame.init()

    sgdl_filename = sys.argv[1]

    game = Parser.from_file(sgdl_filename, 42, True, True)
    
    TextureRepo.load_textures()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(f'Solitaire Game: {game.name}')
    pygame.font.init()
    game_graphic = GameGraphic(game)
    running = True
    button = LabelGE(Vec2D(100, 100), Vec2D(200, 100), (200, 100, 0), 'hello')
    element_clicked: tuple[PileGraphic|None, CardGE|LabelGE|None] = None, None
    action: str|None = None
    is_win = game.is_win()
    mouse_to_card: Vec2D = Vec2D(0, 0)
    log_valid_actions(game)
    while running and not is_win:
        screen.fill((255, 255, 255)) # background
        game_graphic.render(screen)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = Vec2D.from_tuple(pygame.mouse.get_pos())
                element_clicked = game_graphic.element_at(mouse_pos)
                if element_clicked[0] is not None:
                    game_graphic.prioritize_render(element_clicked[0].pile)
                    if ANIMATION and isinstance(element_clicked[1], CardGE):
                        mouse_to_card = element_clicked[1].pos.sub(mouse_pos)
                        element_clicked[0].card_is_moving(element_clicked[1].card)
            if event.type == pygame.MOUSEBUTTONUP:
                if element_clicked[0] is not None and isinstance(element_clicked[1], CardGE):
                    mouse_pos = Vec2D.from_tuple(pygame.mouse.get_pos())
                    dest_element = game_graphic.element_at(mouse_pos) # can be mouse pos, but I think more natural is the center of the card # TODO
                    if dest_element[0] is not None and dest_element[0].pile.get_tag() != 'DRAW':
                        src_pile = element_clicked[0].pile.get_tag()
                        dest_pile = dest_element[0].pile.get_tag()
                        if element_clicked[0].pile.cards[-1] == element_clicked[1].card:
                            action = f'move {src_pile} {dest_pile}'
                        else:
                            src_index = element_clicked[0].pile.cards.index(element_clicked[1].card)
                            action = f'move_stack {src_pile}:{src_index} {dest_pile}'
                        game_graphic.prioritize_render(dest_element[0].pile)
                    element_clicked[0].card_stopped_moving(element_clicked[1].card)
                elif element_clicked[0] is not None and isinstance(element_clicked[1], LabelGE):
                    if element_clicked[0].pile.get_tag() == 'DRAW':
                        action = 'draw'
                element_clicked = None, None
            if event.type == pygame.MOUSEMOTION:
                mouse_pos = Vec2D.from_tuple(pygame.mouse.get_pos())
                if ANIMATION and isinstance(element_clicked[1], CardGE):
                    element_clicked[1].move(mouse_pos.add(mouse_to_card), True)
            if action is not None:
                print(f"action received: {action}")
                Parser.perform_action_in_game(action, game)
                action = None
                log_valid_actions(game)
                is_win = game.is_win()
        pygame.display.update()
    pygame.quit()
    sys.exit()