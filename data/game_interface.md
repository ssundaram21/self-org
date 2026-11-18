# Game interface

Games are written as a self-contained class named `GameEnvironment` in a Python file.
`__init__`, `step`, `score` and `example_actions` are required; `initial_observation` is optional.

```python
class GameEnvironment:
    def __init__(self):
        self.done = False  # set to True to end the game
        ...

    def step(self, action: str) -> str:
        # `action` is a player-provided string. Parse it and handle unexpected input without
        # crashing. Return the feedback string: this is the player's only window into the game.
        ...

    def score(self) -> float:
        # The player's objective, queryable at any time. A number or a bool. The player never
        # sees this -- put anything you want it to know in step()'s feedback.
        ...

    def example_actions(self) -> list[str]:
        # A few representative valid actions, used only to test the game.
        ...

    def initial_observation(self) -> str:
        # OPTIONAL: what the player is shown at turn 0.
        ...
```


