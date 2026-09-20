# FLYBRAIN × 2048

[English](README.md) | **简体中文**

非官方演示：开源项目 [fly.ai](https://github.com/alextitonis/fly.ai) 的 MaleCNS 连接组（166,700 个神经元）来玩 GameWorld 的 [2048](https://github.com/gameworld-project/GameWorld-Games)。该快照里的谜题来自 [Gabriele Cirulli 的 2048](https://github.com/gabrielecirulli/2048)。

本仓库是适配器，不是 fork，也不隶属于上述项目。

## 演示

<video src="assets/flybrain-2048-full.mp4" controls width="100%"></video>

[![FLYBRAIN × 2048](assets/flybrain-2048.gif)](assets/flybrain-2048-full.mp4)

一整局：新开局打到 Game Over。这里**没有训练**脑子，只是把冻结的 MaleCNS 接到 GameWorld `01_2048` 上读出方向。[完整 MP4](assets/flybrain-2048-full.mp4)

| 分数 | 最大砖 | 时长 | 结果 |
| --- | --- | --- | --- |
| 2896 | 256 | 约 132 秒 | Game over |

1600 × 900 · SHA-256 `51cea57958549ea2c149b4e4d852cd841b62d7d78aa00a1b9206bd83c899ab8a` · [录制清单](assets/recording_manifest.json)

## 原理

适配器把 2048 棋盘写到已鉴定的视觉投射神经元，推进 LIF 连接组，再从下行神经元读出方向键。

```
2048 棋盘
  └─> LC10a  追逐最大砖
      LPLC2  逼近 / 增长
      LC4    拥挤即威胁
      LPLC1  2 和 4 视为小物体
        └─> 166,700 神经元 MaleCNS（LIF）
              └─> DNa02            左 / 右
                  DNg100 + DNp01   上
                  MDN              下
                    └─> 2048
```

| 路径 | 内容 |
| --- | --- |
| [`fly2048/`](fly2048/) | 适配器：棋盘 → 神经元 → 走子，以及仪表盘 |
| [`third_party/fly.ai/flybrain/`](third_party/fly.ai/flybrain/) | fly.ai 神经元仿真（`brain.py`、`eyes.py`、`build.py`、`data.py`） |
| [`games/01_2048/`](games/01_2048/) | GameWorld 的 2048 快照 |

约 260 MB 的 MaleCNS 权重**不在**本目录。首次运行时下载（CC BY 4.0，FlyEM / HHMI Janelia）。

## 运行

Python 3.10+（建议 3.12）。

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python fly2048/fly_2048.py
```

打开 http://127.0.0.1:8778/ — 左侧 2048，右侧神经系统。

只有需要覆盖本机路径时才把 [`.env.example`](.env.example) 复制成 `.env`。本目录不含密钥、私钥或云凭证。

### 录屏（可选）

需要 Playwright 和 ffmpeg；只玩不用装。

```sh
pip install -r requirements-record.txt
python -m playwright install chromium
python fly2048/fly_2048.py --record 40 --out assets/flybrain-2048.mp4
python fly2048/fly_2048.py --until-over --out assets/flybrain-2048-full.mp4
```

## 致谢

逐文件来源见 [`SOURCE_MANIFEST.json`](SOURCE_MANIFEST.json)。

**fly.ai / flybrain** — [alextitonis/fly.ai](https://github.com/alextitonis/fly.ai)，MIT，Copyright (c) 2026 alextitonis。PyPI：[flybrain](https://pypi.org/project/flybrain/)。连接组数据：MaleCNS v1.0，**CC BY 4.0**，[署名条款](https://male-cns.janelia.org/download/)。

**2048** — GameWorld `01_2048` 来自 [GameWorld-Games](https://github.com/gameworld-project/GameWorld-Games)，其中打包了 [gabrielecirulli/2048](https://github.com/gabrielecirulli/2048)（MIT，Copyright (c) 2014 Gabriele Cirulli）。许可副本：`games/01_2048/LICENSE.txt`。

本适配器为 Alpha。第三方许可留在各自目录，不并入根目录 [`LICENSE`](LICENSE)。
