# RL_suika_env
RL用スイカゲーム風環境


1. 概要
- スイカゲーム風（落下×衝突×同種マージ）の簡易シミュレーション環境。
- 強化学習（RL）で利用可能な step/reset API と、pygame による可視化・人間操作を提供。
- 依存は pygame のみ。物理は純Pythonで簡易実装（円同士の衝突＋重力）。

------------------------------------------------------------
2. 主要クラス仕様

2.1 EnvConfig (dataclass)
役割:
- 環境パラメータ（画面/コンテナ/物理/ゲーム制約）を一括管理する設定クラス。

主要フィールドは「3. Config設定値一覧」を参照。

------------------------------------------------------------
2.2 SuikaEnv
役割:
- RL向けの環境本体。
- Action入力 → 物理更新 → 衝突解決 → マージ処理 → 観測/報酬/終端を返す。
- pygame描画と人間操作（キー入力）も内包。

----------------------------------------
(公開API / 外部から呼ぶ想定)

[SuikaEnv.__init__(cfg: EnvConfig | None) -> None]
- 引数:
  - cfg: EnvConfig または None（Noneならデフォルト設定）
- 戻り値: なし
- 概要:
  - 環境初期化。乱数seedを反映し、内部状態をreset。

[SuikaEnv.reset() -> dict]
- 引数: なし
- 戻り値:
  - obs: dict（観測。詳細は 4. 観測フォーマット）
- 概要:
  - スコア・盤面・カーソル・next fruit を初期化。

[SuikaEnv.step(action: tuple[float, int]) -> tuple[dict, float, bool, dict]]
- 引数:
  - action: (move, drop)
    - move: float [-1, +1]   (落とす位置カーソルの左右移動指令)
    - drop: int (0/1)        (1なら現在カーソル位置でフルーツを落下)
- 戻り値:
  - obs: dict      観測
  - reward: float  報酬（基本は score増分）
  - done: bool     終端フラグ
  - info: dict     補足情報（例: reason）
- 概要:
  - 1フレーム分の処理（移動→任意でspawn→物理更新→衝突解決→マージ）を実行。
  - 終端条件: lose_line越え、または max_fruits 超過。

[SuikaEnv.render(screen: pygame.Surface) -> None]
- 引数:
  - screen: pygame.Surface（描画先）
- 戻り値: なし
- 概要:
  - 現在盤面を描画（コンテナ枠、フルーツ、カーソル、スコア等）。

[SuikaEnv.human_play() -> None]
- 引数: なし
- 戻り値: なし
- 概要:
  - pygameウィンドウを起動し、人間操作プレイを行う。
  - 操作: ←→ 移動 / Space 落下 / R リセット / Esc 終了

----------------------------------------
(内部処理 / 参考: RL利用時は基本的に触れない)

- _get_obs() -> dict
  観測dictを生成（正規化済み座標、盤面フルーツ一覧など）。

- _sample_next_type() -> int
  次に落ちるフルーツ種を重み付きランダムで決定。

- _radius_for_type(t: int) -> float
  種類 t に対応する半径（px）を返す。

- _score_for_merge(new_type: int) -> int
  マージによる加点（新しい種類に基づく）を返す。

- _spawn_fruit(t: int, x: float, y: float) -> None
  指定位置にフルーツを生成。

- _integrate(dt: float) -> None
  重力などを使って速度・位置を更新。

- _solve_collisions() -> None
  壁/床との衝突、および円同士衝突を解決（簡易反発＋摩擦）。

- _merge_pass(max_merges: int = 8) -> None
  同種の重なりペアを見つけてマージ（1フレーム最大回数制限あり）。

- _find_merge_pair() -> tuple[int, int] | None
  マージ候補ペア（最も深く重なっている同種ペア）を探索。

- _check_lose() -> bool
  lose_lineより上にフルーツが侵入したら True。

- _color_for_type(t: int) -> tuple[int, int, int]
  描画用の色を返す。

------------------------------------------------------------
3. Config設定値一覧 (EnvConfig)

[画面/コンテナ]
- W, H: ウィンドウサイズ(px)
- FPS: シミュレーション更新頻度(Hz)
- wall_thickness: (描画上の)壁厚
- floor_y: 床のy座標(px)
- left_x, right_x: コンテナ左右のx座標(px)
- spawn_y: 落下フルーツ生成のy座標(px)
- lose_line_y: ゲームオーバー判定の基準線(y)。フルーツが上側へ越えると負け

[操作]
- move_speed: カーソル移動速度(px/sec)

[物理]
- g: 重力加速度(px/sec^2)
- substeps: 1フレームを何分割して物理更新するか（多いほど安定・重い）
- restitution: 反発係数（大きいほど跳ねる）
- friction: 摩擦（壁/床や衝突での接線方向減衰）
- vel_damp: 全体の速度減衰（安定化用）
- max_speed: 速度上限(px/sec)

[ゲーム制約]
- max_fruits: 盤面の最大フルーツ数（超えるとdone）
- max_type: フルーツ種類の最大（この種類以上はマージしない）
- seed: 乱数シード（Noneなら非固定）

------------------------------------------------------------
4. 観測フォーマット (reset/step の戻り obs)

obs: dict
- "next": int
  次に落とすフルーツ種類ID (0..max_type)

- "cursor_x": float
  落下位置カーソルx（コンテナ内で 0..1 に正規化）

- "score": int
  現在スコア

- "fruits": list[tuple]
  各要素は (type, x_norm, y_norm, vx_norm, vy_norm, r_norm)
  - type: int フルーツ種類ID
  - x_norm: float コンテナ内 0..1 正規化x
  - y_norm: float lose_line_y..floor_y を 0..1 正規化y
  - vx_norm, vy_norm: float 速度を max_speed で割った値
  - r_norm: float 半径をコンテナ幅で割った値

- "n_fruits": int
  フルーツ数

- "last_merges": int
  直近フレームで発生したマージ回数

------------------------------------------------------------
5. 簡易サンプルコード

5.1 人間操作（ローカルで遊ぶ）
- 事前:
  pip install pygame
- 実行:
  python suika_env.py

またはコードから:
------------------------------------------------
from suika_env import SuikaEnv, EnvConfig
env = SuikaEnv(EnvConfig(seed=0))
env.human_play()
------------------------------------------------

5.2 RL利用（最小例: ランダム/ルールベース）
------------------------------------------------
from suika_env import SuikaEnv, EnvConfig

env = SuikaEnv(EnvConfig(seed=0))
obs = env.reset()

for step_i in range(5000):
    # 例: ランダムに左右移動し、ときどき落下
    move = 0.0  # [-1, 1]
    drop = 1 if (step_i % 30 == 0) else 0

    obs, reward, done, info = env.step((move, drop))

    # 学習用: obs を状態として保存、reward を蓄積、doneでepisode終了など
    if done:
        obs = env.reset()
------------------------------------------------
