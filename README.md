# Football Game — Prototype 0.1

An 11v11 arcade football match: movement, passing, shooting, tackling,
player switching, team AI with real shape (not "everyone chase the ball"),
and dedicated goalkeeper AI. No management/career systems — this prototype
is only about making the match itself fun to play.

## How to run

No build step, no server framework — it's plain HTML/CSS/JS.

1. Open `index.html` directly in a modern browser (Chrome, Firefox, Edge).
2. Pick a half length and click **Kick Off**.

If your browser blocks local file access for any reason, serve the folder
with any static server, e.g. `python3 -m http.server 8000` from this folder,
then visit `http://localhost:8000`.

## Controls

| Key | Action |
|---|---|
| `W A S D` | Move |
| `Shift` (hold) | Sprint (drains stamina) |
| `J` | Pass to the best open teammate in your aim direction |
| `K` (hold, release) | Shoot — hold longer for more power |
| `L` | Tackle a nearby ball carrier |
| `I` / `Tab` | Switch to the teammate closest to the ball |
| `Esc` / `P` | Pause |

## Architecture

Plain `<script>` includes (no bundler), loaded in dependency order from
`index.html`. Everything hangs off a few clean layers so future systems
can be bolted on without rewrites:

```
js/config.js              All tunable constants + shared "football data"
                           shapes (attributes, positions, formation).
js/utils.js                Vector math + small helpers.

js/entities/Player.js      Physical state + attribute-driven stats.
js/entities/Ball.js        Ground + simple air physics.
js/entities/Team.js        Squad generation, formation/shape helpers.

js/systems/input.js        Keyboard state for the human-controlled player.
js/systems/camera.js       Angled top-down arcade camera (follow + zoom).
js/systems/actions.js      Pass/shoot/tackle mechanics — shared by human
                            input AND the AI, so both play by the same rules.
js/systems/ai.js           Outfield team AI: limited "chasers", marking,
                            shape-holding support runs.
js/systems/goalkeeper.js   Dedicated goalkeeper behaviour.
js/systems/renderer.js     All canvas drawing.
js/systems/match.js        The "referee": state machine, timers, scoring,
                            restarts, collisions.

js/ui.js                   DOM overlay (menus/HUD) wiring.
js/main.js                 Boots everything + the game loop.
```

### Reuse for the future SIMULATE MATCH engine

Player/Team/Ball are plain data + pure methods with no rendering or DOM
code inside them, and `actions.js` contains the actual pass/shoot/tackle
math as standalone functions taking entities as arguments. That's the seam
where a future headless "simulate match" engine can call the exact same
attribute-driven mechanics without dragging in the canvas renderer, input
system, or camera — those three are the only browser-specific pieces.

## What's deliberately not built yet

Per the prototype scope: no transfers, contracts, wages, managers, staff,
youth academies, player generation, awards, news, career mode, leagues,
tournaments, save system, or real player databases. Those are for later
versions, once the match itself is confirmed fun.
