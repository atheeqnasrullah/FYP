# Games, levels, session flow and adaptive difficulty

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

In Webcam + EMG mode a grip action also needs enough muscle effort (see [Grip effort threshold](#grip-effort-threshold)), and every game pauses on a waiting screen when EMG data stops.

## Levels (1 to 7)

Every game has seven levels, and the patient picks one on the **level panel**, the first screen of the game (`src/games/levels.py`, `BaseGame.level_select_screen`). With one new level a day, a patient can complete a game in a week.

| Level | Name | Difficulty | Balloon Pop | Car Driving | Treasure Hunt | Shape Matching |
|---|---|---|---|---|---|---|
| 1 | Warm-up | 1.0 | Pop 6 balloons | Catch 4 stars | Collect 2 chests | Place 3 shapes |
| 2 | Getting going | 1.7 | Pop 8 balloons | Catch 5 stars | Collect 3 chests | Place 4 shapes |
| 3 | Steady | 2.3 | Pop 10 balloons | Catch 6 stars | Collect 4 chests | Place 6 shapes |
| 4 | Building up | 3.0 | Pop 12 balloons | Catch 8 stars | Collect 5 chests | Place 8 shapes |
| 5 | Stronger | 3.7 | Pop 14 balloons | Catch 10 stars | Collect 6 chests | Place 9 shapes |
| 6 | Challenge | 4.3 | Pop 16 balloons | Catch 12 stars | Collect 7 chests | Place 10 shapes |
| 7 | Champion | 5.0 | Pop 18 balloons | Catch 14 stars | Collect 8 chests | Place 12 shapes |

- **Difficulty** is fixed for the whole level (it does not adapt during play) and sets the game parameters in [Adaptive difficulty](#adaptive-difficulty); for example, balloons rise faster and are smaller at higher levels. In Webcam + EMG mode with `game_effort_required: auto`, the grip effort needed also rises, from 25% at level 1 to 60% at level 7.
- **Passing:** reach the goal before the session time runs out (3 minutes by default; with no time limit the goal alone ends it). The level ends 1.6 s after the goal is reached, with "Level n complete!". Stars (1-3, from accuracy) are kept for the best pass.
- **Opening the next level:** level 1 is always open. Level n opens `level_days_between` days after level n-1 is first passed (default 1: the next day; 7 gives a level a week, for a 7-week programme; 0 opens it straight away). Passed and open levels can be replayed at any time.
- **Progress** is kept per patient and per game in `data/logs/level_progress.json` (plays, best count, stars, date first passed). Each saved session also records `level` and `level_passed`.
- **Free play** (the eighth card) is the earlier mode: no goal, difficulty from `game_difficulty` (auto adapts during play).

**Level panel.** Seven cards plus Free play. Each card shows the level number, name and goal, and a badge: *Done* (green, with the stars earned), *Play* (open, gold), *Soon* (passed the previous level; shows "Opens tomorrow" or the date) or *Locked* ("Pass level n first"). The lowest open level not yet passed is highlighted, and it starts by itself after 45 s. To choose:

- **Camera:** move the hand over a card, then hold it open for 1.5 s (a green bar fills along the card).
- **Keyboard and mouse:** arrows or keys 1-7 (F for free play), then Enter or Space; or click a card.

Choosing a locked card shows why it is locked and keeps the panel open. While playing, the top right shows the goal progress ("Level 4: 9 of 12 balloons popped"). The results screen says whether the level was passed and when the next one opens ("Level 5 opens tomorrow. See you then!"), or how far the patient got ("8 of 12 balloons popped. Try level 4 again to open level 5!").

## Input feedback on screen

Every game shows what drove each action, so the patient and therapist can see how the game read the hand:

- **Input strip** (top right, under the timer): the input source (Keyboard, Simulator, Camera, Camera + EMG sensor, Camera + EMG replay), the gesture the game sees now with the camera's confidence, and a muscle bar. In Webcam + EMG mode the bar is **grip effort** with a white tick at the effort needed ("20% / need 50%"; yellow below the tick, green at or above it). In other modes it reads "no EMG sensor in this mode".
- **Action cards** appear where something happened (a balloon pops, the car changes lane or brakes, a chest opens, a shape drops) and fade after about 2 s. Each card names the result ("Balloon popped!", "Wrong hole: circle", "Squeeze harder: 20% of 50%"), the gesture, the input source with confidence, and the effort bar. Green border: success; red: a miss or a grip that was too weak.
- **"Squeeze harder" meter:** while a fist is held on a target but is not yet strong enough, a small effort bar with the tick appears next to the hand.

Each attempt records `input_source` and `emg_activity_pct`; grip actions also record `effort_required_pct` and `effort_ok`. The results screen shows the average muscle activity of good movements and, in Webcam + EMG mode, **Strong grips** (how many grip attempts reached the threshold).

## Grip effort threshold

A fist seen by the camera is not enough on its own in Webcam + EMG mode: the grip must also reach a minimum muscle effort set for that patient. Without this, any EMG reading at all would let a balloon pop.

**Muscle check (calibration).** After the start screen, a two-step check runs (`src/games/effort.py`, `BaseGame.calibration_screen`):

1. *Relax your hand* for 3 s: the median EMG RMS is the patient's **rest** level.
2. *Now squeeze!* for 3 s, as hard as is comfortable: the 90th percentile RMS is the patient's **strongest squeeze**.

The first 0.8 s of each step is ignored while the hand settles. If the squeeze is not at least 5% above rest, the check repeats once, then falls back to the patient's saved check. A good check is saved per patient in `data/logs/emg_calibration.json`; press S during the check to reuse the saved one instead. With `game_emg_calibration: false` the saved check is reused without asking. With EMG replay the recording cannot follow instructions, so its own Rest windows (median) and Hand_Close windows (90th percentile) stand in, and nothing is saved for the patient.

**Effort** is then the share of the patient's own range:

```
effort % = (RMS - rest) / (strongest - rest) x 100, clipped to 0-100
```

The MD0437 gives an activity envelope in ADC units, not a force, so this is relative effort, not strength in newtons. If no check exists, effort falls back to the share of the strongest reading so far in the session.

**Effort needed** comes from `game_effort_required` in `config/settings.yaml`, `--effort` on the command line, or *Grip effort needed* in the web Game Launcher:

| Setting | Effort needed |
|---|---|
| `auto` (default) | Follows the difficulty: 25% at game level 1 to 60% at level 7 (in free play, 25% at difficulty 1.0 to 60% at 5.0, 42.5% at medium). Auto difficulty lowers it after weak attempts and raises it after successes |
| `20` to `65` (any 0-100) | Fixed share of the strongest squeeze |
| `0` | Off: any fist the camera sees counts; effort is still recorded |

**What is gated**, in Webcam + EMG mode only (keyboard, simulator and webcam-only modes have no EMG, so a fist counts at once):

| Game | Grip action that needs the effort | A fist that never reaches it |
|---|---|---|
| Balloon Pop | Popping a balloon in reach (one pop per fist) | "Squeeze harder!" under the hand; on opening, a failed attempt `Weak_Grip` and a red card |
| Car Driving | Braking (the car only slows while the grip is strong enough) | Card "Brake too weak: x% of y%"; not a scored attempt, because the targets are lanes |
| Treasure Hunt | Grabbing the gold after the chest opens | Failed attempt `Weak_Grip`; the chest stays closed until a strong fist |
| Shape Matching | Picking up a shape | Failed attempt `Weak_Grip`; the placement attempt records the effort used at pick-up |

Opening the hand (Treasure Hunt's chest lock, releasing a shape) is not gated: it is judged by the camera, since the forearm sensor mainly reads the grip.

One fist is one attempt. The fist fires once when it first reaches the threshold; a fist that opens without reaching it is logged once as `Weak_Grip` (target `Hand_Close`, incorrect), with its strongest moment as the effort.

## Session flow

1. **Level panel:** choose level 1-7 or free play (see [Levels](#levels-1-to-7)); skipped when the level was set in the web Game Launcher or with `--level`.
2. **Start screen:** the level and its goal, how to play; start with Space or by holding an open hand.
3. **Muscle check** (Webcam + EMG mode only): relax 3 s, squeeze 3 s; see [Grip effort threshold](#grip-effort-threshold).
4. **Countdown:** 3-2-1.
5. **Play:** timer at the top (180 s by default), a prompt naming the next movement, popups for streaks and level changes. Enter pauses (paused time is not counted), M mutes, Esc ends early.
6. **Results:** level passed or not and when the next level opens, score, accuracy, good movements per movement type, best streak, average reaction time, previous best, average muscle activity, strong grips, and 1-3 stars (3 stars at 80% accuracy or more, 2 at 50% or more).
7. **Save:** upload to the API, or queue in `data/logs/pending_sessions.jsonl`; level progress goes to `data/logs/level_progress.json`, and in free play with auto difficulty the difficulty is saved to `data/logs/game_levels.json`.

Session length, difficulty, sound and the start/results screens come from `game_session_seconds`, `game_difficulty`, `game_sound` and `game_show_screens` in `config/settings.yaml`, or from `--duration` and `--difficulty` on the command line or in the web app's Game Launcher. In Webcam + EMG mode the muscle check runs between the start screen and the countdown.

## Adaptive difficulty

Difficulty runs from 1.0 (easiest) to 5.0 (hardest). Game levels 1-7 map onto it (1.0, 1.7, 2.3, 3.0, 3.7, 4.3, 5.0) and never change during a level. In free play the presets are easy 1.5, medium 3.0, hard 4.5 (fixed), or auto:

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
| `src/games/game_engine.py` | `BaseGame`: input, scoring, streaks, timer, pause, start/results screens, input strip and action cards, muscle check and grip gate (`grip()`, `effort_ok()`, `log_weak_grip()`), session save, latency log |
| `src/games/effort.py` | Calibration maths, effort %, effort needed, per-patient calibration file |
| `src/games/difficulty.py` | Difficulty 1.0-5.0, presets, auto adaptation, per-patient memory |
| `src/games/levels.py` | The seven levels: names, goals, difficulty per level, when levels open, per-patient progress file |
| `src/games/summary.py` | Results summary, stars, encouragement text |
| `src/games/audio.py` | Synthesised sound effects |
| `src/games/balloon_pop.py`, `car_driving.py`, `treasure_hunt.py`, `shape_matching.py` | The four games |

To add a game, see [developer_guide.md](developer_guide.md).
