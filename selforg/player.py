"""One player, one game: a fresh session in a fresh sandbox, driven turn by turn until the game is
won or the turn or token budget runs out. The player sees only the game's feedback strings."""

import shutil
import tempfile
import traceback
from pathlib import Path

from selforg import harness, prompts
from selforg.config import PLAYER_PROMPT


def play(make_game, *, model: str, turns: int, tokens: int, artifacts: str | None,
         log: Path) -> dict:
    """`artifacts` is a player_folder: its player_prompt.md becomes the system prompt and its other
    files the player's working directory. None plays with the default prompt and no files."""
    with tempfile.TemporaryDirectory() as sandbox:
        prompt = prompts.PLAYER
        if artifacts:
            shutil.copytree(artifacts, sandbox, dirs_exist_ok=True,
                            ignore=lambda d, _: {PLAYER_PROMPT} if Path(d) == Path(artifacts) else set())
            if (Path(artifacts) / PLAYER_PROMPT).is_file():
                prompt = (Path(artifacts) / PLAYER_PROMPT).read_text()
        files = sorted(str(p.relative_to(sandbox)) for p in Path(sandbox).rglob("*"))
        system = prompts.player_system(prompt, files)
        game = make_game()
        try:
            session = harness.session(model, workdir=sandbox, tools=["Read", "Glob"],
                                      system_prompt=system, log=log)
            try:
                return {**_play(game, session, turns, tokens), "system_prompt": system}
            finally:
                session.close()
        finally:
            game.close()


def _play(game, session, turns: int, tokens: int) -> dict:
    intro = game.initial_observation()
    actions = game.available_actions()
    msg = prompts.first_turn(intro, actions, turns)
    log, used, spent, error, looped = [], 0, 0, None, False
    while used < turns and spent < tokens and not looped:
        session.cap_output(tokens - spent)
        reply = session.turn(msg)
        spent += reply["output_tokens"]
        looped = reply.get("tool_loop", False)
        action = prompts.parse_action(reply["text"])
        try:
            feedback = game.step(action)
        except Exception:
            error = traceback.format_exc()
            feedback = "[environment error]"
        log.append({"turn": len(log), "prompt": msg, "response": reply["text"],
                    "available_actions": actions, "action": action or "<no action: no ACTION: line>",
                    "feedback": feedback, "tool_uses": reply["tool_uses"], "thinking": reply["thinking"]})
        used += getattr(game, "turn_cost", 1)
        if error or game.done:
            break
        actions = game.available_actions()
        msg = (prompts.no_action_turn(game.initial_observation(), actions, turns - used) if not action
               else prompts.next_turn(feedback, actions, turns - used))
    try:
        score = 0.0 if error else float(game.score())
    except Exception:
        score, error = 0.0, traceback.format_exc()
    stop = ("crashed" if error else "done" if game.done else "tool_loop" if looped
            else "token_budget" if spent >= tokens else "turn_budget")
    amount = f"{tokens // 1000}k" if tokens % 1000 == 0 else str(tokens)
    note = {"token_budget": f"{amount} total token budget exhausted",
            "turn_budget": f"{turns}-turn budget exhausted", "tool_loop": "tool-call loop aborted"}
    if log and stop in note:
        log[-1]["feedback"] += f"\n[{note[stop]}]"
    return {"score": score, "stop_reason": stop, "crashed": bool(error), "error": error,
            "output_tokens": spent, "intro": intro, "turns": log, "info": game.info()}
