"""Module entrypoint for `python -m hex_game`."""

if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hex_game.play import play_hex


if __name__ == "__main__":
    play_hex()
