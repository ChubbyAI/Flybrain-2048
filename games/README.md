# Games

This folder vendors **GameWorld**'s 2048 snapshot, not a fresh clone of Cirulli's repo.

## 2048 — GameWorld `01_2048`

| | |
| --- | --- |
| Snapshot | `games/01_2048/` |
| GameWorld games library | https://github.com/gameworld-project/GameWorld-Games |
| GameWorld project | https://gameworld-project.github.io/ |
| Technical report | https://arxiv.org/abs/2604.07429 |
| Local rights note | `01_2048/RIGHTS.md` |
| Cirulli MIT text | `01_2048/LICENSE.txt` |

GameWorld is a 34-game browser library for multimodal agents (ECCV 2026).
`01_2048` is their packaged copy of 2048 with a `window.gameAPI` so an agent can
read the board (`game_state.environment`) and score, plus a seeded RNG for
reproducible episodes.

GameWorld's own rights file for this directory says:

- Identified source: **2048** by Gabriele Cirulli
- Source URL: https://github.com/gabrielecirulli/2048
- License / rights status: **MIT**
- Relationship: this local directory follows Cirulli's implementation

The GameWorld-Games README states the library is for **educational and research
use**; third-party materials remain with their copyright owners.

The snapshot is trimmed to files the iframe actually loads. Unused GameWorld extras
(scss sources, autoplay AI, polyfills, app icons, duplicate fonts) were removed.
The fly dashboard talks to the game through the existing `gameAPI` / `__gameManager`
hooks GameWorld already added.

One local addition: `LICENSE.txt` is Gabriele Cirulli's MIT text from
https://github.com/gabrielecirulli/2048/blob/master/LICENSE.txt, kept next
to the vendored sources.
