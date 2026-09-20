# FLYBRAIN × 2048

**English** | [简体中文](README.zh-CN.md)

An unofficial demo: the open-source [fly.ai](https://github.com/alextitonis/fly.ai) MaleCNS connectome (166,700 neurons) plays GameWorld’s [2048](https://github.com/gameworld-project/GameWorld-Games). The puzzle in that snapshot is [Gabriele Cirulli’s 2048](https://github.com/gabrielecirulli/2048).

This repo is an adapter, not a fork, and is not affiliated with those projects.

## Demo

<video src="assets/flybrain-2048-full.mp4" controls width="100%"></video>

[![FLYBRAIN × 2048](assets/flybrain-2048.gif)](assets/flybrain-2048-full.mp4)

One full game, new board to Game Over. The brain is **not trained**; this is a frozen MaleCNS readout on GameWorld `01_2048`. [Full MP4](assets/flybrain-2048-full.mp4)

| Score | Max tile | Duration | Outcome |
| --- | --- | --- | --- |
| 2896 | 256 | ~132 s | Game over |

1600 × 900 · SHA-256 `51cea57958549ea2c149b4e4d852cd841b62d7d78aa00a1b9206bd83c899ab8a` · [manifest](assets/recording_manifest.json)

## How it works

The adapter writes the 2048 board onto identified visual projection neurons, steps the leaky integrate-and-fire connectome, and reads identified descending neurons as arrow keys.

```
2048 board
  └─> LC10a  chase the max tile
      LPLC2  looming / growth
      LC4    crowding as threat
      LPLC1  2s and 4s as small objects
        └─> 166,700-neuron MaleCNS (LIF)
              └─> DNa02            left / right
                  DNg100 + DNp01   up
                  MDN              down
                    └─> 2048
```

| Path | What lives there |
| --- | --- |
| [`fly2048/`](fly2048/) | adapter: board → neurons → moves, plus the dashboard |
| [`third_party/fly.ai/flybrain/`](third_party/fly.ai/flybrain/) | fly.ai neuron simulation (`brain.py`, `eyes.py`, `build.py`, `data.py`) |
| [`games/01_2048/`](games/01_2048/) | GameWorld’s 2048 snapshot |

The ~260 MB MaleCNS weights are **not** in this folder. They download on first run (CC BY 4.0, FlyEM / HHMI Janelia).

## Run

Python 3.10+ (3.12 preferred).

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python fly2048/fly_2048.py
```

Opens http://127.0.0.1:8778/ — 2048 on the left, the nervous system on the right.

Copy [`.env.example`](.env.example) to `.env` only for local path overrides. This folder has no secrets, private keys, or cloud credentials.

### Record a run (optional)

Needs Playwright and ffmpeg; not required to play.

```sh
pip install -r requirements-record.txt
python -m playwright install chromium
python fly2048/fly_2048.py --record 40 --out assets/flybrain-2048.mp4
python fly2048/fly_2048.py --until-over --out assets/flybrain-2048-full.mp4
```

## Credits

File-by-file provenance: [`SOURCE_MANIFEST.json`](SOURCE_MANIFEST.json).

**fly.ai / flybrain** — [alextitonis/fly.ai](https://github.com/alextitonis/fly.ai), MIT, Copyright (c) 2026 alextitonis. PyPI: [flybrain](https://pypi.org/project/flybrain/). Connectome data: MaleCNS v1.0, **CC BY 4.0**, [attribution terms](https://male-cns.janelia.org/download/).

**2048** — GameWorld `01_2048` from [GameWorld-Games](https://github.com/gameworld-project/GameWorld-Games), which packages [gabrielecirulli/2048](https://github.com/gabrielecirulli/2048) (MIT, Copyright (c) 2014 Gabriele Cirulli). License copy: `games/01_2048/LICENSE.txt`.

This adapter is Alpha. Third-party licenses stay in their own folders and are not mixed into the root [`LICENSE`](LICENSE).
