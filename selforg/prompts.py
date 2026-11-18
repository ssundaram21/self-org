"""Every model-facing string: the player's prompts, the teacher's, and the Gameplay tool's."""

import re
from pathlib import Path

from selforg.config import WORKDIR, Train, is_pi

PLAYER = """\
You are playing a game. Each turn, end your response with:

ACTION: the action you take this turn (just the action, nothing else)."""


def player_system(prompt: str, files: list[str]) -> str:
    listing = (f"Files in your working directory: {', '.join(files)}." if files
               else "There are no files in your working directory.")
    return f"{prompt}\nYour working directory is {WORKDIR}.\n{listing}"


def _turn_tail(actions: list[str] | None, turns_left: int) -> tuple[str, str]:
    menu = "\nAvailable actions: " + " | ".join(actions) if actions else ""
    return menu, f"\nTurns remaining: {turns_left}."


def first_turn(intro: str | None, actions: list[str] | None, turns_left: int) -> str:
    menu, left = _turn_tail(actions, turns_left)
    intro = f"\n{intro.strip()}" if intro else ""
    return f"The game begins.{intro}{menu} Take your first action (format: ACTION: ...).{left}"


def next_turn(feedback: str, actions: list[str] | None, turns_left: int) -> str:
    menu, left = _turn_tail(actions, turns_left)
    return f"Feedback: {feedback}{menu}\nTake your next action (format: ACTION: ...).{left}"


def no_action_turn(intro: str | None, actions: list[str] | None, turns_left: int) -> str:
    """Replaces the next prompt after a reply with no ACTION: line, re-showing the live board."""
    menu, left = _turn_tail(actions, turns_left)
    intro = f"\n{intro.strip()}" if intro else ""
    return (f"Please issue a valid action.{intro}{menu}\n"
            f"Take your next action (format: ACTION: ...).{left}")


def parse_action(response: str) -> str:
    found = re.findall(r"ACTION:\s*(.+)", response, re.IGNORECASE)
    return found[-1].strip() if found else ""


# Two lines end in a space, as they did in the paper's runs.
TEACHER = (
    "Your goal is to improve an agent's ability to play unfamiliar single-player games. \n"
    "All games have the following attributes:\n"
    "- Single player.\n"
    "- At each player turn, the player takes an action, and receives feedback on the game state.\n"
    "- The game has an objective and a score.\n"
    "- The player plays without full knowledge of the rules, and discovers the game mechanics "
    "through play.\n"
    "\n"
    "The player has basic file read tools.\n"
    "\n"
    "You can write whatever artifacts you want for the player to player_folder/. ONLY write "
    "artifacts for the player to player_folder/. It is the player's working directory. The player "
    "prompt is in player_folder/player_prompt.md, and may be edited. \n"
    "**Generalizability.** The goal is to help a blind player do well on NEW games of the same "
    "style/form but DIFFERENT tasks and subject matter. Your artifacts must TRANSFER to improve "
    "performance on unseen games.\n"
)
GAME_REFERENCE = {
    "puzzlescript": "The PuzzleScript language reference is in puzzlescript_docs/.",
    "python": "The game interface is in game_interface.md.",
}
BEGIN = "Begin."


def teacher_system(cfg: Train) -> str:
    text = TEACHER
    if cfg.tools == "gameplay":
        text += (f"\n{GAME_REFERENCE[cfg.games]} Do NOT place your generated games or output "
                 f"files in player_folder/.")
    if cfg.context:
        text += f"\n\n**Information about the game setting:**\n\n{Path(cfg.context).read_text().strip()}"
    if is_pi(cfg.model):
        text += (f"\n\nThere are two budgets: {cfg.plays} game plays and {cfg.updates} revisions. "
                 f"A revision is any tool call that changes {WORKDIR}/player_folder/; writing two "
                 f"files in one turn spends two. Every play result reports the revisions left and "
                 f"gameplays used. The run ends when either budget is exhausted. ")
    return text


def keep_working(revisions_left: int) -> str:
    return f"Keep working. Revise your artifacts further. Revisions remaining: {revisions_left}."


def gameplay_tool(cfg: Train, turn_pool: int, token_pool: int) -> dict:
    """The play_own_game tool as an MCP definition. Read-only-hinted so several calls run at once."""
    description = ("Play one game you wrote with a fresh player agent, and wait for it to finish. "
                   + ("Pass player_folder to give your artifacts to the player; omit the "
                      "player_folder argument to play with the default prompt. " if is_pi(cfg.model)
                      else "")
                   + "Several of these can run at once.")
    outside = "must be outside player_folder/"
    args = {"game_file": (f"path to the PuzzleScript file holding your game; {outside}"
                          if cfg.games == "puzzlescript"
                          else f"path to the Python file holding your GameEnvironment class; {outside}")}
    if cfg.games == "puzzlescript":
        args["level"] = "index of the level in that file to play; defaults to 0"
    if turn_pool:
        args["turns"] = (f"how many turns to give the player in this game; drawn from your pool "
                         f"of {turn_pool} turns, which every play result reports.")
    if token_pool:
        args["tokens"] = (f"how many total output tokens to give the player in this game, at most "
                          f"{cfg.max_game_tokens}; drawn from your pool of {token_pool} tokens, which "
                          f"every play result reports. ")
    args["out"] = f"path this play's full result is written to; {outside}"
    args["player_folder"] = "path to the folder of artifacts to give the player; omit it to play with none"
    return {"name": "play_own_game", "description": description,
            "inputSchema": {"type": "object",
                            "properties": {k: {"type": "string", "description": v}
                                           for k, v in args.items()},
                            "required": [k for k in args if k not in ("level", "player_folder")]},
            "annotations": {"title": "play_own_game", "readOnlyHint": True}}

