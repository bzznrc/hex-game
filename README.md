# Hex Game

Lightweight turn-based hex strategy game with local-only modules and assets.

## Quickstart
```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
```

Run:
```bash
python -m hex_game
```

## Structure
- `src/hex_game/config.py`: central config
- `src/hex_game/core/`: grid + turn/combat logic
- `src/hex_game/ui/`: rendering
- `src/hex_game/boards/`: hex layout and generation helpers
- `src/hex_game/runtime/`: local runtime helpers
- `src/hex_game/assets/`: local icons/fonts used by UI

## Tests
```bash
pytest
```
