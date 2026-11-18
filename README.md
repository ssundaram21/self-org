<div align="center">
<h1>Do LLM Agents Still Need to Be Told How to Self-Improve?</h1>

#### [Project Page](https://ssundaram21.github.io/self-org/) | [Paper](https://arxiv.org/abs/2611.23219) | [Bibtex](#bibtex)

[**Shobhita Sundaram**](https://ssundaram21.github.io/)<sup>1</sup>,  [**Cansu Sancaktar**](https://csancaktar.github.io/)<sup>2</sup>,  [**Phillip Isola**](https://web.mit.edu/phillipi/)<sup>1</sup>

<sup>1</sup>MIT  <sup>2</sup> University of Tübingen

</div>

**Tl;DR** We give a frozen LLM agent a general self-improvement goal, a budget, and basic tools for writing games and editing text. We don't give it a recipe or tell it how to compose those tools. We find that sufficiently capable LLM agents successfully compose their own self-improvement loops using human-recognizable learning strategies.

## Abstract
LLM agents increasingly drive their own learning. Self-improvement methods delegate various components of model optimization to the models themselves. As models become more capable, this motivates a basic question: do these increasingly capable models still need us to specify how they should self-improve? In this paper we study an autonomous paradigm in which, given basic primitives, resources, and a general goal for self-improvement, agents construct their own self-learning algorithm for context-based optimization. Using the setting of gameplay as a testbed, a frozen LLM agent is given a compute budget and tools for collecting experience and updating text documents, and allowed to freely experiment without an externally imposed loop or access to real-world data. We find that sufficiently capable models do self-improve under these conditions, demonstrating strategies that align with classic cognitive frameworks for self-regulated learning and constructs from machine learning literature on self-generated curricula. Furthermore, we study the extent to which the learned text artifacts transfer to external benchmarks, observing improvement across different game horizons, mechanics, and 3D navigation.

## Setup

Requires git, node (>= 12; the `mazebench` benchmark needs >= 20), npm, Python >= 3.10, and a
container runtime: Singularity/Apptainer or Docker (Linux, or Docker Desktop on macOS).

    ./setup.sh          # game engines, the agent containers, pip requirements
    ./download.sh       # the benchmarks, into data/benchmarks/

**Setting your container**
- Set `SELFORG_RUNTIME=singularity` to run in a Singularity container.
- Set `SELFORG_RUNTIME=docker` to run in a Docker container.
- To (re)build the agent containers, run `./containers/build.sh`.

**Credentials:**
- For Claude models (using headless Claude Code sessions), set`CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`.
- For Non-Claude models (using headless Pi sessions) set `OPENROUTER_API_KEY`.
- For ARC-AGI-3 evals, set `ARC_API_KEY`.

## Run
The main entry point script is:
    ./run.sh            # baseline, train, evaluate

Which executes these three steps:

    python eval.py  out=evals/baseline/ps_t20/seed1 benchmark=ps_t20     # the default player
    python train.py out=runs/seed1                                       # the teacher optimizes player_folder/
    python eval.py  out=evals/trained/ps_t20/seed1 benchmark=ps_t20 \
        artifacts=runs/seed1/player_folder                               # the optimized player

## How the pipeline works

**Player sessions** (`selforg/player.py`) plays one game in a fresh session. Each turn it is shown the
game's feedback and replies with a line `ACTION: ...`, until the game is won or its turn or
output-token budget runs out. All it has is a given system prompt and a `player_folder` containing further context (such as skill files). The baseline player has a short default prompt and no files.

**Teacher Sessions** (`train.py`, `selforg/teacher.py`) "Training" is one long teacher session. The teacher works in
a sandbox containing `player_folder/`, seeded with the default prompt, and is given a general goal to make
the player better at unknown games. It can edit `player_folder/` and update the player prompt however it wants. 

When the Gameplay tool is enabled (`selforg/gameplay.py`) the teacher can write its own games and observe a fresh player
play them, with or without its current text artifacts. The Gameplay tool validates that the provided game source file compiles, and for PuzzleScript games that they are solvable.

Each teacher session is subject to two budgets:
- **Updates**: One update is a tool call that leaves `player_folder/` in a new state. Each state
  is saved as `library_versions/vNNN` (`v001` is the default prompt).
- **Plays**: How many games the teacher may observe with the Gameplay tool.

The run ends when either budget is exhausted. If the teacher tries to stop earlier, it is nudged to continue.

**Evaluation** (`eval.py`) plays every game in an external benchmark with a given
`player_folder` (or none, for the baseline) and reports the mean score. Each benchmark's default turn horizon and token budget are in `selforg/config.py`.

Teacher and player sessions both run as agent sessions inside Singularity or Docker containers
(`selforg/harness.py`): Claude models in Claude Code, `openrouter/...` models in Pi.

## Configs

Config options are `key=value` arguments; see `selforg/config.py`.

`train.py` config options:

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


<a name="bibtex"></a>
## Citation

If you find our work or any of our materials useful, please cite our paper:
```
@article{sundaram2026llmagentsneedtold,
      title={Do LLM Agents Still Need to Be Told How to Self-Improve?}, 
      author={Shobhita Sundaram and Cansu Sancaktar and Phillip Isola},
      year={2026},
      eprint={2611.23219},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/2611.23219}, 
}
```
