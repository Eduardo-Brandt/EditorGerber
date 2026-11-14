"""Visual stack order, independent of fabrication order inside each Gerber."""

import re

from gerber_editor.core.layer import canonical_function


def layer_order_key(layer):
    """Lower keys are displayed nearer the top of the layer manager."""
    role = canonical_function(layer.function)
    inner = re.fullmatch(r"In(\d+)\.Cu", role)
    if inner:
        return 4, int(inner[1])
    groups = {
        "F.Silk": 0,
        "F.Paste": 1,
        "F.Mask": 2,
        "F.Cu": 3,
        "B.Cu": 5,
        "B.Mask": 6,
        "B.Paste": 7,
        "B.Silk": 8,
        "Drill": 9,
        "Drill.PTH": 9,
        "Drill.NPTH": 9,
        "Drill.Blind": 9,
        "Drill.Buried": 9,
        "Drill drawing": 9,
        "Edge.Cuts": 10,
        "Route.Cuts": 11,
    }
    return groups.get(role, 12), 0


def ordered_back_to_front(layers):
    """The model stores the back first; the manager displays the reverse."""
    return list(reversed(sorted(layers, key=layer_order_key)))
