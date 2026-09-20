# fly.ai source snapshot

These files are the **flybrain** Python package from
[alextitonis/fly.ai](https://github.com/alextitonis/fly.ai)
(MIT, Copyright (c) 2026 alextitonis). Snapshot of commit
[`125e21a`](https://github.com/alextitonis/fly.ai/tree/125e21a646e01b085ec1fa7bf693f128f934ee41).

This is not a fork. Demos, token notes, and other fly.ai extras are not copied
here. The MaleCNS connectome (~260 MB) is still downloaded at first run.

| File | What it is |
| --- | --- |
| `flybrain/brain.py` | 166,700-neuron LIF network |
| `flybrain/eyes.py` | visual feature detectors (LC10a, LPLC2, LC4, LPLC1) |
| `flybrain/build.py` | build the weight matrix from MaleCNS |
| `flybrain/data.py` | download / cache connectome files |
| `flybrain/reservoir.py` | optional linear readout |
