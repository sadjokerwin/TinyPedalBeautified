#  TinyPedal is an open-source overlay application for racing simulation.
#  Copyright (C) 2022-2026 TinyPedal developers, see contributors.md file
#
#  This file is part of TinyPedal.
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Fuel Widget
"""

from math import ceil

from .. import calculation as calc
from .. import units
from ..module_info import minfo
from ._consumption_metrics import consumption_metrics, format_extension_targets
from ._consumption_card import ConsumptionStrategyCard
from ._base import Overlay
from ._common import warning_flash
from ._painter import FuelLevelBar


class Realtime(Overlay):
    """Draw widget"""

    def __init__(self, config, widget_name):
        # Assign base setting
        super().__init__(config, widget_name)
        layout = self.set_grid_layout(gap=self.wcfg["bar_gap"])
        self.set_primary_layout(layout=layout)

        # Config font
        font = self.config_font(
            self.wcfg["font_name"],
            self.wcfg["font_size"],
            self.wcfg["font_weight"],
        )
        self.setFont(font)
        font_m = self.get_font_metrics(font)

        # Config variable
        text_def = "-.--"
        bar_padx = self.set_padding(self.wcfg["font_size"], self.wcfg["bar_padding"])
        self.bar_width = max(self.wcfg["bar_width"], 3)
        style_width = font_m.width * self.bar_width + bar_padx
        column_count = 0

        # Config units
        self.unit_fuel = units.set_unit_fuel(self.cfg.units["fuel_unit"])

        # Create layout
        layout_upper = self.set_grid_layout()
        layout_lower = self.set_grid_layout()
        layout.addLayout(layout_upper, self.wcfg["display_order_upper"], 0)
        layout.addLayout(layout_lower, self.wcfg["display_order_lower"], 0)

        # Recent-use strategy footer, shared by fuel and virtual energy.
        self.bar_strategy = self.set_rawtext(
            text="SAVE +1 --   +2 --   +3 --",
            fixed_height=font_m.height,
            offset_y=font_m.voffset,
            fg_color=self.wcfg.get("font_color_estimated_consumption", self.wcfg.get("font_color_remaining", "#FFFFFF")),
            bg_color=self.wcfg.get("background_color_estimated_consumption", "#222222"),
        )
        strategy_row = max(
            self.wcfg["display_order_upper"], self.wcfg["display_order_lower"],
            self.wcfg["display_order_middle"],
        ) + 1
        layout.addWidget(self.bar_strategy, strategy_row, 0, 1, 6)
        self._strategy_last = None

        # Caption style
        if self.wcfg["show_caption"]:
            font_cap = self.config_font(
                self.wcfg["font_name"],
                self.wcfg["font_size"] * self.wcfg["font_scale_caption"],
                self.wcfg["font_weight"],
            )
            font_cap_m = self.get_font_metrics(font_cap)

            row_idx_upper = 2 * self.wcfg["swap_upper_caption"]
            row_idx_lower = 2 - 2 * self.wcfg["swap_lower_caption"]

        # Remaining
        self.bar_style_curr = (
            self.wcfg["background_color_remaining"],
            self.wcfg["warning_color_low_fuel"],
        )
        self.bar_curr = self.set_rawtext(
            text=text_def,
            fixed_width=style_width,
            fixed_height=font_m.height,
            offset_y=font_m.voffset,
            fg_color=self.wcfg["font_color_remaining"],
            bg_color=self.bar_style_curr[0],
        )
        self.bar_curr.decimals = max(self.wcfg["decimal_places_remaining"], 0)
        layout_upper.addWidget(self.bar_curr, 1, 1)
        column_count += 1

        if self.wcfg["show_caption"]:
            cap_temp = self.set_rawtext(
                font=font_cap,
                text=self.wcfg["caption_text_remaining"],
                fixed_height=font_cap_m.height,
                offset_y=font_cap_m.voffset,
                fg_color=self.wcfg["font_color_caption"],
                bg_color=self.wcfg["background_color_caption"],
            )
            layout_upper.addWidget(cap_temp, row_idx_upper, 1)

        # Total needed
        self.bar_style_need = (
            self.wcfg["background_color_refueling"],
            self.wcfg["warning_color_low_fuel"],
        )
        self.bar_need = self.set_rawtext(
            text=text_def,
            fixed_width=style_width,
            fixed_height=font_m.height,
            offset_y=font_m.voffset,
            fg_color=self.wcfg["font_color_refueling"],
            bg_color=self.bar_style_need[0],
        )
        self.bar_need.decimals = max(self.wcfg["decimal_places_refueling"], 0)
        layout_upper.addWidget(self.bar_need, 1, 2)
        column_count += 1

        if self.wcfg["show_caption"]:
            cap_temp = self.set_rawtext(
                font=font_cap,
                text=(
                    self.wcfg["caption_text_absolute_refueling"]
                    if self.wcfg["show_absolute_refueling"]
                    else self.wcfg["caption_text_refueling"]
                ),
                fixed_height=font_cap_m.height,
                offset_y=font_cap_m.voffset,
                fg_color=self.wcfg["font_color_caption"],
                bg_color=self.wcfg["background_color_caption"],
            )
            layout_upper.addWidget(cap_temp, row_idx_upper, 2)

        # Estimated laps can last
        self.bar_laps = self.set_rawtext(
            text=text_def,
            fixed_width=style_width,
            fixed_height=font_m.height,
            offset_y=font_m.voffset,
            fg_color=self.wcfg["font_color_estimated_laps"],
            bg_color=self.wcfg["background_color_estimated_laps"],
        )
        self.bar_laps.decimals = max(self.wcfg["decimal_places_estimated_laps"], 0)
        layout_lower.addWidget(self.bar_laps, 1, 1)

        if self.wcfg["show_caption"]:
            cap_temp = self.set_rawtext(
                font=font_cap,
                text=self.wcfg["caption_text_estimated_laps"],
                fixed_height=font_cap_m.height,
                offset_y=font_cap_m.voffset,
                fg_color=self.wcfg["font_color_caption"],
                bg_color=self.wcfg["background_color_caption"],
            )
            layout_lower.addWidget(cap_temp, row_idx_lower, 1)

        # Estimated minutes can last
        self.bar_mins = self.set_rawtext(
            text=text_def,
            fixed_width=style_width,
            fixed_height=font_m.height,
            offset_y=font_m.voffset,
            fg_color=self.wcfg["font_color_estimated_minutes"],
            bg_color=self.wcfg["background_color_estimated_minutes"],
        )
        self.bar_mins.decimals = max(self.wcfg["decimal_places_estimated_minutes"], 0)
        layout_lower.addWidget(self.bar_mins, 1, 2)

        if self.wcfg["show_caption"]:
            cap_temp = self.set_rawtext(
                font=font_cap,
                text=self.wcfg["caption_text_estimated_minutes"],
                fixed_height=font_cap_m.height,
                offset_y=font_cap_m.voffset,
                fg_color=self.wcfg["font_color_caption"],
                bg_color=self.wcfg["background_color_caption"],
            )
            layout_lower.addWidget(cap_temp, row_idx_lower, 2)

        # Estimated consumption
        self.bar_used = self.set_rawtext(
            text=text_def,
            fixed_width=style_width,
            fixed_height=font_m.height,
            offset_y=font_m.voffset,
            fg_color=self.wcfg["font_color_estimated_consumption"],
            bg_color=self.wcfg["background_color_estimated_consumption"],
        )
        self.bar_used.decimals = max(self.wcfg["decimal_places_estimated_consumption"], 0)
        layout_upper.addWidget(self.bar_used, 1, 3)
        column_count += 1

        if self.wcfg["show_caption"]:
            cap_temp = self.set_rawtext(
                font=font_cap,
                text=self.wcfg["caption_text_estimated_consumption"],
                fixed_height=font_cap_m.height,
                offset_y=font_cap_m.voffset,
                fg_color=self.wcfg["font_color_caption"],
                bg_color=self.wcfg["background_color_caption"],
            )
            layout_upper.addWidget(cap_temp, row_idx_upper, 3)

        # Estimated one less pit consumption
        self.bar_save = self.set_rawtext(
            text=text_def,
            fixed_width=style_width,
            fixed_height=font_m.height,
            offset_y=font_m.voffset,
            fg_color=self.wcfg["font_color_saving_target"],
            bg_color=self.wcfg["background_color_saving_target"],
        )
        self.bar_save.decimals = max(self.wcfg["decimal_places_saving_target"], 0)
        layout_lower.addWidget(self.bar_save, 1, 3)

        if self.wcfg["show_caption"]:
            cap_temp = self.set_rawtext(
                font=font_cap,
                text=self.wcfg["caption_text_saving_target"],
                fixed_height=font_cap_m.height,
                offset_y=font_cap_m.voffset,
                fg_color=self.wcfg["font_color_caption"],
                bg_color=self.wcfg["background_color_caption"],
            )
            layout_lower.addWidget(cap_temp, row_idx_lower, 3)

        if self.wcfg["show_estimated_pitstop_count"]:
            # Estimate pit stop counts when pitting at end of current stint
            self.bar_pits = self.set_rawtext(
                text=text_def,
                fixed_width=style_width,
                fixed_height=font_m.height,
                offset_y=font_m.voffset,
                fg_color=self.wcfg["font_color_pitstop_count"],
                bg_color=self.wcfg["background_color_pitstop_count"],
            )
            self.bar_pits.decimals = max(self.wcfg["decimal_places_pitstop_count"], 0)
            layout_upper.addWidget(self.bar_pits, 1, 0)
            column_count += 1

            if self.wcfg["show_caption"]:
                cap_temp = self.set_rawtext(
                    font=font_cap,
                    text=self.wcfg["caption_text_pitstop_count"],
                    fixed_height=font_cap_m.height,
                    offset_y=font_cap_m.voffset,
                    fg_color=self.wcfg["font_color_caption"],
                    bg_color=self.wcfg["background_color_caption"],
                )
                layout_upper.addWidget(cap_temp, row_idx_upper, 0)

            # Estimate pit stop counts when pitting at end of current lap
            self.bar_early = self.set_rawtext(
                text=text_def,
                fixed_width=style_width,
                fixed_height=font_m.height,
                offset_y=font_m.voffset,
                fg_color=self.wcfg["font_color_early_pitstop_count"],
                bg_color=self.wcfg["background_color_early_pitstop_count"],
            )
            self.bar_early.decimals = max(self.wcfg["decimal_places_early_pitstop_count"], 0)
            layout_lower.addWidget(self.bar_early, 1, 0)

            if self.wcfg["show_caption"]:
                cap_temp = self.set_rawtext(
                    font=font_cap,
                    text=self.wcfg["caption_text_early_pitstop_count"],
                    fixed_height=font_cap_m.height,
                    offset_y=font_cap_m.voffset,
                    fg_color=self.wcfg["font_color_caption"],
                    bg_color=self.wcfg["background_color_caption"],
                )
                layout_lower.addWidget(cap_temp, row_idx_lower, 0)

        if self.wcfg["show_delta_consumption_and_end_remaining"]:
            # Delta consumption
            self.bar_delta = self.set_rawtext(
                text=text_def,
                fixed_width=style_width,
                fixed_height=font_m.height,
                offset_y=font_m.voffset,
                fg_color=self.wcfg["font_color_delta_consumption"],
                bg_color=self.wcfg["background_color_delta_consumption"],
            )
            self.bar_delta.decimals = max(self.wcfg["decimal_places_delta_consumption"], 0)
            layout_upper.addWidget(self.bar_delta, 1, 4)
            column_count += 1

            if self.wcfg["show_caption"]:
                cap_temp = self.set_rawtext(
                    font=font_cap,
                    text=self.wcfg["caption_text_delta_consumption"],
                    fixed_height=font_cap_m.height,
                    offset_y=font_cap_m.voffset,
                    fg_color=self.wcfg["font_color_caption"],
                    bg_color=self.wcfg["background_color_caption"],
                )
                layout_upper.addWidget(cap_temp, row_idx_upper, 4)

            # Estimated end remaining
            self.bar_end = self.set_rawtext(
                text=text_def,
                fixed_width=style_width,
                fixed_height=font_m.height,
                offset_y=font_m.voffset,
                fg_color=self.wcfg["font_color_end_remaining"],
                bg_color=self.wcfg["background_color_end_remaining"],
            )
            self.bar_end.decimals = max(self.wcfg["decimal_places_end_remaining"], 0)
            layout_lower.addWidget(self.bar_end, 1, 4)

            if self.wcfg["show_caption"]:
                cap_temp = self.set_rawtext(
                    font=font_cap,
                    text=self.wcfg["caption_text_end_remaining"],
                    fixed_height=font_cap_m.height,
                    offset_y=font_cap_m.voffset,
                    fg_color=self.wcfg["font_color_caption"],
                    bg_color=self.wcfg["background_color_caption"],
                )
                layout_lower.addWidget(cap_temp, row_idx_lower, 4)

        # Fuel level bar
        if self.wcfg["show_fuel_level_bar"]:
            self.bar_level = FuelLevelBar(
                self,
                width=(font_m.width * self.bar_width + bar_padx) * column_count,
                height=max(self.wcfg["fuel_level_bar_height"], 1),
                start_mark_width=max(self.wcfg["starting_fuel_level_mark_width"], 1),
                refill_mark_width=max(self.wcfg["refueling_level_mark_width"], 1),
                input_color=self.wcfg["highlight_color_fuel_level"],
                bg_color=self.wcfg["background_color_fuel_level"],
                start_mark_color=self.wcfg["starting_fuel_level_mark_color"],
                refill_mark_color=self.wcfg["refueling_level_mark_color"],
                show_start_mark=self.wcfg["show_starting_fuel_level_mark"],
                show_refill_mark=self.wcfg["show_refueling_level_mark"],
            )
            layout.addWidget(self.bar_level, self.wcfg["display_order_middle"], 0)

        # Replace the old plain rows with one unified, rounded strategy card.
        for child_layout in (layout_upper, layout_lower):
            self._hide_calculator_rows(child_layout)
        self.bar_strategy.hide()
        if self.wcfg.get("show_fuel_level_bar", False):
            self.bar_level.hide()
        self.strategy_card = ConsumptionStrategyCard(
            self, "fuel", self.wcfg["font_name"], self.wcfg["font_size"]
        )
        layout.addWidget(self.strategy_card, 0, 0, 1, 6)

        if self.wcfg["show_low_fuel_warning_flash"]:
            self.warn_flash = warning_flash(
                self.wcfg["warning_flash_highlight_duration"],
                self.wcfg["warning_flash_interval"],
                self.wcfg["number_of_warning_flashes"],
            )

    @staticmethod
    def _hide_calculator_rows(layout):
        """Hide legacy children after their data has been repurposed into the card."""
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.hide()
            elif item.layout() is not None:
                Realtime._hide_calculator_rows(item.layout())

    def timerEvent(self, event):
        """Update when vehicle on track"""
        is_low_fuel = minfo.fuel.estimatedLaps <= self.wcfg["low_fuel_lap_threshold"]
        if self.wcfg["show_low_fuel_warning_flash"] and minfo.fuel.estimatedValidConsumption:
            is_low_fuel = self.warn_flash.send(is_low_fuel)
            if is_low_fuel:
                padding = 0.00000001  # add padding for switching state
            else:
                padding = 0
        else:
            padding = 0

        # Remaining
        amount_curr = self.unit_fuel(minfo.fuel.amountCurrent)
        self.update_fuel(self.bar_curr, amount_curr + padding, self.bar_style_curr[is_low_fuel])

        # Total needed
        if self.wcfg["show_absolute_refueling"]:
            amount_need = calc.sym_max(self.unit_fuel(minfo.fuel.neededAbsolute), 9999)
            self.update_fuel(self.bar_need, amount_need + padding, self.bar_style_need[is_low_fuel])
        else:
            amount_need = calc.sym_max(self.unit_fuel(minfo.fuel.neededRelative), 9999)
            self.update_fuel(self.bar_need, amount_need + padding, self.bar_style_need[is_low_fuel], "+")

        metrics = consumption_metrics("fuel")
        # Show stint range and average from the last five valid completed laps.
        self.update_fuel(self.bar_laps, metrics["remaining_laps"])
        self.update_fuel(self.bar_mins, metrics["remaining_minutes"])
        self.update_fuel(self.bar_used, self.unit_fuel(metrics["average"]))
        self.update_fuel(self.bar_save, self.unit_fuel(metrics["average"] * (1 - 1 / max(metrics["remaining_laps"] + 1, 1))))
        if self.wcfg["show_delta_consumption_and_end_remaining"]:
            self.update_fuel(self.bar_delta, self.unit_fuel(metrics["current_lap_delta"] or 0), None, "+")
            self.update_fuel(self.bar_end, self.unit_fuel(metrics["stint_average"]))
        strategy = format_extension_targets(metrics["extension_targets"])
        if self._strategy_last != strategy:
            self._strategy_last = strategy
            self.bar_strategy.text = strategy
            self.bar_strategy.update()
        targets = []
        for extra, saving in metrics["extension_targets"]:
            if saving is not None and saving <= 0.15 and metrics["average"] > 0:
                target_average = self.unit_fuel(metrics["average"] * (1 - saving))
                target_unit = self.cfg.units["fuel_unit"]
                targets.append((f"+{extra} LAP", f"{target_average:.2f} {target_unit}/lap"))


        extension_saving = metrics["extension_targets"][0][1]
        fuel_to_finish = max(self.unit_fuel(minfo.fuel.neededRelative), 0)
        stops_to_finish = max(ceil(minfo.fuel.estimatedNumPitStopsEnd), 0)
        finish_fuel_label = "FUEL TO GO"
        finish_fuel_text = f"{fuel_to_finish:.2f} {units.set_symbol_fuel(self.cfg.units['fuel_unit'])}"
        if stops_to_finish > 1:
            finish_fuel_label = "STOPS TO GO"
            finish_fuel_text = str(stops_to_finish)
        self.strategy_card.set_values(
            current=self.unit_fuel(minfo.fuel.amountCurrent),
            current_text=f"{self.unit_fuel(minfo.fuel.amountCurrent):.2f} {units.set_symbol_fuel(self.cfg.units['fuel_unit'])}",
            finish_fuel_label=finish_fuel_label,
            finish_fuel_text=finish_fuel_text,
            needed_text=f"{self.unit_fuel(amount_need):.2f}",
            level=minfo.fuel.amountCurrent / minfo.fuel.capacity if minfo.fuel.capacity else 0,
            average_text=f"{self.unit_fuel(metrics['average']):.2f}" if metrics["average"] > 0 else "—",
            range_text=f"{metrics['remaining_laps']:.1f} Laps" if metrics["average"] > 0 else "—",
            last_lap_text=f"{self.unit_fuel(metrics['last_lap']):.2f}" if metrics["last_lap"] > 0 else "—",
            extension_target_text=(
                "—" if metrics["average"] <= 0 else (
                    f"{self.unit_fuel(metrics['average'] * (1 - extension_saving)):.2f}"
                    if extension_saving is not None and extension_saving <= 0.15
                    else ">15% cut"
                )
            ),
            delta_text="—" if metrics["current_lap_delta"] is None or metrics["current_lap_delta"] <= metrics["average"] else f"{self.unit_fuel(metrics['current_lap_delta']):+.2f}",
            delta_color="#FF7777" if metrics["current_lap_delta"] is not None and metrics["current_lap_delta"] > 0 else "#48D6C4",
            targets=tuple(targets),
        )

        if self.wcfg["show_estimated_pitstop_count"]:
            # Estimate pit stop counts when pitting at end of current stint
            est_pits_end = calc.zero_max(minfo.fuel.estimatedNumPitStopsEnd, 99.99)
            self.update_fuel(self.bar_pits, est_pits_end)

            # Estimate pit stop counts when pitting at end of current lap
            est_pits_early = calc.zero_max(minfo.fuel.estimatedNumPitStopsEarly, 99.99)
            self.update_fuel(self.bar_early, est_pits_early)


        # Fuel level bar
        if self.wcfg["show_fuel_level_bar"]:
            level_capacity = minfo.fuel.capacity
            level_curr = minfo.fuel.amountCurrent
            level_start = minfo.fuel.amountStart
            level_refill = level_curr + minfo.fuel.neededRelative
            level_state = round(level_curr + level_start + level_refill, 3)
            if level_capacity and self.bar_level.last != level_state:
                self.bar_level.last = level_state
                self.bar_level.update_input(
                    level_curr / level_capacity,
                    level_start / level_capacity,
                    level_refill / level_capacity,
                )

    # GUI update methods
    def update_fuel(self, target, data, color=None, sign=""):
        """Update fuel data"""
        if target.last != data:
            target.last = data
            target.text = f"{data:{sign}.{target.decimals}f}"[:self.bar_width].strip(".")
            if color:  # low fuel warning
                target.bg = color
            target.update()
