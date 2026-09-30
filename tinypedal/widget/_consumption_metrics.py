"""Shared recent-consumption strategy calculations for fuel and virtual energy."""

from statistics import fmean

from ..api_control import api
from ..module_info import minfo

RECENT_LAPS = 5
MAX_SAVING_FRACTION = 0.15


def consumption_metrics(kind):
    """Return average use, remaining laps, stint delta, and extension targets."""
    attr = "lastLapUsedFuel" if kind == "fuel" else "lastLapUsedEnergy"
    current = minfo.fuel if kind == "fuel" else minfo.energy
    valid_laps = [
        getattr(lap, attr) for lap in minfo.history.consumptionDataSet
        if lap.isValidLap and getattr(lap, attr) > 0
    ]
    recent = valid_laps[:min(len(valid_laps), RECENT_LAPS)]
    average = fmean(recent) if recent else 0.0
    remaining = current.amountCurrent / average if average > 0 else 0.0

    stint = minfo.history.stintDataCurrent
    total = stint.totalFuel if kind == "fuel" else stint.totalEnergy
    completed_laps = max(stint.totalLaps, 0)
    used_stint = max(total - current.amountUsedCurrent, 0.0)
    stint_average = used_stint / completed_laps if completed_laps else 0.0

    progress = min(max(api.read.lap.progress(), 0.0), 1.0)
    projected = current.amountUsedCurrent / progress if progress >= 0.10 else 0.0
    delta = projected - stint_average if projected > 0 and stint_average > 0 else None

    targets = []
    for extra in (1, 2, 3):
        saving = extra / (remaining + extra) if remaining > 0 else None
        targets.append((extra, saving))
    return {
        "average": average, "last_lap": valid_laps[0] if valid_laps else 0.0,
        "remaining_laps": remaining,
        "remaining_minutes": remaining * minfo.delta.lapTimePace,
        "stint_average": stint_average, "current_lap_delta": delta,
        "extension_targets": tuple(targets),
    }


def format_extension_targets(targets, decimals=1):
    """Compactly show feasible consumption reductions for +1/+2/+3 laps."""
    parts = []
    for extra, saving in targets:
        if saving is None:
            value = "--"
        elif saving > MAX_SAVING_FRACTION:
            value = ">15%"
        else:
            value = f"{saving * 100:.{decimals}f}%"
        parts.append(f"+{extra} {value}")
    return "SAVE " + "   ".join(parts)
