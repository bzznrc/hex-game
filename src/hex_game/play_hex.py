if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import arcade

from hex_game.config import (
    FONT_NAME_BAR,
    FONT_NAME_UNITS,
    FONT_PATH_REGULAR,
    FONT_PATH_UNITS,
    FONT_SIZE_BAR,
    FONT_SIZE_UNITS,
    FPS,
    WINDOW_TITLE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
import hex_game.render as ui
from hex_game.game import HexGame
from hex_game.grid import HexGrid
from hex_game.runtime import ArcadeFrameClock, ArcadeWindowController


def play_hex():
    window_controller = ArcadeWindowController(
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        WINDOW_TITLE,
        enabled=True,
        queue_input_events=True,
        vsync=False,
    )
    window = window_controller.window
    if window is None:
        return

    frame_clock = ArcadeFrameClock()
    grid = HexGrid(*HexGrid.compute_grid_size())
    font_units = ui.load_font_spec(
        FONT_PATH_UNITS,
        FONT_SIZE_UNITS,
        fallback_family=FONT_NAME_UNITS,
    )
    font_bar = ui.load_font_spec(
        FONT_PATH_REGULAR,
        FONT_SIZE_BAR,
        fallback_family=FONT_NAME_BAR,
    )
    icon_assets = ui.load_icon_assets(grid.hex_radius)
    icon_radius = grid.hex_radius
    game = HexGame(grid)

    while True:
        dt_seconds = frame_clock.tick(FPS)
        if window_controller.poll_events():
            break

        for symbol in window_controller.consume_key_presses():
            if symbol == arcade.key.ENTER:
                game.end_player_step()

        for click in window_controller.consume_mouse_presses():
            top_left_y = window_controller.to_top_left_y(click.y)
            cell = ui.get_cell_under_pixel(game.grid, click.x, top_left_y)
            if cell is None:
                continue
            mapped_button = 3 if click.button == arcade.MOUSE_BUTTON_RIGHT else click.button
            game.handle_click(cell.q, cell.r, mapped_button)

        game.update(dt_seconds)
        if game.grid.hex_radius != icon_radius:
            icon_assets = ui.load_icon_assets(game.grid.hex_radius)
            icon_radius = game.grid.hex_radius

        ui.draw_frame(window, font_units, font_bar, icon_assets, game.grid, game)
        window_controller.flip()

    window_controller.close()


if __name__ == "__main__":
    play_hex()

