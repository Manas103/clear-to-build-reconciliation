"""Domain constants for the PLM/ERP/MES clear-to-build reconciliation."""

DISCREPANCY_CLASSES = [
    "part_number_mismatch",
    "uom_mismatch",
    "revision_skew",
    "bom_orphan_reference",
    "on_hand_shortage",
    "invalid_bom_quantity",
]

LEVEL_COUNTS = {
    "raw": 6000,
    "component": 3600,
    "subassembly": 1800,
    "finished": 600,
}

# Unit-of-measure conversion factors: (from_uom, to_uom) -> multiply-by factor.
# e.g. 1 CS (case) = 12 EA, so UOM_CONVERSIONS[("CS", "EA")] = 12.
UOM_CONVERSIONS = {
    ("EA", "EA"): 1.0,
    ("CS", "EA"): 12.0,
    ("EA", "CS"): 1.0 / 12.0,
    ("BOX", "EA"): 24.0,
    ("EA", "BOX"): 1.0 / 24.0,
    ("KG", "G"): 1000.0,
    ("G", "KG"): 1.0 / 1000.0,
    ("L", "ML"): 1000.0,
    ("ML", "L"): 1.0 / 1000.0,
}

RNG_SEED = 20261120

PER_CLASS_DEFECTS = 40
