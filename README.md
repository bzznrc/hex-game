# Hex Game

Hex Game is a turn-based strategy roguelike campaign prototype played on a hexagonal map.
You control the Player side, while the CPU controls the opposing side with simple automated logic.

Each match includes varied terrain (such as rivers and mountains), creating positional choices and tradeoffs.
The objective is to outmaneuver the CPU and dominate more of the map over the course of each level.

## Shared Design System
- Visual and board constants are sourced from the sibling Bazza Game Design System package (`bgds` imports).
- For standalone environments, install it with `pip install -e ../bazza-game-design-system`.

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
python play_hex.py
```

Icons are from https://fonts.google.com/icons
