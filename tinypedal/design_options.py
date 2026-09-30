"""Quick design controls for the recently redesigned widgets."""

REDESIGNED_WIDGETS = frozenset({
    "battery",
    "damage_stats",
    "deltabest",
    "gear",
    "standings",
    "tyre_inner_layer",
})

# (column key, display label, existing settings key)
STANDINGS_COLUMN_OPTIONS = (
    ("position", "Position", "show_position"),
    ("class_position", "Class position", "show_position_in_class"),
    ("change", "Position change", "show_position_change"),
    ("driver", "Driver name", "show_driver_name"),
    ("class", "Class", "show_class"),
    ("brand", "Brand logo", "show_brand_logo"),
    ("damage", "Vehicle damage", "show_vehicle_integrity"),
    ("gap", "Gap to leader", "show_time_gap"),
    ("interval", "Interval", "show_time_interval"),
    ("laptime", "Lap time", "show_laptime"),
    ("energy", "Virtual energy", "show_energy_remaining"),
    ("tyre", "Tyre compound", "show_tyre_compound"),
    ("status", "Pit status", "show_pit_status"),
)
