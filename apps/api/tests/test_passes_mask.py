from __future__ import annotations

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from passes.horizon import StaticMask, is_visible_with_mask


def test_mask_blocks_low_elevation():
    angles = list(range(360))
    elevations = [10.0] * 360
    mask = StaticMask(angles_deg=__import__("numpy").array(angles), elevations_deg=__import__("numpy").array(elevations))
    assert not is_visible_with_mask(5.0, 123.0, mask)
    assert is_visible_with_mask(15.0, 123.0, mask)


