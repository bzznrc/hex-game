from hex_game.boards import compute_best_fit_hex_layout


def test_import_package():
    import hex_game

    assert hex_game.__version__


def test_hex_layout_even_area():
    layout = compute_best_fit_hex_layout(
        screen_width_px=800,
        screen_height_px=800,
        bottom_bar_height_px=36,
        target_hex_count=80,
    )
    assert layout.columns * layout.rows % 2 == 0
    assert layout.radius_px >= 6
