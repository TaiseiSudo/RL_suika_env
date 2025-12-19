# suika_env.py
# Minimal Suika-like environment for RL + human play (pygame only).
# pip install pygame

import math
import random
from dataclasses import dataclass

try:
    import pygame
except ImportError as e:
    raise SystemExit("pygame is required. Install with: pip install pygame") from e


@dataclass
class EnvConfig:
    # World / screen
    W: int = 480
    H: int = 720
    FPS: int = 60

    # Container walls (inside area)
    wall_thickness: int = 12
    floor_y: float = 700.0  # y increasing downward
    left_x: float = 40.0
    right_x: float = 440.0

    # Spawn / control
    # spawn_y: float = 90.0
    spawn_y: float = 100.0
    # lose_line_y: float = 70.0
    lose_line_y: float = 10.0
    move_speed: float = 360.0  # px/sec for cursor

    # Physics
    g: float = 1400.0          # px/sec^2
    substeps: int = 4
    # restitution: float = 0.05  # bounciness
    restitution: float = 0.90  # bounciness
    friction: float = 0.10     # simple tangential damping
    vel_damp: float = 0.999    # global damping
    max_speed: float = 2500.0

    # Game limits
    max_fruits: int = 70
    max_type: int = 10         # last type (like watermelon)
    seed: int | None = None


class SuikaEnv:
    """
    Action: (move, drop)
      - move: float in [-1, +1]  (cursor move left/right)
      - drop: int 0/1            (spawn current fruit)

    Observation (dict):
      - next: int
      - cursor_x: float (0..1 normalized inside container)
      - score: int
      - fruits: list of tuples (type, x_norm, y_norm, vx_norm, vy_norm, r_norm)
    """

    def __init__(self, cfg: EnvConfig | None = None):
        self.cfg = cfg or EnvConfig()
        self.rng = random.Random(self.cfg.seed)
        self.reset()

    # ---------- Public API ----------
    def reset(self):
        self.score = 0
        self.done = False
        self.t = 0.0

        self.fruits = []  # each fruit: dict {type,x,y,vx,vy,r}
        self.cursor_x = (self.cfg.left_x + self.cfg.right_x) * 0.5
        self.next_type = self._sample_next_type()
        self._last_merge_count = 0
        return self._get_obs()

    def step(self, action):
        if self.done:
            return self._get_obs(), 0.0, True, {"reason": "done"}

        move, drop = action
        move = float(max(-1.0, min(1.0, move)))
        drop = int(drop != 0)

        dt = 1.0 / self.cfg.FPS
        reward = 0.0
        info = {}

        # cursor move
        self.cursor_x += move * self.cfg.move_speed * dt
        self.cursor_x = max(self.cfg.left_x + 5.0, min(self.cfg.right_x - 5.0, self.cursor_x))

        # drop
        if drop:
            if len(self.fruits) >= self.cfg.max_fruits:
                self.done = True
                return self._get_obs(), 0.0, True, {"reason": "max_fruits"}
            self._spawn_fruit(self.next_type, self.cursor_x, self.cfg.spawn_y)
            self.next_type = self._sample_next_type()

        # physics
        sub_dt = dt / self.cfg.substeps
        prev_score = self.score
        self._last_merge_count = 0

        for _ in range(self.cfg.substeps):
            self._integrate(sub_dt)
            self._solve_collisions()
            self._merge_pass(max_merges=8)  # avoid infinite loops per frame

        # lose condition
        if self._check_lose():
            self.done = True
            info["reason"] = "lose_line"

        reward = float(self.score - prev_score)
        self.t += dt
        return self._get_obs(), reward, self.done, info

    # ---------- Observation ----------
    def _get_obs(self):
        # Normalize positions within container area
        w = (self.cfg.right_x - self.cfg.left_x)
        h = (self.cfg.floor_y - self.cfg.lose_line_y)
        cx = (self.cursor_x - self.cfg.left_x) / max(1e-6, w)

        fruits_out = []
        for f in self.fruits:
            x_n = (f["x"] - self.cfg.left_x) / max(1e-6, w)
            y_n = (f["y"] - self.cfg.lose_line_y) / max(1e-6, h)
            vx_n = f["vx"] / self.cfg.max_speed
            vy_n = f["vy"] / self.cfg.max_speed
            r_n = f["r"] / w
            fruits_out.append((f["type"], x_n, y_n, vx_n, vy_n, r_n))

        return {
            "next": int(self.next_type),
            "cursor_x": float(cx),
            "score": int(self.score),
            "fruits": fruits_out,
            "n_fruits": len(self.fruits),
            "last_merges": int(self._last_merge_count),
        }

    # ---------- Game rules ----------
    def _sample_next_type(self):
        # Suika-like: mostly small fruits
        # You can tweak weights freely.
        # types: 0..max_type
        weights = [3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0]
        weights = weights[: self.cfg.max_type + 1]
        total = sum(weights)
        r = self.rng.uniform(0.0, total)
        acc = 0.0
        for i, w in enumerate(weights):
            acc += w
            if r <= acc:
                return i
        return 0

    def _radius_for_type(self, t):
        # increasing circle size
        # tuned for W=480-ish
        base = 16.0
        return base + t * 6.0

    def _score_for_merge(self, new_type):
        # simple scoring: bigger fruit -> more score
        # you can change to match the real game.
        return int(2 ** max(0, new_type))

    def _spawn_fruit(self, t, x, y):
        r = self._radius_for_type(t)
        self.fruits.append({
            "type": int(t),
            "x": float(x),
            "y": float(y),
            "vx": 0.0,
            "vy": 0.0,
            "r": float(r),
        })

    # ---------- Physics ----------
    def _integrate(self, dt):
        g = self.cfg.g
        damp = self.cfg.vel_damp
        vmax = self.cfg.max_speed

        for f in self.fruits:
            f["vy"] += g * dt
            f["vx"] *= damp
            f["vy"] *= damp

            # clamp speed
            sp = math.hypot(f["vx"], f["vy"])
            if sp > vmax:
                k = vmax / max(1e-9, sp)
                f["vx"] *= k
                f["vy"] *= k

            f["x"] += f["vx"] * dt
            f["y"] += f["vy"] * dt

    def _solve_collisions(self):
        # walls/floor
        L, R = self.cfg.left_x, self.cfg.right_x
        floor = self.cfg.floor_y
        e = self.cfg.restitution
        fr = self.cfg.friction

        for f in self.fruits:
            r = f["r"]

            # left wall
            if f["x"] - r < L:
                f["x"] = L + r
                if f["vx"] < 0:
                    f["vx"] = -f["vx"] * (1.0 - e)
                f["vy"] *= (1.0 - fr)

            # right wall
            if f["x"] + r > R:
                f["x"] = R - r
                if f["vx"] > 0:
                    f["vx"] = -f["vx"] * (1.0 - e)
                f["vy"] *= (1.0 - fr)

            # floor
            if f["y"] + r > floor:
                f["y"] = floor - r
                if f["vy"] > 0:
                    f["vy"] = -f["vy"] * (1.0 - e)
                f["vx"] *= (1.0 - fr)

        # circle-circle collisions (naive O(n^2))
        n = len(self.fruits)
        for i in range(n):
            a = self.fruits[i]
            for j in range(i + 1, n):
                b = self.fruits[j]
                dx = b["x"] - a["x"]
                dy = b["y"] - a["y"]
                dist2 = dx * dx + dy * dy
                rs = a["r"] + b["r"]
                if dist2 >= rs * rs or dist2 <= 1e-12:
                    continue

                dist = math.sqrt(dist2)
                nx = dx / dist
                ny = dy / dist

                # positional correction (split overlap)
                overlap = (rs - dist)
                a["x"] -= nx * (overlap * 0.5)
                a["y"] -= ny * (overlap * 0.5)
                b["x"] += nx * (overlap * 0.5)
                b["y"] += ny * (overlap * 0.5)

                # relative velocity along normal
                rvx = b["vx"] - a["vx"]
                rvy = b["vy"] - a["vy"]
                vn = rvx * nx + rvy * ny
                if vn > 0:
                    continue  # separating

                # impulse (equal mass)
                e = self.cfg.restitution
                jimp = -(1.0 + e) * vn * 0.5
                a["vx"] -= jimp * nx
                a["vy"] -= jimp * ny
                b["vx"] += jimp * nx
                b["vy"] += jimp * ny

                # simple tangential friction
                tx = -ny
                ty = nx
                vt = rvx * tx + rvy * ty
                jt = -vt * self.cfg.friction * 0.5
                a["vx"] -= jt * tx
                a["vy"] -= jt * ty
                b["vx"] += jt * tx
                b["vy"] += jt * ty

    # ---------- Merging ----------
    def _merge_pass(self, max_merges=8):
        merges = 0
        while merges < max_merges:
            pair = self._find_merge_pair()
            if pair is None:
                break
            i, j = pair
            if i > j:
                i, j = j, i
            a = self.fruits[i]
            b = self.fruits[j]
            if a["type"] != b["type"]:
                break

            t = a["type"]
            if t >= self.cfg.max_type:
                # no further merge at max
                break

            # new fruit at average position, average velocity
            nx = 0.5 * (a["x"] + b["x"])
            ny = 0.5 * (a["y"] + b["y"])
            nvx = 0.5 * (a["vx"] + b["vx"])
            nvy = 0.5 * (a["vy"] + b["vy"])
            new_type = t + 1
            new_r = self._radius_for_type(new_type)

            # remove higher index first
            self.fruits.pop(j)
            self.fruits.pop(i)

            self.fruits.append({
                "type": int(new_type),
                "x": float(nx),
                "y": float(ny),
                "vx": float(nvx),
                "vy": float(nvy),
                "r": float(new_r),
            })

            self.score += self._score_for_merge(new_type)
            merges += 1
            self._last_merge_count += 1

    def _find_merge_pair(self):
        # find any overlapping same-type pair
        n = len(self.fruits)
        best = None
        best_overlap = 0.0
        for i in range(n):
            a = self.fruits[i]
            for j in range(i + 1, n):
                b = self.fruits[j]
                if a["type"] != b["type"]:
                    continue
                if a["type"] >= self.cfg.max_type:
                    continue
                dx = b["x"] - a["x"]
                dy = b["y"] - a["y"]
                rs = a["r"] + b["r"]
                dist2 = dx * dx + dy * dy
                if dist2 < rs * rs:
                    dist = math.sqrt(max(1e-12, dist2))
                    overlap = rs - dist
                    # pick the deepest overlap first for stability
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best = (i, j)
        return best

    # ---------- Termination ----------
    def _check_lose(self):
        # Simple lose: any fruit crosses lose line (top boundary)
        for f in self.fruits:
            if (f["y"] - f["r"]) < self.cfg.lose_line_y:
                return True
        return False

    # ---------- Rendering / Human play ----------
    def render(self, screen):
        # background
        screen.fill((245, 245, 245))

        # container
        L, R = int(self.cfg.left_x), int(self.cfg.right_x)
        floor = int(self.cfg.floor_y)
        lose = int(self.cfg.lose_line_y)

        # walls / floor / lose line
        pygame.draw.rect(screen, (40, 40, 40), pygame.Rect(L - 2, lose, 4, floor - lose))
        pygame.draw.rect(screen, (40, 40, 40), pygame.Rect(R - 2, lose, 4, floor - lose))
        pygame.draw.rect(screen, (40, 40, 40), pygame.Rect(L, floor - 2, R - L, 4))
        pygame.draw.line(screen, (200, 60, 60), (L, lose), (R, lose), 2)

        # fruits
        for f in self.fruits:
            color = self._color_for_type(f["type"])
            pygame.draw.circle(screen, color, (int(f["x"]), int(f["y"])), int(f["r"]))
            pygame.draw.circle(screen, (20, 20, 20), (int(f["x"]), int(f["y"])), int(f["r"]), 2)

        # cursor + next preview
        cx = int(self.cursor_x)
        cy = int(self.cfg.spawn_y)
        nt = self.next_type
        nr = int(self._radius_for_type(nt))
        pygame.draw.circle(screen, (0, 0, 0), (cx, cy), nr, 2)

        # HUD
        font = pygame.font.SysFont(None, 24)
        s1 = font.render(f"Score: {self.score}", True, (20, 20, 20))
        s2 = font.render(f"Next: {nt}", True, (20, 20, 20))
        s3 = font.render(f"Fruits: {len(self.fruits)}  Merges(last): {self._last_merge_count}", True, (20, 20, 20))
        screen.blit(s1, (16, 8))
        screen.blit(s2, (16, 32))
        screen.blit(s3, (16, 56))

        if self.done:
            big = pygame.font.SysFont(None, 56)
            msg = big.render("GAME OVER", True, (200, 60, 60))
            screen.blit(msg, (self.cfg.W // 2 - msg.get_width() // 2, self.cfg.H // 2 - 40))

    def _color_for_type(self, t):
        # simple palette
        palette = [
            (255, 200, 200),
            (255, 220, 160),
            (255, 240, 140),
            (210, 255, 170),
            (170, 240, 255),
            (170, 200, 255),
            (210, 170, 255),
            (255, 170, 220),
            (255, 180, 120),
            (180, 255, 120),
            (120, 255, 200),
        ]
        return palette[t % len(palette)]

    def human_play(self):
        pygame.init()
        screen = pygame.display.set_mode((self.cfg.W, self.cfg.H))
        pygame.display.set_caption("Suika-like Env (Minimal)")
        clock = pygame.time.Clock()

        self.reset()
        running = True
        while running:
            move = 0.0
            drop = 0

            # events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        self.reset()
                    elif event.key == pygame.K_SPACE:
                        drop = 1

            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                move -= 1.0
            if keys[pygame.K_RIGHT]:
                move += 1.0

            # step
            self.step((move, drop))

            # render
            self.render(screen)
            pygame.display.flip()
            clock.tick(self.cfg.FPS)

        pygame.quit()


if __name__ == "__main__":
    env = SuikaEnv(EnvConfig(seed=0))
    env.human_play()
