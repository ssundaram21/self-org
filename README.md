# Self-organized self-improvement

A frozen LLM, the **teacher**, is given a budget, a prompt and a set of tools, and is left to
improve the text context of a **player** (another instance of the same model) however it likes.
We then measure how the optimized context transfers to held-out game benchmarks.

## Setup

Requires git, node (>= 12; the `mazebench` benchmark needs >= 20), npm, Python >= 3.10, and a
container runtime: Singularity/Apptainer or Docker (Linux, or Docker Desktop on macOS).

    ./setup.sh          # game engines, the agent containers, pip requirements
    ./download.sh       # the benchmarks, into data/benchmarks/

The runtime is Singularity if it is installed, else Docker; set `SELFORG_RUNTIME=singularity` or
`SELFORG_RUNTIME=docker` to choose, for both setup and runs. To (re)build only the agent containers,
run `./containers/build.sh`. Docker containers run as your user and are removed when their session
ends; any left behind by a killed run can be removed with
`docker rm -f $(docker ps -aq --filter label=selforg)`.

Credentials: `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` for Claude models,
`OPENROUTER_API_KEY` for other models, `ARC_API_KEY` for the ARC-AGI-3 benchmark.

## Run

    ./run.sh            # baseline, train, evaluate

which is these three steps:

    python eval.py  out=evals/baseline/ps_t20/seed1 benchmark=ps_t20     # the default player
    python train.py out=runs/seed1                                       # the teacher optimizes player_folder/
    python eval.py  out=evals/trained/ps_t20/seed1 benchmark=ps_t20 \
        artifacts=runs/seed1/player_folder                               # the optimized player

The gap between the two `report.json` win rates is the result.

## How the pipeline works

**The player** (`selforg/player.py`) plays one game in a fresh session. Each turn it is shown the
game's feedback and replies with a line `ACTION: ...`, until the game is won or its turn or
output-token budget runs out. All it has is a `player_folder`: `player_prompt.md` is its system
prompt, and any other files are in its working directory, which it can read. The baseline player
has a three-line default prompt and no files.

**Training** (`train.py`, `selforg/teacher.py`) is one long teacher session. The teacher works in
a sandbox containing `player_folder/`, seeded with the default prompt, and is told only to make
the player better at unfamiliar games. It can edit `player_folder/` however it wants. With the
Gameplay tool (`selforg/gameplay.py`) it can also write its own games and have a fresh player
play them, with or without its current artifacts, and read the full transcript back. Before a
game is played it is validated: it must compile, and a PuzzleScript level is rejected if a solver
proves it unwinnable. The teacher never sees the evaluation benchmarks.

Two budgets bound a run:

- **updates**: one update is one tool call that leaves `player_folder/` in a new state. Each state
  is saved as `library_versions/vNNN` (`v001` is the seed).
- **plays**: how many games the teacher may run.

The run ends on the update that reaches `updates`, or when the teacher stops with its gameplay
budget spent. If it stops earlier it is told to keep working.

**Evaluation** (`eval.py`) plays every game of a benchmark several times with a given
`player_folder` (or none, for the baseline) and reports the mean score. Each benchmark's default turns,
tokens and rollouts per game are in `selforg/config.py`.

Teacher and player both run as agent sessions inside Singularity or Docker containers
(`selforg/harness.py`): Claude models in Claude Code, `openrouter/...` models in Pi.

## Options

Options are `key=value` arguments. Defaults and all fixed settings are in `selforg/config.py`.

`train.py`:

| option | default | |
|---|---|---|
| `out` | required | directory for the run; must not exist yet |
| `model` | `claude-opus-5` | teacher and player model. A Claude model id, or `openrouter/<provider>/<model>` |
| `tools` | `gameplay` | what the teacher can do: `read_write` (file tools only), `bash` (plus a shell), `gameplay` (plus the Gameplay tool) |
| `games` | `puzzlescript` | the language the teacher writes its games in: `puzzlescript` or `python`. The matching reference (`data/puzzlescript_docs/` or `data/game_interface.md`) is put in its sandbox |
| `budget` | `fixed` | who sets each game's budget. `fixed`: every game gets `horizon` turns. `token`: the teacher picks each game's turns from a pool of `plays` x `horizon`. `free`: the teacher picks turns and tokens, from pools of `plays` x `horizon` turns and `plays` x `tokens` tokens; one game may take at most 1.25 x `tokens` |
| `horizon` | `20` | turns per game |
| `tokens` | `25000` | output tokens the player may spend per game |
| `updates` | `20` | update budget |
| `plays` | `150` | gameplay budget |
| `context` | none | a file describing the target games, appended to the teacher's prompt (see `data/context/`) |

`games`, `budget`, `horizon`, `tokens` and `plays` only matter with `tools=gameplay`.

`eval.py`:

| option | default | |
|---|---|---|
| `out` | required | directory for the evaluation; skipped if it already holds a `report.json` |
| `benchmark` | required | `ps_t20`, `ps_t30` (PuzzleScript games, 20 and 30 turns), `ps_narrow` (a narrower set of PuzzleScript games), `arcagi3`, `mazebench` |
| `model` | `claude-opus-5` | player model |
| `artifacts` | none | a `player_folder` to give the player: a run's final `player_folder/`, or any `library_versions/vNNN/player_folder`. Omit for the baseline |
| `turns`, `tokens` | the benchmark's | override the benchmark's turns and output tokens per game |

## Examples

`run.sh` is the default configuration. `examples/` has the same pipeline with other settings:

    examples/quick_train.sh     a 2-update, 8-game teacher run, to check the setup
    examples/read_write.sh      a teacher with file tools only, no gameplay
    examples/python_free.sh     the teacher writes Python games and sets each game's turns and tokens
    examples/horizon30.sh       30-turn games with a larger token budget, evaluated on ps_t30 and arcagi3
    examples/other_model.sh     a non-Claude teacher and player through OpenRouter
    examples/context.sh         the teacher is given a description of the target games

## Outputs

A training run:

    player_folder/        the final optimized context: player_prompt.md plus any other files
    library_versions/     every distinct state of player_folder
    plays.jsonl, plays/   every game the teacher played: score, artifact version, transcript
    actions.log           timeline of the teacher's tool calls, plays and new versions
    logs/                 every agent session's raw events
    sandbox/              the teacher's working directory, including the games it wrote

An evaluation:

    report.json           win rate (and SPL, for mazebench)
    plays.jsonl, plays/   every game played: score and transcript
    logs/                 every player session's raw events

## Layout

    train.py, eval.py     entrypoints
    selforg/config.py     options and fixed settings
    selforg/prompts.py    every prompt the teacher and player see
    selforg/teacher.py    a training run
    selforg/gameplay.py   the teacher's Gameplay tool
    selforg/player.py     one player playing one game
    selforg/harness.py    agent sessions in Singularity or Docker containers
    selforg/games/        PuzzleScript, Python, ARC-AGI-3 and MazeBench games
    data/                 game-writing references for the teacher, context descriptions, benchmarks
