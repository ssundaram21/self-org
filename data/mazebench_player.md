You are controlling a 3D grid game. Its rules are not given to you: work them out by acting and
watching what changes.

# Objective
You have just entered this room from its {side} edge. Leave it through a different edge, into another room.

# Notes
`action_sequence` takes several actions in order, e.g. `action_sequence up up left`; each one
costs a turn, and the sequence stops at the first action the game refuses.

Moves are screen-relative. A blocked move is not reported: infer the effect of a move from the
next observation. If the player dies, only `undo` and `reset` are accepted until the player is
alive again.
