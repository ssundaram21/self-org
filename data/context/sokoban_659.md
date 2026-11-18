You will play small, turn-based, grid puzzle games written in PuzzleScript (objects, per-turn pattern-rewrite rules, collision layers, a win condition, hand-made levels). Themes, mechanics, and polish vary widely.

An episode is one level from one game, drawn from anywhere in its sequence (possibly late). No title, rules, level number, or win condition is shown — only the grid and its responses.

Each turn you see a text rendering and choose `up`, `down`, `left`, `right`, or `action`; `undo` and `restart` also exist. The episode ends on win or after a fixed turn budget. Optimal solutions are short (about 5–12 moves); the budget is larger and the optimum hidden.

Rendering: cells separated by `|`, each with equal character slots; a slot holds a letter (one object) or `.` (empty), so stacks show several letters. A legend maps letters to object names. Letters are per-game, often arbitrary, and reused with different meanings across games; names may be terse or inconsistent. The legend lists only objects currently present; later-created objects appear once they exist. Originally invisible or decorative objects render as ordinary letters, so not everything shown matters.

Nearly all games have an avatar moving one cell per turn, blocked by walls. Most involve pushing (an object moves if the cell beyond is free). Most win conditions are "every X on a Y", sometimes combined. `action` often does nothing.

Other mechanics are discovered only by play, e.g. matching blocks vanishing, colors merging, one-axis pushing, buttons opening remote doors, form-changing keys, teleporters, lethal enemies, countdowns resetting pieces, ability pickups, spreading paint, sliding platforms, multiple avatars. Rules may fire automatically after a move, causing distant changes or chain reactions over turns. Unwinnable states arise silently. Rules range from one to dozens; layouts from a corridor to mazes of hundreds of cells.