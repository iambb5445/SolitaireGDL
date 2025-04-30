# SGDL Grammar

This document describes the format of a Solitaire Game Description Language (SGDL) file. A sgdl file should contain the following:

## `<name>`
The file starts by one line containing the name of the game, which is only used for visualization and logging.

## `$cards`

```sgdl
DECK <count> <suits>
```

The first section in the file should describe the number and type of cards used in the game. This is described as some number of decks, each containing some combination of suits. For example, `DECK 4 {SPADES, HEARTS}` describes a game that is played with 4 deck of cards, each containing only Spades and Hearts (26 cards per deck). This is the set of cards required to play 2-Suit Spider Solitaire. The cards are shuffled before dealing into piles based on the `$initial` section.

## `$initial`

```sgdl
[DRAW <count> <draw_def>]
<initial_rule><nl>*
```

This section in the GDL describes the initial position of cards. The initial position of cards are always described as a set of piles. Note that this means some games with more complicated positioning for cards, such as Pyramid or TriPeaks, cannot be defined with the current grammar.

The description of piles consists of at most one `DRAW` pile and any number of other piles.

### DRAW

```sgdl
DRAW <count> DEAL <piles> | DRAW <count> ROTATE <count> <count_or_u> <count_or_u>
```

The first element in describing a draw pile is to define how many cards it initially has. The draw pile is then described as one of two possible types:
- A deal draw pile, which deals a card to any `<piles>` among the other piles. For example, `DRAW 50 DEAL COLUMN` is the draw pile in a Spider Solitaire game, which has 50 cards and will deal a card to any `COLUMN` pile when the user chooses to draw. Note that a deal draw pile cannot deal cards to itself.

- A rotate draw pile, which displays some number of cards at a time. When the user chooses to draw, some number of cards will be added to the display, but to maintain the size of the display, old cards will rotate back to the draw pile. In other words, the draw pile has a circualr queue format but only displays a window of cards at a time. The user can interact with the top card of the display by moving it to some other pile, as permitted by the move conditions.<br />
The last element in describing a draw pile is the number of times user can redeal the pile, since many games have a limited number of times the same card can be drawn from a rotate draw pile. (e.g. WestCliff, Bline Alleys, etc.)<br />
An example of a rotate draw pile is `DRAW 24 ROTATE 3 3 U` in Klondike Solitaire. The pile starts with 24 cards, with a display window of 3 cards. When the user chooses to draw, 3 more cards will be drawn (replacing the current cards unless not enough cards are avaialble to draw). Finally, this pile has unlimited redeals, denoted by the `U` as the third argument of the description.

### Other Piles
```sgdl
<pile> <count> [<pile_face>] [<cards>]
```

Any other pile in the game can be described with the format above. The first two elements show the name of the pile and the number of cards initially in the pile. Note that the name is the token used to decribe rules for a pile. For example, multiple piles in Spider have the name `COLUMN`, all of which follow the same set of conditions for moving cards into and out of them. The one "special" pile name is `FOUNDATION`, with the only special thing about it being that when using GUI, all of the cards in the foundation are visualized on top of each other (in a way that only the last card can be seen).

The third alement of the description of a pile is optional, and if included shows the starting face of the cards. By default, all piles are `FACE_LAST`. The options for face of a pile are:
- `FACE_LAST`, meaning that only the last (top) card in the pile will be face up. Note that, when the top card is moved, another card will become the top card and will be automatically turned face up, if not already. An example of this are the `COLUMN` piles in Spider or Klondike.
- `FACE_ALL`, meaning that all cards in this column are initially face up. Examples of this are `COLUMN`s in Free Cell and Simple Simon.
- `FACE_ALTERNATE_LAST`, meaning that cards in the column start alternating between face up and face down, in a way that the top card always starts face up. Note that, again, any cards at the top of the column will be automatically face up. An example of this is Legion, which is a variation of Klondike.
- Support for custom face types will be added later, since some Solitaire games such as Scorpion or Aunt Mary start with more unconventional pile faces.

The final element of describing a pile is the set of starting cards. When a pile doesn't start empty, by default the starting cards are dealt from the shuffled deck. However, if the pile starts with a predetermined set of cards in some order, those cards should be mentioned here. For example, Blind Alley starts with the 4 Ace cards in the 4 `FOUNDATION` piles.

## `$moves`

```sgdl
<move_rule><nl>*
<move_stack_rule><nl>*
[<draw_rule>]
```

The moves section defines the core logic of the game. It describes the valid moves in the game, and the conditions that should be valid for the moves to be legal.

All the moves in the game have one of the following types: `MOVE`, `MOVE_STACK`, or `DRAW`.
### `MOVE`

```sgdl
MOVE <piles_or_D> <piles><nl><move_conds>
```

This describes the conditions for moving a single card from one pile to another. Note that you can move from a DRAW pile to some other pile, but you cannot move a card to the DRAW pile.

### `MOVE_STACK`

```sgdl
MOVE_STACK <piles> <piles><nl><stack_conds>
```

This describes the conditions for moving a stack of cards (also called a "run") from one pile to another. You cannot move stacks to or from a DRAW pile.

To avoid ambiguity, MOVE_STACK is only considered when the stack size is greater than 1. While a stack size of 1 is in theory valid and can be performed using the terminal interface, it creates ambiguity when considering the gui interface. For the same reason, stack moves with only 1 card in the stack are excluded from the output of `get_possible_actions`, which is used by the bots to choose a move.

### `DRAW`

When a draw pile is available, DRAW as an action is immediately considered a valid action in the game and does not need to be defined separately. However, in case there are rules for drawing cards, DRAW can be redefined here to describe the DRAW rules. For example, in most variations of Spider, cards can be drawn from the "deal" draw pile when non of the `COLUMN`s are empty.

### Conditions

The set of conditions for checking the validity of an action are defiend after every action. These conditions, which can be added together using `AND` and `OR` keywords, have different types and can be used for different actions based on their type.

#### Conditions valid for MOVE and MOVE_STACK

Move actions involve a source card (the card being moved in `MOVE`, or the top card of the stack being moved in `MOVE_STACK`) and a destination pile.

- `DEST Empty`: Destination pile should be empty
- `DEST Size <op> <count>`: Destination pile should have a certain size (e.g. == 13, > 0, etc.)
- `SRC Suit <suits>`: Source card should have one of the suits described here
- `SRC Rank <ranks>`: Source card should have one of the ranks described here
- `DESTSRC Suit alternate_color`: Final card in the destianation pile and the source card should have alternating colors (black and red, or red and black). Note that the destination cannot be empty.
- `DESTSRC Suit match_color`: Similar to the previous case, but suit colors should be the same.
- `DESTSRC Suit match`: Similar to the previous case, but the suits should be the same (as opposed to suit colors)
- `DESTSRC Rank ascending`: Final card in the destianation pile and the source card should have ascending rank (consecutive numbers that are strictly ascending)
- `DESTSRC Rank descending`: Similar to the previous case, but descending


#### Conditions valid for MOVE_STACK

These conditions are only meaningful when moving a stack of cards. Similar to the ones above, they can involve a destiantion column, a source card (top card of the stack), and the stack of cards being moved.

- `SRCSTACK Suit alternate_color`: Suits of the cards in the stack should have alternating colors (black and red alternating)
- `SRCSTACK Suit match_color`: Suits of the cards in the stack should all have the same color (black or red)
- `SRCSTACK Suit match`: Cards in the stack should all have the same suit
- `SRCSTACK Rank ascending`: Ranks of the cards in the stack should be ascending (consecutive numbers with strictly ascending ranks)
- `SRCSTACK Rank descending`: Ranks of the cards in the stack should be ascending (consecutive numbers with strictly ascending ranks)
- `SRCSTACK Size <op> <count>`: Size of the stack should follow some rule (e.g. == 13, > 0, etc.)

#### Conditions valid for DRAW/WIN

- `PILE ALL <pileset> Size <op> <count>`: All piles of some name should have sizes that follows some rule (e.g. == 13, > 0, etc)
- `PILE ANY <pileset> Size <op> <count>`: Similar to the previous one, but as long of one of the piles with a name in this list follows the rule, this is considered true.
- `PILE ALL <pileset> Empty`: All piles of some name should be empty
- `PILE ANY <pileset> Empty`: At least one of the piles with some name should be empty

### Examples

The grammar is described in more details in `games\GRAMMAR`, and example `gsdl` files are available in the `games` directory. To give an example of a move condition here, consider the following moves description from Spider:

```sgdl
$moves
MOVE COLUMN COLUMN
OR
    DEST Empty # empty destination won't pass DESTSRC rules, to prevent problems in games such as klondike
    AND
        DESTSRC Suit match
        DESTSRC Rank descending
MOVE_STACK COLUMN COLUMN
AND
    OR
        DEST Empty
        AND
            DESTSRC Suit match
            DESTSRC Rank descending
    SRCSTACK Suit match
    SRCSTACK Rank descending
DRAW
PILE ALL COLUMN Size > 0
```

- Moving a card from one `COLUMN` pile to another `COLUMN` pile is allowed as long as either the destination is empty, or the source card and the final card in the destaition have matching suits and descending ranks.
- Moving a stack of cards from a `COLUMN` pile to another `COLUMN` pile is allowed as long as the:
   - Either the destiantion is empty, or the source card and the final card in the destination have matching suits and descending rank; and,
   - The cards in the stack have matching suits; and,
   - The cards in the stack have descending ranks
- Drawing cards is only possible if all `COLUMN` piles have a size greater than 0 (i.e. no `COLUMN` is empty)

As a second example, consider this one move description from Klondike:

```sgdl
MOVE {DRAW, COLUMN, FOUNDATION} COLUMN
OR
    AND
        DESTSRC Suit alternate_color
        DESTSRC Rank descending
    AND
        DEST Empty
        SRC Rank K
```

This means that you can move from the a card from a `DRAW` pile, `COLUMN` pile or a `FOUNDATION` pile to a `COLUMN` pile if and only if:
- The source card and the last card in the detination column have alternating colors and descending ranks (since only two cards are involved, this means that they should have a different colors and source's rank should be one lower than the rank of last card in the destination column); or,
- The destiantion is empty and the source card is a king.

## `$auto`

```sgdl
$auto
<move_rule><nl>*
<move_stack_rule><nl>*
```

The `$auto` section describes moves and conditions for them that will happen automatically in the game. For example, in Spider whenever a stack of cards is created with the same suit and ranks going from King to Ace, the stack is automatically moved to a `FOUNDATION` column. Note that since these moves are not performed by the player, they do not need to follow the rules described in `$moves`. The example above is described as follows:

```sgdl
$auto
MOVE_STACK COLUMN FOUNDATION
AND
    SRCSTACK Suit match
    SRCSTACK Rank descending
    SRCSTACK Size == 13
    DEST Empty
```

While many possible moves with these conditions may all be valid, the first one is performed. There is no guarantee on which one of the valid auto-moves are performed, but as long as one valid auto-move is available, it will be performed. Be cautious not to define infinite loops through auto-moves.

## `$win`
The final section of the sgdl file describes the win conditition. The conditions follow the same format described above. For example, in Spider the player wins when no card remains in `COLUMN` pile or the `DRAW` pile:

```sgdl
$win
AND
    PILE ALL COLUMN Empty
    PILE ALL DRAW Empty
```

Alternatively, the same condition can be described as "each `FOUNDATION` pile should have 13 cards".

```sgdl
$win
PILE ALL FOUNDATION Size == 13
```