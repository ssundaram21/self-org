// All on-screen text for the teaser video. Edit here, then re-render (see README.md).
//
// Times are in "story seconds", the clock index.html animates on. The video plays this clock
// slower or faster per segment (SPEED in index.html).
// Rough story-clock map of what happens on screen:
//   -6.4 .. 2.0   intro text on its own, then fades out
//    2.8 .. 13.4  workspace appears: robot, frame, Files box, goal, tools
//   13.6 .. 31.0  scene t=0: test game -> player loses -> agent writes notes v2
//   32.0 .. 38.0  fast-forward through 60 gameplays (timeline)
//   38.4 .. 64.0  scene t=60: game19 -> player loses -> notes edited to v16 -> player wins
// To find exact times, open index.html?play=1&debug=1 in a browser: the story clock is shown top-left.
//
// Text may contain <b>bold</b>.

// Intro, shown alone before any of the workspace appears. Each piece fades in at `at`.
// (The intro plays faster than the rest of the video; see SPEED in index.html.)
const INTRO = [
  { at: -6.4, text: 'We put an LLM agent in a workspace' },
  { at: -5.2, text: ' and give it a <b>general <span style="white-space:nowrap">self-improvement</span> goal</b>' },
  { at: -3.8, text: ' to get better at playing unseen games.' },
  { at: -2.2, text: ' It has <b>tools</b>, but <b>no real games</b> to practice on.' },
  { at: -0.8, text: ' What does it do?' },
];
const INTRO_FADE_OUT = 1.4;  // story time the intro starts fading out

// Narration bar under the workspace. Each line shows from `at` until the next line's `at`
// (or until `until`, if given). Use text: '' to clear the bar.
// Markup:  <file>game1.txt</file>  a file or folder (monospace, grey chip)
//          <ver>v15</ver>  a version of the player artifacts (monospace, blue chip)
//          <b>bold</b>
const NARRATION = [
  { at: 2.9,  text: 'The agent is inside a constrained workspace.' },
  { at: 5.4,  text: 'Its instruction is to make a <b>player</b> agent (an instance of itself) better at playing games.' },
  { at: 8.0,  text: 'It has tools to <b>read</b>/<b>write</b> files, run <b>bash</b>, and watch the player <b>play</b> games.' },
  { at: 10.6, text: 'No real games are given. To watch the player try games, <b>it must write the games itself.</b>' },
  { at: 13.6, text: 'It starts by exploring: it decides to build a test game.' },
  { at: 16.5, text: 'It <b>writes</b> a new game, <file>game1.txt</file>.' },
  { at: 18.3, text: 'It has the player <b>play</b> the game; the player loses.' },
  { at: 23.9, text: 'The game <file>transcript</file> is saved so the agent can study it.' },
  { at: 25.0, text: 'From the loss, it concludes the player should analyze the board on every turn…' },
  { at: 27.8, until: 31.4, text: '…and <b>writes</b> it into notes <ver>v2</ver> given to the player before each game.' },
  // { at: 31.4, text: 'It keeps running this loop on its own: build games, watch the player, revise the notes.' },
  { at: 38.4, text: 'The agent now has 18 games and notes at <ver>v15</ver>. It considers re-running an old game…' },
  { at: 41.2, text: '…but decides a new stress test will teach more, and <b>writes</b> <file>game19.txt</file>.' },
  { at: 45.0, text: 'It has the player <b>play</b> <file>game19</file> both with and without notes <ver>v15</ver>.' },
  { at: 51.0, text: 'It finds the player\'s mistake.' },
  { at: 54.8, text: 'It <b>edits</b> the notes, making <ver>v16</ver>.' },
  { at: 57.0, text: 'It replays <file>game19</file> with <ver>v16</ver>, and the player wins both games.' },
  // { at: 60.1, text: 'With no tasks given, the agent built its own practice games and improved the player.' },
];

// Caption shown inside the workspace during the fast-forward.
const FAST_FORWARD_CAPTION = '60 gameplays later…';

// The agent's thought bubbles (typed out in the bubbles on screen).
const THOUGHTS = {
  B1:  "I'll start by exploring the environment.\n\nLet me set up a test game.",
  B2:  "I'm updating the play prompt to require per-turn state analysis.\n\nTime to write this into files.",
  D1a: "I'm weighing whether to re-run game17...",
  D1b: "\n\nI decide to build a new mechanic stress test: game19.",
  D2:  "The key failure was committing to an unverified goal — worth noting that decoys exist.",
  D3:  "The decoy game jumped from 0.0 to 1.0, a solid improvement.",
};
const GOAL = "Improve an agent's ability to play unfamiliar single-player games.";
