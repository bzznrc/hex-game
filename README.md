# Hex Game

## Overview
Minimal, local-only turn-based hex strategy game.

## Quickstart
```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .
```

## Run
```bash
python -m hex_game
python -m hex_game.play_hex
```

## Project Layout
- `src/hex_game/config.py`: central configuration and constants
- `src/hex_game/layout.py`: hex layout utilities
- `src/hex_game/generation.py`: terrain and river generation helpers
- `src/hex_game/grid.py`: board state and rule primitives
- `src/hex_game/game.py`: turn flow, combat resolution, CPU behavior
- `src/hex_game/render.py`: arcade rendering
- `src/hex_game/play_hex.py`: game entrypoint
- `src/hex_game/runtime.py`: arcade runtime helpers
- `src/hex_game/assets.py`: local asset path resolution
