<div align="center">
<h1>Do LLM Agents Still Need to Be Told How to Self-Improve?</h1>

#### [Project Page](https://ssundaram21.github.io/self-org/) | [Paper](https://arxiv.org/abs/2611.23219) | [Bibtex](#bibtex)

[**Shobhita Sundaram**](https://ssundaram21.github.io/)<sup>1</sup>,  [**Cansu Sancaktar**](https://csancaktar.github.io/)<sup>2</sup>,  [**Phillip Isola**](https://web.mit.edu/phillipi/)<sup>1</sup>

<sup>1</sup>MIT  <sup>2</sup> University of Tübingen

</div>

**Tl;DR** We study the natural behavior of LLM agents given a general self-improvement goal, a budget, and basic tools for collecting experience and editing text. We do not give it real tasks or an explicit recipe. Sufficiently capable models successfully compose their own self-improvement loops using human-recognizable learning strategies.

## Abstract
LLM agents increasingly drive their own learning. Self-improvement methods delegate various components of model optimization to the models themselves. As models become more capable, this motivates a basic question: do these increasingly capable models still need us to specify how they should self-improve? In this paper we study an autonomous paradigm in which, given basic primitives, resources, and a general goal for self-improvement, agents construct their own self-learning algorithm for context-based optimization. Using the setting of gameplay as a testbed, a frozen LLM agent is given a compute budget and tools for collecting experience and updating text documents, and allowed to freely experiment without an externally imposed loop or access to real-world data. We find that sufficiently capable models do self-improve under these conditions, demonstrating strategies that align with classic cognitive frameworks for self-regulated learning and constructs from machine learning literature on self-generated curricula. Furthermore, we study the extent to which the learned text artifacts transfer to external benchmarks, observing improvement across different game horizons, mechanics, and 3D navigation.

## Setup

Requirements: 
- node (>= 12; >= 20 for `mazebench` evals)
- npm
- Python >= 3.10
- Singularity/Apptainer or Docker

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
| `out` | required | Output/log directory |
| `model` | `claude-opus-5` | Model ID |
| `tools` | `gameplay` | Teacher tools (e.g., `read_write`, `bash`, `gameplay`) |
| `games` | `puzzlescript` | Language the teacher writes games in (`puzzlescript`, `python`) |
| `budget` | `fixed` | `fixed`: every game gets `horizon` turns and `tokens` token budget. `token`: every game gets `token` token budget; the teacher chooses the turn budget. `free`: the teacher chooses both the turn and token budgets. |
| `horizon` | `20` | Turn budget per game |
| `tokens` | `25000` | Total output token budget per game |
| `updates` | `20` | Teacher update budget |
| `plays` | `150` | Gameplay budget |
| `context` | none | Extra context to give the teacher |

`eval.py`:

| option | default | |
|---|---|---|
| `out` | required | Output directory |
| `benchmark` | required | Benchmark ID: (`ps_t20`, `ps_t30`, `ps_narrow`, `arcagi3`, `mazebench`) |
| `model` | `claude-opus-5` | Model ID |
| `artifacts` | none | A `player_folder` to give the player. Omit for the baseline |
| `turns`, `tokens` | the benchmark's | Override the benchmark's default turn and token budgets per game |

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
