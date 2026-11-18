"""Run configuration: the options of train.py and eval.py, and every fixed setting."""

import os
import platform
import shutil
from dataclasses import MISSING, dataclass, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKDIR = "/workspace"                    # every agent session's cwd inside the container

# The agent containers' runtime: SELFORG_RUNTIME (singularity | docker), else singularity if it is
# installed, else docker. Singularity and Docker on Linux share the host's network, so a container
# reaches the host's loopback servers at 127.0.0.1. Docker Desktop (macOS, Windows) runs containers
# in a VM, where the host's loopback is host.docker.internal and host unix sockets are unreachable.
RUNTIME = os.environ.get("SELFORG_RUNTIME") or ("singularity" if shutil.which("singularity")
                                                or not shutil.which("docker") else "docker")
if RUNTIME not in ("singularity", "docker"):
    raise SystemExit(f"SELFORG_RUNTIME={RUNTIME} is not one of singularity, docker")
DOCKER_DESKTOP = RUNTIME == "docker" and platform.system() != "Linux"
HOST_FROM_CONTAINER = "host.docker.internal" if DOCKER_DESKTOP else "127.0.0.1"
DOCKER_IMAGE = "selforg-{}"               # the Docker image of an agent container (claude_code, pi)
PLAYER_FOLDER = "player_folder"
PLAYER_PROMPT = "player_prompt.md"

EFFORT = "low"
MAX_RESPONSE_TOKENS = 20_000
MAX_GAME_TOKENS = 1.25                    # cap on one game when the teacher picks its budget, x `tokens`
CONCURRENT_PLAYS = 4                      # games played at once during training
EVAL_CONCURRENT_PLAYS = 16
BENCHMARKS = {                            # name -> (turns, tokens per game, rollouts per game)
    "ps_t20": (20, 25_000, 4),
    "ps_t30": (30, 31_250, 4),
    "arcagi3": (30, 31_250, 4),
    "mazebench": (100, 75_000, 2),
    "ps_narrow": (20, 25_000, 4),
}


@dataclass(frozen=True)
class Train:
    out: str
    model: str = "claude-opus-5"
    tools: str = "gameplay"       # read_write | bash | gameplay
    games: str = "puzzlescript"   # puzzlescript | python
    budget: str = "fixed"         # fixed | token | free: who sets each game's turns and tokens
    horizon: int = 20             # turns per game
    tokens: int = 25_000          # output-token budget per game
    context: str = ""             # file describing the target games, appended to the teacher prompt
    updates: int = 20
    plays: int = 150

    @property
    def max_game_tokens(self) -> int:
        return int(self.tokens * MAX_GAME_TOKENS)


@dataclass(frozen=True)
class Eval:
    out: str
    benchmark: str                # a key of BENCHMARKS
    model: str = "claude-opus-5"
    artifacts: str = ""           # a player_folder to give the player; "" = baseline
    turns: int = 0                # turns per game; 0 = the benchmark's
    tokens: int = 0               # output-token budget per game; 0 = the benchmark's


CHOICES = {"tools": ("read_write", "bash", "gameplay"), "games": ("puzzlescript", "python"),
           "budget": ("fixed", "token", "free"), "benchmark": tuple(BENCHMARKS)}


def parse(cls, argv: list[str]):
    """`key=value` arguments -> a `cls`. Exits with a message on a bad command line."""
    if bad := [a for a in argv if "=" not in a]:
        raise SystemExit(f"options are key=value; got {bad}")
    args = dict(a.split("=", 1) for a in argv)
    types = {f.name: f.type for f in fields(cls)}
    if unknown := args.keys() - types.keys():
        raise SystemExit(f"unknown option(s) {sorted(unknown)}; known: {sorted(types)}")
    if missing := [f.name for f in fields(cls) if f.default is MISSING and f.name not in args]:
        raise SystemExit(f"missing required option(s): {', '.join(k + '=' for k in missing)}")
    for k, v in args.items():
        if k in CHOICES and v not in CHOICES[k]:
            raise SystemExit(f"{k}={v} is not one of {', '.join(CHOICES[k])}")
    try:
        return cls(**{k: types[k](v) for k, v in args.items()})
    except ValueError as e:
        raise SystemExit(f"bad option value: {e}")


def credential(*names: str) -> tuple[str, str]:
    """The first of these environment variables that is set, as (name, value); exits if none is."""
    for name in names:
        if os.environ.get(name):
            return name, os.environ[name]
    raise SystemExit(f"set {' or '.join(names)} in the environment")


def model_credential(model: str) -> tuple[str, str]:
    if is_pi(model):
        return credential(f"{model.partition('/')[0].upper()}_API_KEY")
    return credential("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")


def is_pi(model: str) -> bool:
    """Claude models run in Claude Code; everything else runs in Pi via OpenRouter."""
    return model.startswith("openrouter/")
