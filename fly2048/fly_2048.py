#!/usr/bin/env python3
"""Unofficial adapter: let the MaleCNS fly brain play GameWorld's 2048.

Not a fork of fly.ai and not affiliated with its authors.

Board state drives the fly's own visual projection neurons. The frozen
connectome runs for a short window, then identified descending neurons
vote for up / right / down / left. The dashboard shows GameWorld 2048 on
the left and every positioned neuron on the right.

Brain: fly.ai / flybrain, https://github.com/alextitonis/fly.ai
(MIT, Copyright 2026 alextitonis). MaleCNS v1.0 data is CC BY 4.0
from FlyEM (HHMI Janelia) and collaborators; downloaded at runtime.

Game snapshot: GameWorld `01_2048` from
https://github.com/gameworld-project/GameWorld-Games
(based on Gabriele Cirulli's MIT 2048; LICENSE.txt in that folder).

    python fly_2048.py
    python fly_2048.py --device cpu --port 8778
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import subprocess
import tempfile
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from flybrain import FlyBrain
from flybrain.eyes import FeatureDetectors

HERE = Path(__file__).resolve().parent
GAME_DIR = HERE.parent / "games" / "01_2048"
PAGE = (HERE / "dashboard.html").read_text(encoding="utf-8")

STEPS_PER_MOVE = 20  # 400 ms of brain time at dt=0.020
STEER_WINDOW = 20
WARMUP_STEPS = 80
MAX_SPIKES = 6000

MOVE_NAME = {0: "up", 1: "right", 2: "down", 3: "left"}
MOTOR_LABELS = {
    "steer": ("DNa02", "left / right"),
    "forward": ("DNg100", "up"),
    "backward": ("MDN", "down"),
    "escape": ("DNp01", "escape"),
}

INJECT_CSS = """
<style>
.game-intro,.game-explanation,.controls{display:none!important}
.container{margin:12px auto}
body{margin:0;background:#faf8ef}
</style>
"""


def _slide_line(line: list[int]) -> list[int]:
    tiles = [v for v in line if v]
    out: list[int] = []
    skip = False
    for i, value in enumerate(tiles):
        if skip:
            skip = False
            continue
        if i + 1 < len(tiles) and tiles[i + 1] == value:
            out.append(value * 2)
            skip = True
        else:
            out.append(value)
    out.extend([0] * (len(line) - len(out)))
    return out


def apply_move(board: list[list[int]], direction: int) -> tuple[list[list[int]], bool]:
    """Slide a column-major 4x4 board (board[x][y], x=col, y=row)."""
    next_board = [col[:] for col in board]
    moved = False
    if direction == 0:  # up
        for x in range(4):
            new = _slide_line([next_board[x][y] for y in range(4)])
            for y in range(4):
                if next_board[x][y] != new[y]:
                    moved = True
                next_board[x][y] = new[y]
    elif direction == 2:  # down
        for x in range(4):
            new = _slide_line([next_board[x][y] for y in range(3, -1, -1)])
            for i, y in enumerate(range(3, -1, -1)):
                if next_board[x][y] != new[i]:
                    moved = True
                next_board[x][y] = new[i]
    elif direction == 3:  # left
        for y in range(4):
            new = _slide_line([next_board[x][y] for x in range(4)])
            for x in range(4):
                if next_board[x][y] != new[x]:
                    moved = True
                next_board[x][y] = new[x]
    elif direction == 1:  # right
        for y in range(4):
            new = _slide_line([next_board[x][y] for x in range(3, -1, -1)])
            for i, x in enumerate(range(3, -1, -1)):
                if next_board[x][y] != new[i]:
                    moved = True
                next_board[x][y] = new[i]
    return next_board, moved


def legal_moves(board: list[list[int]]) -> list[int]:
    return [d for d in range(4) if apply_move(board, d)[1]]


def _log_mass(value: int) -> float:
    return 0.0 if value <= 0 else float(np.log2(value))


class BoardEncoder:
    """Map a 2048 board onto the fly's identified visual projection neurons.

    Columns are azimuth (left two → left eye, right two → right eye). Tile
    value is object size. The highest tile is the chase target (LC10a);
    board fill is threat (LC4); growth of the max tile is looming (LPLC2);
    2s and 4s are small objects (LPLC1).
    """

    def __init__(self, brain: FlyBrain):
        self.features = FeatureDetectors(brain, loom_size=0.6)
        self.prev_max = 0
        self.prev_filled = 0

    def inject(self, board: list[list[int]]) -> list:
        filled = sum(1 for x in range(4) for y in range(4) if board[x][y])
        max_val = max((board[x][y] for x in range(4) for y in range(4)), default=0)
        max_x, max_y = 1, 1
        left_mass = right_mass = 0.0
        top_mass = bot_mass = 0.0
        shots: list[tuple[str, float, float]] = []
        for x in range(4):
            for y in range(4):
                value = board[x][y]
                if not value:
                    continue
                mass = _log_mass(value)
                if x < 2:
                    left_mass += mass
                else:
                    right_mass += mass
                if y < 2:
                    top_mass += mass
                else:
                    bot_mass += mass
                if value == max_val:
                    max_x, max_y = x, y
                if value <= 4:
                    dx = (x - 1.5) * 40.0
                    shots.append((f"t{x}{y}", dx, 10.0 + 2.0 * value))

        dx = (max_x - 1.5) * 48.0
        size = 12.0 + 6.0 * _log_mass(max_val)
        grew = max_val > self.prev_max or filled > self.prev_filled
        if grew:
            size += 8.0
        threat = float(np.clip(filled / 16.0 + 0.15 * (top_mass - bot_mass) / 8.0, 0, 1))
        # Bias chase toward the heavier half so DNa02 can steer with the mass.
        if left_mass > right_mass + 0.5:
            dx = min(dx, -24.0)
        elif right_mass > left_mass + 0.5:
            dx = max(dx, 24.0)

        self.prev_max, self.prev_filled = max_val, filled
        inject = self.features.inject((dx, size), shots, threat)
        # Vertical: extra looming when the top is heavy (maps onto DNp01 take-off → up).
        extra = []
        top_drive = float(np.clip((top_mass - bot_mass) / 10.0, 0, 0.5))
        bot_drive = float(np.clip((bot_mass - top_mass) / 10.0, 0, 0.5))
        if top_drive > 0:
            extra.append((self.features.cells["loom"]["L"], top_drive * 0.4))
            extra.append((self.features.cells["loom"]["R"], top_drive * 0.4))
            self.features.last["loomL"] = min(0.8, self.features.last.get("loomL", 0) + top_drive)
            self.features.last["loomR"] = min(0.8, self.features.last.get("loomR", 0) + top_drive)
        if bot_drive > 0:
            extra.append((self.features.cells["shot"]["L"], bot_drive * 0.4))
            extra.append((self.features.cells["shot"]["R"], bot_drive * 0.4))
            self.features.last["shotL"] = min(0.8, self.features.last.get("shotL", 0) + bot_drive)
            self.features.last["shotR"] = min(0.8, self.features.last.get("shotR", 0) + bot_drive)
        return inject + extra


class Decoder:
    """Descending-neuron spikes → 2048 move (0 up, 1 right, 2 down, 3 left)."""

    def __init__(self, groups: dict[str, np.ndarray], n: int):
        self.names = list(groups)
        self.col = {name: i for i, name in enumerate(self.names)}
        self.groups = groups
        self.history: deque[np.ndarray] = deque(maxlen=STEER_WINDOW)
        self.mask = np.zeros(n, dtype=bool)

    def reset_window(self) -> None:
        self.history.clear()

    def observe(self, fired: np.ndarray) -> None:
        counts = np.zeros(len(self.names), dtype=np.float32)
        self.mask[:] = False
        if len(fired):
            self.mask[fired] = True
        for name, idx in self.groups.items():
            counts[self.col[name]] = float(self.mask[idx].sum())
        self.history.append(counts)

    def count(self, *groups: str) -> float:
        if not self.history:
            return 0.0
        recent = np.sum(list(self.history), axis=0)
        return float(sum(recent[self.col[name]] for name in groups if name in self.col))

    def snapshot(self) -> dict[str, float]:
        return {name: self.count(name) for name in self.names}

    def scores(self) -> dict[int, float]:
        left = self.count("steer_L")
        right = self.count("steer_R")
        up = self.count("forward_L", "forward_R") + 0.35 * self.count("escape_L", "escape_R")
        down = self.count("backward_L", "backward_R")
        return {0: up, 1: right, 2: down, 3: left}

    def choose(self, legal: list[int], rng: np.random.Generator) -> int:
        if not legal:
            return 0
        scores = self.scores()
        ranked = sorted(legal, key=lambda move: (scores.get(move, 0.0), rng.random()), reverse=True)
        return ranked[0]


class Fly2048:
    def __init__(self, device: str | None = None, seed: int = 64):
        print("loading connectome (first run downloads ~260 MB)...", flush=True)
        self.brain = FlyBrain(device=device, seed=seed)
        self.encoder = BoardEncoder(self.brain)
        self.decoder = Decoder(self.brain.groups, self.brain.n)
        self.rng = np.random.default_rng(seed)
        self.step_ms = 0.0
        self.frame_spikes = np.empty(0, np.int64)
        n_syn = int(len(self.brain.indices)) if hasattr(self.brain, "indices") else 0
        print(
            f"brain ready: {self.brain.n:,} neurons, {n_syn:,} connections on {self.brain.device}",
            flush=True,
        )
        print("warming up spontaneous activity (numba compiles on the first steps)...", flush=True)
        t0 = time.perf_counter()
        for _ in range(WARMUP_STEPS):
            self.brain.step()
        print(f"warmup done in {time.perf_counter() - t0:.1f}s", flush=True)

    def think(self, board: list[list[int]]) -> dict:
        legal = legal_moves(board)
        inject = self.encoder.inject(board)
        self.decoder.reset_window()
        fired_all: list[np.ndarray] = []
        t0 = time.perf_counter()
        for _ in range(STEPS_PER_MOVE):
            fired = self.brain.step(inject=inject)
            if isinstance(fired, list):
                fired = fired[0]
            self.decoder.observe(fired)
            fired_all.append(fired)
        self.step_ms = (time.perf_counter() - t0) * 1000
        self.frame_spikes = np.concatenate(fired_all) if fired_all else np.empty(0, np.int64)
        move = self.decoder.choose(legal, self.rng)
        now = {name: bool(np.isin(idx, self.frame_spikes).any()) for name, idx in self.brain.groups.items()}
        return {
            "move": int(move),
            "move_name": MOVE_NAME[move],
            "legal": legal,
            "counts": self.decoder.snapshot(),
            "now": now,
            "drive": dict(self.encoder.features.last),
            "ms": round(self.step_ms, 1),
            "total": int(len(self.frame_spikes)),
        }


class Dashboard:
    def __init__(self, fly: Fly2048, port: int = 8778):
        self.fly = fly
        self.port = port
        brain = fly.brain
        if brain.positions is None:
            raise SystemExit("brain.npz has no positions; run `flybrain build`")
        ok = ~np.isnan(brain.positions).any(axis=1)
        self.pos_index = np.full(brain.n, -1, np.int32)
        self.pos_index[ok] = np.arange(ok.sum(), dtype=np.int32)
        xy = brain.positions[ok][:, [0, 2]].copy()
        side = brain.side[ok]
        if np.nanmean(xy[side == "R", 0]) < np.nanmean(xy[side == "L", 0]):
            xy[:, 0] = -xy[:, 0]
        lo, hi = np.percentile(xy, 0.2, axis=0), np.percentile(xy, 99.8, axis=0)
        scale = (hi - lo).max()
        pad = (scale - (hi - lo)) / 2
        norm = np.clip((xy - lo + pad) / scale, 0, 1) * 1000
        groups: dict[str, list[int]] = {}
        for name, idx in brain.groups.items():
            groups[name] = [int(i) for i in self.pos_index[idx] if i >= 0]
        for channel, per_side in fly.encoder.features.cells.items():
            for s, idx in per_side.items():
                groups[f"{channel}{s}"] = [int(i) for i in self.pos_index[idx] if i >= 0]
        n_syn = int(len(brain.indices)) if hasattr(brain, "indices") else 0
        self.static = json.dumps({
            "x": norm[:, 0].round().astype(int).tolist(),
            "y": norm[:, 1].round().astype(int).tolist(),
            "groups": groups,
            "labels": MOTOR_LABELS,
            "neurons": int(brain.n),
            "connections": n_syn,
            "mapped": int(ok.sum()),
        })
        self.cond = threading.Condition()
        self.payload: str | None = None
        self.seq = 0
        self.rng = np.random.default_rng(0)
        self.lock = threading.Lock()

    def publish(self, result: dict) -> None:
        spikes = self.pos_index[self.fly.frame_spikes]
        spikes = spikes[spikes >= 0]
        if len(spikes) > MAX_SPIKES:
            spikes = self.rng.choice(spikes, MAX_SPIKES, replace=False)
        payload = {
            "spikes": spikes.tolist(),
            "total": result["total"],
            "counts": result["counts"],
            "now": result["now"],
            "drive": result["drive"],
            "ms": result["ms"],
            "move": result["move"],
            "move_name": result["move_name"],
        }
        with self.cond:
            self.payload = json.dumps(payload)
            self.seq += 1
            self.cond.notify_all()

    def start(self, open_browser: bool = True) -> None:
        class ReuseHTTPServer(ThreadingHTTPServer):
            allow_reuse_address = True

        server = ReuseHTTPServer(("127.0.0.1", self.port), _handler(self))
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{self.port}/"
        print(f"dashboard: {url}", flush=True)
        if open_browser:
            webbrowser.open(url)

    def serve_forever(self) -> None:
        print("fly is playing 2048. Ctrl+C to stop.", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nstopped.", flush=True)


def _handler(dash: Dashboard):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body: bytes, ctype: str, extra: dict[str, str] | None = None) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if extra:
                for key, value in extra.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path == "/reset":
                dash.fly.encoder.prev_max = 0
                dash.fly.encoder.prev_filled = 0
                dash.fly.encoder.features.previous = {}
                dash.fly.decoder.reset_window()
                return self._send(b'{"ok": true}', "application/json")
            if self.path != "/think":
                return self.send_error(404)
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            board = body.get("board")
            if not isinstance(board, list) or len(board) != 4:
                return self.send_error(400, "board must be 4x4")
            with dash.lock:
                result = dash.fly.think(board)
            dash.publish(result)
            payload = json.dumps({
                "move": result["move"],
                "move_name": result["move_name"],
                "legal": result["legal"],
                "ms": result["ms"],
            }).encode()
            return self._send(payload, "application/json")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(PAGE.encode(), "text/html; charset=utf-8")
            if self.path == "/static.json":
                return self._send(dash.static.encode(), "application/json")
            if self.path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                seen = -1
                try:
                    while True:
                        with dash.cond:
                            fresh = dash.cond.wait_for(lambda: dash.seq != seen, timeout=15)
                            seen, data = dash.seq, dash.payload
                        self.wfile.write(
                            f"data: {data}\n\n".encode() if fresh and data else b": ping\n\n"
                        )
                        self.wfile.flush()
                except OSError:
                    return
            if self.path.startswith("/game/"):
                return self._serve_game(self.path[len("/game/"):])
            return self.send_error(404)

        def _serve_game(self, rel: str) -> None:
            rel = rel.split("?", 1)[0]
            if rel in ("",):
                rel = "index.html"
            path = (GAME_DIR / rel).resolve()
            if GAME_DIR.resolve() not in path.parents and path != GAME_DIR.resolve():
                return self.send_error(404)
            if not path.is_file():
                return self.send_error(404)
            data = path.read_bytes()
            if path.name == "index.html":
                html = data.decode("utf-8")
                html = html.replace("</head>", INJECT_CSS + "\n</head>")
                data = html.encode("utf-8")
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            return self._send(data, ctype)

    return Handler


def _webm_to_mp4(webm: Path, mp4: Path) -> None:
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("imageio-ffmpeg is required to write mp4") from exc
    cmd = [
        ffmpeg, "-y", "-i", str(webm),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(mp4),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not mp4.is_file():
        raise RuntimeError(result.stderr[-800:] or "ffmpeg failed to write mp4")


def record_session(
    url: str,
    out: Path,
    seconds: float | None = None,
    until_over: bool = False,
    max_seconds: float = 1200,
    width: int = 1600,
    height: int = 900,
    reset: bool = True,
) -> Path:
    """Open the live dashboard in Chrome and write a video to `out`."""
    import os
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("playwright is required for --record: pip install playwright") from exc

    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        str(Path.home() / "Library" / "Caches" / "ms-playwright"),
    )
    until_over = until_over or seconds is None
    out = out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if until_over:
        print(f"recording full game until over (max {max_seconds:.0f}s) → {out}", flush=True)
    else:
        print(f"recording {seconds:.0f}s → {out}", flush=True)

    GAME_OVER_JS = """() => {
      const win = document.getElementById('game')?.contentWindow;
      const st = win?.gameAPI?.getState?.();
      if (st && st.terminal && st.terminal.isTerminal) return st.terminal.outcome || 'over';
      return '';
    }"""
    SCORE_JS = """() => document.getElementById('scoreline')?.textContent || ''"""

    with tempfile.TemporaryDirectory(prefix="fly2048-") as raw:
        raw_dir = Path(raw)
        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--autoplay-policy=no-user-gesture-required"],
            )
            context = browser.new_context(
                viewport={"width": width, "height": height},
                record_video_dir=str(raw_dir),
                record_video_size={"width": width, "height": height},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_function(
                "() => (document.getElementById('stats')?.textContent || '').includes('neurons')",
                timeout=60_000,
            )
            page.wait_for_function(
                "() => document.getElementById('game')?.contentWindow?.gameAPI",
                timeout=120_000,
            )
            if reset:
                page.click("#reset")
                page.wait_for_timeout(800)
            page.wait_for_function(
                "() => (document.getElementById('spk')?.textContent || '').includes('spikes')",
                timeout=180_000,
            )
            print("capturing gameplay", flush=True)
            if until_over:
                deadline = time.time() + max_seconds
                outcome = ""
                while time.time() < deadline:
                    outcome = page.evaluate(GAME_OVER_JS) or ""
                    print(f"  {page.evaluate(SCORE_JS)}", flush=True)
                    if outcome:
                        print(f"game over: {outcome}", flush=True)
                        break
                    page.wait_for_timeout(4000)
                else:
                    print("timed out before game over; saving what we have", flush=True)
                page.wait_for_timeout(3000)
            else:
                page.wait_for_timeout(int(seconds * 1000))
            video = page.video
            page.close()
            context.close()
            browser.close()
            webm = Path(video.path()) if video else None
        if webm is None or not webm.is_file():
            found = list(raw_dir.glob("*.webm"))
            if not found:
                raise RuntimeError("playwright did not write a video")
            webm = found[0]
        staged = webm
        if out.suffix.lower() == ".mp4":
            staged = raw_dir / "flybrain-2048.mp4"
            _webm_to_mp4(webm, staged)
        shutil.copy2(staged, out)
    print(f"saved {out} ({out.stat().st_size / 1e6:.1f} MB)", flush=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Fly brain plays GameWorld 2048")
    parser.add_argument("--device", default="auto", help="cpu, cuda, or auto")
    parser.add_argument("--port", type=int, default=8778)
    parser.add_argument("--seed", type=int, default=64)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--record",
        type=float,
        nargs="?",
        const=40.0,
        default=None,
        metavar="SECONDS",
        help="record the dashboard to video (default 40s) and exit",
    )
    parser.add_argument(
        "--until-over",
        action="store_true",
        help="with --record, keep recording until the 2048 game ends",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="video path used with --record",
    )
    args = parser.parse_args()
    if not GAME_DIR.is_dir():
        raise SystemExit(f"2048 game not found: {GAME_DIR}")
    fly = Fly2048(device=args.device, seed=args.seed)
    dash = Dashboard(fly, port=args.port)
    dash.start(open_browser=not args.no_browser and args.record is None and not args.until_over)
    if args.record is not None or args.until_over:
        default_name = "flybrain-2048-full.mp4" if args.until_over else "flybrain-2048.mp4"
        out = Path(args.out) if args.out else HERE.parent / "assets" / default_name
        time.sleep(0.4)
        record_session(
            f"http://127.0.0.1:{args.port}/",
            out,
            seconds=None if args.until_over else args.record,
            until_over=args.until_over,
        )
        return
    dash.serve_forever()


if __name__ == "__main__":
    main()
