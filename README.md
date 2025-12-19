# スイカゲーム風シミュレーション環境（Python）

## 使用例：人間操作（Human Play）

```bash
pip install pygame
python suika_env.py
```

操作:

* `←/→`: カーソル移動
* `Space`: 落下（ドロップ）
* `R`: リセット
* `Esc`: 終了

---

## 使用例：RL / プログラムからステップ実行（最小例）

```python
from suika_env import SuikaEnv, EnvConfig

env = SuikaEnv(EnvConfig(seed=0))
obs = env.reset()

for t in range(2000):
    # 例：カーソルを中央に固定し、一定間隔で落とす
    move = 0.0
    drop = 1 if (t % 30 == 0) else 0

    obs, reward, done, info = env.step((move, drop))

    if done:
        obs = env.reset()
```

---

## 使用例：RL / ランダム方策（Random Policy）

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

---

## クラス：`EnvConfig`

`EnvConfig` は、環境の定数（画面サイズ、コンテナ境界、物理、各種上限など）を定義する dataclass です。

### フィールド

| 名前               |             型 |    デフォルト | 意味                                             |
| ---------------- | ------------: | -------: | ---------------------------------------------- |
| `W`              |         `int` |    `480` | 画面幅（ピクセル）。                                     |
| `H`              |         `int` |    `720` | 画面高（ピクセル）。                                     |
| `FPS`            |         `int` |     `60` | シミュレーションおよび描画のフレームレート（1秒あたりのステップ数）。            |
| `wall_thickness` |         `int` |     `12` | 壁の厚み（見た目/構造）。                                  |
| `floor_y`        |       `float` |  `700.0` | 床のY座標（ピクセル）。                                   |
| `left_x`         |       `float` |   `40.0` | 左壁のX座標（ピクセル）。                                  |
| `right_x`        |       `float` |  `440.0` | 右壁のX座標（ピクセル）。                                  |
| `spawn_y`        |       `float` |   `90.0` | 新しいフルーツのスポーンY座標（ピクセル）。                         |
| `lose_line_y`    |       `float` |   `70.0` | 負けラインのY座標（ピクセル）。いずれかのフルーツがこのラインより上に出るとエピソード終了。 |
| `move_speed`     |       `float` |  `360.0` | カーソル移動速度（ピクセル/秒）。                              |
| `g`              |       `float` | `1400.0` | 重力加速度（ピクセル/秒²）。                                |
| `substeps`       |         `int` |      `4` | 1フレーム（`FPS`の1ステップ）内での物理サブステップ数。大きいほど安定。        |
| `restitution`    |       `float` |   `0.05` | 衝突の反発係数。小さいほど跳ねにくい。                            |
| `friction`       |       `float` |   `0.10` | 壁/床および円同士の衝突で使う簡易な接線方向の減衰。                     |
| `vel_damp`       |       `float` |  `0.999` | 積分ステップごとの速度減衰（数値安定用）。                          |
| `max_speed`      |       `float` | `2500.0` | 速度ノルムの上限（クランプ）。                                |
| `max_fruits`     |         `int` |     `70` | コンテナ内フルーツ数の上限（ハードキャップ）。                        |
| `max_type`       |         `int` |     `10` | 最大フルーツ種インデックス（これ以上マージ進行しない）。                   |
| `seed`           | `int \| None` |   `None` | 次フルーツのサンプリングを決定論にするための乱数シード。                   |

---

## クラス：`SuikaEnv`

RL と人間操作に対応した、最小構成のスイカゲーム風環境です。

### アクション

アクションは 2 要素タプル：`(move, drop)`

* `move`: `float` in `[-1.0, +1.0]`（カーソルを左右移動）
* `drop`: `int`（`0/1`）（現在の `next` フルーツを `cursor_x` 位置にスポーン）

### 観測（Observation）

`reset()` と `step()` は以下の観測 dict を返します：

| キー            | 型             | 意味                                                                  |
| ------------- | ------------- | ------------------------------------------------------------------- |
| `next`        | `int`         | 次に落とすフルーツ種インデックス。                                                   |
| `cursor_x`    | `float`       | カーソルの x 位置（コンテナ内で `[0,1]` 正規化）。                                     |
| `score`       | `int`         | 現在スコア（マージで増加）。                                                      |
| `fruits`      | `list[tuple]` | コンテナ内のフルーツ一覧。各要素：`(type, x_norm, y_norm, vx_norm, vy_norm, r_norm)` |
| `n_fruits`    | `int`         | コンテナ内のフルーツ数。                                                        |
| `last_merges` | `int`         | 直近 `step()` で発生したマージ回数。                                             |

正規化の定義：

* `x_norm`: x を `[left_x, right_x]` に対して `[0,1]` へ正規化
* `y_norm`: y を `[lose_line_y, floor_y]` に対して `[0,1]` へ正規化
* `vx_norm`, `vy_norm`: 速度を `max_speed` で割る
* `r_norm`: 半径をコンテナ幅で割る

---

## `SuikaEnv` 関数一覧

### `__init__(self, cfg: EnvConfig | None = None)`

* **引数**

  * `cfg`: `EnvConfig | None` — 設定。`None` の場合は `EnvConfig()`（デフォルト）を使用。
* **戻り値**: `None`
* **概要**: 乱数・設定を初期化し、`reset()` を呼びます。

### `reset(self)`

* **引数**: なし
* **戻り値**: `dict` — 観測
* **概要**: スコア、フルーツ一覧、カーソルを初期化し、`next` をサンプルします。

### `step(self, action)`

* **引数**

  * `action`: `(move, drop)`

    * `move`: float in `[-1, +1]`
    * `drop`: int（0/1）
* **戻り値**: `(obs, reward, done, info)`

  * `obs`: `dict` — 観測
  * `reward`: `float` — このステップで増えたスコア（`score_after - score_before`）
  * `done`: `bool` — 終端フラグ
  * `info`: `dict` — `reason` を含む場合あり（例：`"lose_line"`, `"max_fruits"`, `"done"`）
* **概要**:

  1. カーソルを移動。
  2. `drop == 1` の場合、現在の `next` をスポーンし、次の `next` をサンプル。
  3. `substeps` 回の物理更新。
  4. 衝突解決とマージ。
  5. 終端条件をチェック。

### `render(self, screen)`

* **引数**

  * `screen`: `pygame.Surface` — 描画先サーフェス
* **戻り値**: `None`
* **概要**: コンテナ、フルーツ、カーソルプレビュー、HUD、ゲームオーバー表示を描画します。

### `human_play(self)`

* **引数**: なし
* **戻り値**: `None`
* **概要**: pygame の対話ループを実行します。

  * `←/→`: カーソル移動
  * `Space`: 落下
  * `R`: リセット
  * `Esc`: 終了

---

## 内部関数（実装詳細）

以下は、物理・マージ・サンプリングを実装するための内部関数です。

### `_get_obs(self)`

* **戻り値**: `dict` 観測
* **概要**: 内部状態から正規化観測を生成します。

### `_sample_next_type(self)`

* **戻り値**: `int` 種インデックス
* **概要**: 小さい種が出やすい重みテーブルで次フルーツ種をサンプルします。

### `_radius_for_type(self, t)`

* **引数**: `t: int`
* **戻り値**: `float` 半径（ピクセル）
* **概要**: 種から円の半径を計算します。

### `_score_for_merge(self, new_type)`

* **引数**: `new_type: int`
* **戻り値**: `int` スコア増分
* **概要**: `new_type` が生成されたときのスコア増分を計算します。

### `_spawn_fruit(self, t, x, y)`

* **引数**: `t: int`, `x: float`, `y: float`
* **戻り値**: `None`
* **概要**: `self.fruits` に新しいフルーツ（dict）を追加します。

### `_integrate(self, dt)`

* **引数**: `dt: float`
* **戻り値**: `None`
* **概要**: 重力・減衰・速度クランプを適用し、位置を積分します。

### `_solve_collisions(self)`

* **戻り値**: `None`
* **概要**:

  * 壁・床との衝突を解決します。
  * 円同士の重なりを解消し、簡易インパルス応答を適用します。

### `_merge_pass(self, max_merges=8)`

* **引数**: `max_merges: int`
* **戻り値**: `None`
* **概要**: 重なっている同種フルーツを繰り返しマージします（1回の呼び出しで最大 `max_merges` 回）。

### `_find_merge_pair(self)`

* **戻り値**: `(i, j) | None`
* **概要**: マージ対象になりうる同種フルーツのペアを、重なりが最も大きいものから選びます。

### `_check_lose(self)`

* **戻り値**: `bool`
* **概要**: いずれかのフルーツが `lose_line_y` より上に出た場合、終端とします。

### `_color_for_type(self, t)`

* **引数**: `t: int`
* **戻り値**: `(r, g, b)` タプル
* **概要**: 描画用にフルーツ種を簡易カラーパレットへ割り当てます。
