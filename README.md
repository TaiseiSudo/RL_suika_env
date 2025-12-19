# Suika-like Simulation Environment (Python)

## Class: `EnvConfig`

`EnvConfig` is a dataclass that defines all environment constants (screen size, container bounds, physics, and limits).

### Fields

| Name             |          Type |  Default | Meaning                                                                                         |
| ---------------- | ------------: | -------: | ----------------------------------------------------------------------------------------------- |
| `W`              |         `int` |    `480` | Screen width (pixels).                                                                          |
| `H`              |         `int` |    `720` | Screen height (pixels).                                                                         |
| `FPS`            |         `int` |     `60` | Simulation and rendering frame rate (steps per second).                                         |
| `wall_thickness` |         `int` |     `12` | Wall thickness (visual/structural).                                                             |
| `floor_y`        |       `float` |  `700.0` | Y-coordinate of the floor (pixels).                                                             |
| `left_x`         |       `float` |   `40.0` | X-coordinate of the left wall (pixels).                                                         |
| `right_x`        |       `float` |  `440.0` | X-coordinate of the right wall (pixels).                                                        |
| `spawn_y`        |       `float` |   `90.0` | Y-coordinate where new fruit spawns (pixels).                                                   |
| `lose_line_y`    |       `float` |   `70.0` | Y-coordinate of the lose line (pixels). If any fruit crosses above this line, the episode ends. |
| `move_speed`     |       `float` |  `360.0` | Cursor movement speed (pixels/second).                                                          |
| `g`              |       `float` | `1400.0` | Gravity acceleration (pixels/second²).                                                          |
| `substeps`       |         `int` |      `4` | Physics substeps per frame (`FPS` step). Higher improves stability.                             |
| `restitution`    |       `float` |   `0.05` | Bounce factor for collisions. Lower is less bouncy.                                             |
| `friction`       |       `float` |   `0.10` | Simple tangential damping used on wall/floor and circle collisions.                             |
| `vel_damp`       |       `float` |  `0.999` | Global velocity damping per integration step (numerical stability).                             |
| `max_speed`      |       `float` | `2500.0` | Maximum allowed speed magnitude (clamp).                                                        |
| `max_fruits`     |         `int` |     `70` | Maximum number of fruits in the container (hard cap).                                           |
| `max_type`       |         `int` |     `10` | Maximum fruit type index (merge does not progress beyond this).                                 |
| `seed`           | `int \| None` |   `None` | Random seed for deterministic next-fruit sampling.                                              |

---

## Class: `SuikaEnv`

Minimal Suika-like environment for RL and human play.

### Action Space

Action is a 2-tuple: `(move, drop)`

* `move`: `float` in `[-1.0, +1.0]` (cursor move left/right)
* `drop`: `int` (`0/1`) (spawn the current `next` fruit at `cursor_x`)

### Observation

`reset()` and `step()` return observation dict:

| Key           | Type          | Meaning                                                                                           |
| ------------- | ------------- | ------------------------------------------------------------------------------------------------- |
| `next`        | `int`         | Next fruit type index to be dropped.                                                              |
| `cursor_x`    | `float`       | Cursor x-position normalized to `[0,1]` within container bounds.                                  |
| `score`       | `int`         | Current score (increases on merges).                                                              |
| `fruits`      | `list[tuple]` | Fruits currently in the container. Each entry: `(type, x_norm, y_norm, vx_norm, vy_norm, r_norm)` |
| `n_fruits`    | `int`         | Number of fruits currently in the container.                                                      |
| `last_merges` | `int`         | Number of merges that occurred during the last `step()`.                                          |

Normalization:

* `x_norm`: x in `[0,1]` relative to `[left_x, right_x]`
* `y_norm`: y in `[0,1]` relative to `[lose_line_y, floor_y]`
* `vx_norm`, `vy_norm`: velocity divided by `max_speed`
* `r_norm`: radius divided by container width

---

## `SuikaEnv` Method List

### `__init__(self, cfg: EnvConfig | None = None)`

* **Args**

  * `cfg`: `EnvConfig | None` — configuration. If `None`, default `EnvConfig()` is used.
* **Returns**: `None`
* **Behavior**: Initializes RNG, config, and calls `reset()`.

### `reset(self)`

* **Args**: none
* **Returns**: `dict` — observation
* **Behavior**: Resets score, fruit list, cursor, and samples a new `next` fruit.

### `step(self, action)`

* **Args**

  * `action`: `(move, drop)`

    * `move`: float in `[-1, +1]`
    * `drop`: int (0/1)
* **Returns**: `(obs, reward, done, info)`

  * `obs`: `dict` — observation
  * `reward`: `float` — score increment from this step (`score_after - score_before`)
  * `done`: `bool` — termination flag
  * `info`: `dict` — may contain `reason` (e.g., `"lose_line"`, `"max_fruits"`, `"done"`)
* **Behavior**:

  1. Moves cursor.
  2. If `drop == 1`, spawns the current `next` fruit and resamples `next`.
  3. Advances physics with `substeps`.
  4. Resolves collisions and merges.
  5. Checks termination conditions.

### `render(self, screen)`

* **Args**

  * `screen`: `pygame.Surface` — target surface for drawing
* **Returns**: `None`
* **Behavior**: Draws container, fruits, cursor preview, HUD, and game-over message.

### `human_play(self)`

* **Args**: none
* **Returns**: `None`
* **Behavior**: Runs an interactive pygame loop.

  * `←/→`: move cursor
  * `Space`: drop
  * `R`: reset
  * `Esc`: quit

---

## Internal Methods (Implementation Details)

These methods exist to implement physics, merging, and sampling.

### `_get_obs(self)`

* **Returns**: `dict` observation
* **Behavior**: Converts internal fruit state into normalized observation.

### `_sample_next_type(self)`

* **Returns**: `int` type index
* **Behavior**: Samples next fruit type using a fixed weight table biased toward smaller types.

### `_radius_for_type(self, t)`

* **Args**: `t: int`
* **Returns**: `float` radius (pixels)
* **Behavior**: Computes fruit circle radius from type.

### `_score_for_merge(self, new_type)`

* **Args**: `new_type: int`
* **Returns**: `int` score increment
* **Behavior**: Computes score gain for forming `new_type`.

### `_spawn_fruit(self, t, x, y)`

* **Args**: `t: int`, `x: float`, `y: float`
* **Returns**: `None`
* **Behavior**: Appends a new fruit dict to `self.fruits`.

### `_integrate(self, dt)`

* **Args**: `dt: float`
* **Returns**: `None`
* **Behavior**: Applies gravity, damping, speed clamp, and integrates position.

### `_solve_collisions(self)`

* **Returns**: `None`
* **Behavior**:

  * Resolves wall and floor collisions.
  * Resolves circle-circle overlaps and applies simple impulse response.

### `_merge_pass(self, max_merges=8)`

* **Args**: `max_merges: int`
* **Returns**: `None`
* **Behavior**: Repeatedly merges overlapping equal-type fruits (up to `max_merges` per call).

### `_find_merge_pair(self)`

* **Returns**: `(i, j) | None`
* **Behavior**: Finds the deepest-overlap pair of equal-type fruits eligible to merge.

### `_check_lose(self)`

* **Returns**: `bool`
* **Behavior**: Episode terminates if any fruit crosses above `lose_line_y`.

### `_color_for_type(self, t)`

* **Args**: `t: int`
* **Returns**: `(r, g, b)` tuple
* **Behavior**: Maps fruit type to a simple color palette for rendering.

---

## Usage: Human Play

```bash
pip install pygame
python suika_env.py
```

Controls:

* `←/→`: move cursor
* `Space`: drop
* `R`: reset
* `Esc`: quit

---

## Usage: RL / Programmatic Stepping (Minimal)

```python
from suika_env import SuikaEnv, EnvConfig

env = SuikaEnv(EnvConfig(seed=0))
obs = env.reset()

for t in range(2000):
    # Example: keep cursor centered and drop periodically
    move = 0.0
    drop = 1 if (t % 30 == 0) else 0

    obs, reward, done, info = env.step((move, drop))

    if done:
        obs = env.reset()
```

---

## Usage: RL / Random Policy Example

```python
import random
from suika_env import SuikaEnv, EnvConfig

env = SuikaEnv(EnvConfig(seed=123))
obs = env.reset()

for _ in range(5000):
    move = random.uniform(-1.0, 1.0)
    drop = 1 if random.random() < 0.10 else 0

    obs, reward, done, info = env.step((move, drop))

    if done:
        obs = env.reset()
```
