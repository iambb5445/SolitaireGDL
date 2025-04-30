# Solitaire Game Description Language (SGDL)

This repository contains the code for a framework which allows for creating playable soliatire games based on a Game Description Language (GDL). The code includes game logic, parsing, and some game playing bots capable of playing with any generated game.

Additionally, a simple gui is implemented in `gui.py` which can be used to visualize and play any described game. Note that due to the dynamic generation of gui, the placement of elements are not always perfect. Alternatively, the game can be played through the terminal commands using `run_cmd.py`.

## How to Run

### Play through Terminal
To play a solitaire game through terminal commands, use:

```shell
python run_cmd.py <sgdl-filename>
# e.g.
# python run_cmd.py games\spider.sgdl
```

The state of the game will be printed in the terminal, and the list of valid moves at the current state will be displayed. To play the game, you can either type the desired move (which might be invalid), or type the index of the move from the list of displayed moves.

Whenever a move is attempted, a full summary of its conditions is displayed, showing whether or not each subcondition is true or false. If the move is finally valid, it will be performed. Otherwise, the game continues from the current state.

Additionally, a summary of the win condition will be displayed after every move.

### Play through GUI

To play the game using the GUI, you can run:

```shell
python gui.py <sgdl-filename>
# e.g.
# python gui.py games\klondike.sgdl
```

Note that the gui uses the `pygame` library, so ensure that `pygame` is installed before running the GUI. `pygame` can be installed using:

```shell
pip install pygame
```

Upon running the gui, a visual representation of the current game state will be displayed. The cards can be dragged to perform a `MOVE`. A `MOVE_STACK` can be performed by moving the top card of the stack to a new position. Note that no animations are supported, so the visuals will change only if the move is valid.
Finally, a `DRAW` action is done by clicking on the `Draw` label next to the draw pile. This is only supported if the draw pile exists and if the draw action is valid.

The game ends and the window is closed when a win condition is reached. Note that when any move is attempted, valid or invalid, a full summary of its conditions will be printed in the terminal. Additionally, the list of all valid moves and a summary of the win conditions is also displayed after every move.

### Simulation using Bots

To have bots play the game, use the following command:

```shell
python simulate.py
```

This is work in progress. The readme will be updated later.

## Solitaire Game Description Language (SGDL)

To describe a game of solitiare, a `sgdl` file format is used. This file should follow SGDL grammar rules. For more information, refer to [the SGDL documentation](SGDL_Grammar.md).