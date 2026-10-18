# Games, session flow and adaptive difficulty

Each game asks for one target movement at a time, logs every attempt as correct or not, and scores 10 points per correct movement, plus 5 more while the patient has 3 or more correct in a row.

## The four games

| Game | Goal | Webcam control | Keyboard control | Trains |
|---|---|---|---|---|
| Balloon Pop | Pop rising balloons | Move the hand to aim; a full five-finger fist on the glowing balloon pops it; open the hand again before the next pop | Arrows aim, C pops | Reaching, hand close and open |
| Car Driving | Catch gold stars in the green lane and avoid traffic | Hold the hand left, middle or right of the camera view to pick a lane; a fist brakes | Left/Right arrows change lane, C brakes | Side-to-side reach, holding a position, hand close |
| Treasure Hunt | Collect every chest on an island grid | Push the hand like a joystick (left, right, up, down) for one step, then return to centre; at a chest open the hand, then make a fist | Arrows walk, O opens, C grabs | Four directions, hand open and close |
| Shape Matching | Put each shape in its matching hole | Hover a shape, make a fist to pick it up, carry it, open the hand to drop it | Mouse; hold left-click or Space to drag | Grasp and release, reaching, precision |

| Game | What counts as an attempt | Extra points and penalties |
|---|---|---|
| Balloon Pop | Each pop (correct); each balloon that floats away (missed) | Golden balloon (every 7th) +20 |
| Car Driving | Each lane change toward or away from the star lane | Star caught +15; missed star breaks the streak; crash -5 |
| Treasure Hunt | Each step against the suggested shortest path; opening and grabbing at a chest | Chest +25; island cleared +50, then a new island |
| Shape Matching | Each drop in a hole (right or wrong hole) | Round complete +20; dropping away from any hole is not counted |

In Webcam + EMG mode every game also shows live EMG RMS and MAV (Car Driving adds a meter relative to the session peak) and pauses on a waiting screen when EMG data stops. These are electrical activity values, not strength scores.

## Session flow

1. **Start screen:** how to play; start with Space or by holding an open hand.
2. **Countdown:** 3-2-1.
3. **Play:** timer at the top (180 s by default), a prompt naming the next movement, popups for streaks and level changes. Enter pauses (paused time is not counted), M mutes, Esc ends early.
4. **Results:** score, accuracy, good movements per movement type, best streak, average reaction time, previous best, and 1-3 stars (3 stars at 80% accuracy or more, 2 at 50% or more).
5. **Save:** upload to the API, or queue in `data/logs/pending_sessions.jsonl`; in auto mode the level is saved to `data/logs/game_levels.json`.

Session length, difficulty, sound and the start/results screens come from `game_session_seconds`, `game_difficulty`, `game_sound` and `game_show_screens` in `config/settings.yaml`, or from `--duration` and `--difficulty` on the command line or in the web app's Game Launcher.

## Adaptive difficulty

Levels run from 1.0 (easiest) to 5.0 (hardest). Presets: easy 1.5, medium 3.0, hard 4.5; presets never change during a session.

Auto mode (`src/games/difficulty.py`) starts at the patient's saved level for that game (or 3.0). After at least 4 attempts since the last change it looks at the last 6 attempts:

- 80% or more correct: level up by 0.5 ("Level up! A little faster now").
- 40% or less correct: level down by 0.5 ("Let's slow it down a little").

Each game turns the level into concrete parameters, interpolated linearly from level 1 to level 5:

| Game | Parameter | Level 1 | Level 5 |
|---|---|---|---|
| Balloon Pop | New balloon every | 1,700 ms | 800 ms |
| Balloon Pop | Rise speed | 1.2 | 2.8 |
| Balloon Pop | Balloon radius | 54 px | 38 px |
| Balloon Pop | Hand movement amplification | 1.6x | 1.0x |
| Car Driving | Top speed | 3.5 | 7.5 |
| Car Driving | New traffic every | 2,300 ms | 1,000 ms |
| Car Driving | Hand distance from centre to change lane | 10% of view | 19% of view |
| Treasure Hunt | Chests per island | 2 | 5 |
| Treasure Hunt | Obstacles | 6 | 16 |
| Treasure Hunt | Joystick push needed | 8% of view | 16% of view |
| Shape Matching | Shapes per round | 3 | 6 |
| Shape Matching | Drop zone | 80 px | 42 px |
| Shape Matching | Hand movement amplification | 1.5x | 1.0x |

## Code

| File | Role |
|---|---|
| `src/games/game_engine.py` | `BaseGame`: input, scoring, streaks, timer, pause, start/results screens, session save, latency log |
| `src/games/difficulty.py` | Levels, presets, auto adaptation, per-patient memory |
| `src/games/summary.py` | Results summary, stars, encouragement text |
| `src/games/audio.py` | Synthesised sound effects |
| `src/games/balloon_pop.py`, `car_driving.py`, `treasure_hunt.py`, `shape_matching.py` | The four games |

To add a game, see [developer_guide.md](developer_guide.md).
