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
Tyre inner temperatures and tread remaining widget.
"""

from PySide2.QtCore import QRectF, Qt
from PySide2.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide2.QtWidgets import QWidget

from .. import calculation as calc
from .. import units
from ..api_control import api
from ..const_common import TEXT_PLACEHOLDER
from ..module_info import minfo
from ..regex_pattern import FONT_WEIGHT_MAP
from ..userfile.heatmap import (
    HEATMAP_DEFAULT_TYRE,
    load_heatmap_color,
    select_compound_color,
    select_compound_symbol,
    select_tyre_heatmap_name,
)
from ._base import Overlay


class TyreConditionPanel(QWidget):
    """Four-tire dashboard in the shared rounded-card style."""

    def __init__(self, parent, font_name, font_size, font_weight, show_ico):
        super().__init__(parent)
        self._scale = max(font_size, 10)
        self._family = font_name
        self._weight = font_weight
        self._show_ico = show_ico
        self._temps = [[("—", QColor("#293642"), QColor("#91A5B5"))] * (3 if show_ico else 1) for _ in range(4)]
        self._tread = [0.0] * 4
        self._lap_wear = [0.0] * 4
        self._compound = [("", QColor("#91A5B5"))] * 4
        self._warning_threshold = 30
        self._warning_color = QColor("#FF785F")
        self.setFixedSize(round(self._scale * 22), round(self._scale * 14.5))

    def set_data(self, temps, tread, lap_wear, compounds, warning_threshold, warning_color):
        data = (temps, tread, lap_wear, compounds, warning_threshold, warning_color)
        old = (self._temps, self._tread, self._lap_wear, self._compound,
               self._warning_threshold, self._warning_color)
        if data == old:
            return
        self._temps, self._tread, self._lap_wear, self._compound = temps, tread, lap_wear, compounds
        self._warning_threshold, self._warning_color = warning_threshold, warning_color
        self.update()

    def _font(self, size, bold=False):
        font = QFont(self._family)
        font.setPixelSize(max(round(size), 1))
        font.setWeight(QFont.Bold if bold else FONT_WEIGHT_MAP[self._weight])
        return font

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        scale = self._scale
        margin = scale * 0.25
        panel = QRectF(margin, margin, self.width() - margin * 2, self.height() - margin * 2)
        path = QPainterPath()
        path.addRoundedRect(panel, scale * 0.62, scale * 0.62)
        painter.fillPath(path, QColor("#E8121B26"))
        painter.setPen(QPen(QColor("#557F9BAA"), max(scale * 0.045, 0.6)))
        painter.drawPath(path)

        pad = scale * 0.85
        left, right = panel.left() + pad, panel.right() - pad
        top = panel.top() + scale * 0.15

        gap = scale * 0.48
        card_width = (right - left - gap) / 2
        card_height = scale * 6.0
        grid_top = top + scale * 0.3
        labels = ("FL", "FR", "RL", "RR")
        for index in range(4):
            col, row = index % 2, index // 2
            mirrored = col == 1
            x = left + col * (card_width + gap)
            y = grid_top + row * (card_height + gap)
            card = QRectF(x, y, card_width, card_height)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#AA202B36"))
            painter.drawRoundedRect(card, scale * 0.45, scale * 0.45)

            # Wheel label and compound chip.
            painter.setPen(QColor("#E8F1F6"))
            painter.setFont(self._font(scale * 0.7, True))
            if mirrored:
                label_rect = QRectF(card.right() - pad * 0.48 - scale * 2.1,
                                    y + scale * 0.25, scale * 2.1, scale * 0.95)
                label_align = Qt.AlignRight | Qt.AlignVCenter
            else:
                label_rect = QRectF(x + pad * 0.48, y + scale * 0.25, scale * 2.1, scale * 0.95)
                label_align = Qt.AlignLeft | Qt.AlignVCenter
            painter.drawText(label_rect, label_align, labels[index])
            compound, compound_color = self._compound[index]
            if compound:
                chip_x = card.right() - scale * 3.9 if mirrored else x + scale * 2.45
                chip = QRectF(chip_x, y + scale * 0.31, scale * 1.45, scale * 0.76)
                painter.setBrush(QColor(compound_color.red(), compound_color.green(), compound_color.blue(), 38))
                painter.drawRoundedRect(chip, scale * 0.25, scale * 0.25)
                painter.setPen(compound_color)
                painter.setFont(self._font(scale * 0.54, True))
                painter.drawText(chip, Qt.AlignCenter, compound)

            tread = max(0.0, min(self._tread[index], 100.0))
            tread_color = self._warning_color if tread <= self._warning_threshold else QColor("#63D6AE")
            # Split tread information from temperatures with a vertical divider.
            main_divider_x = card.right() - scale * 4.55 if mirrored else x + scale * 4.55
            inner_left = main_divider_x + scale * 0.25 if mirrored else x + pad * 0.48
            inner_right = card.right() - pad * 0.48 if mirrored else main_divider_x - scale * 0.25
            body_top = y + scale * 1.35
            body_bottom = y + card_height - scale * 0.3
            painter.setPen(QPen(QColor("#557F9BAA"), max(scale * 0.045, 0.6)))
            painter.drawLine(int(main_divider_x), int(body_top), int(main_divider_x), int(body_bottom))

            # Remaining tread above the horizontal split; this-lap wear below it.
            left_width = max(inner_right - inner_left, 0)
            content_align = Qt.AlignRight | Qt.AlignVCenter if mirrored else Qt.AlignLeft | Qt.AlignVCenter
            painter.setPen(QColor("#91A5B5"))
            painter.setFont(self._font(scale * 0.68, True))
            painter.drawText(QRectF(inner_left, body_top, left_width, scale * 0.72),
                             content_align, "TREAD LEFT")
            painter.setPen(tread_color)
            painter.setFont(self._font(scale * 1.1, True))
            painter.drawText(QRectF(inner_left, body_top + scale * 0.68, left_width, scale * 1.15),
                             content_align, f"{tread:.1f}%")
            split_y = body_top + scale * 2.05
            painter.setPen(QPen(QColor("#557F9BAA"), max(scale * 0.045, 0.6)))
            painter.drawLine(int(inner_left), int(split_y), int(inner_right), int(split_y))
            painter.setPen(QColor("#91A5B5"))
            painter.setFont(self._font(scale * 0.68, True))
            painter.drawText(QRectF(inner_left, split_y + scale * 0.08, left_width, scale * 0.7),
                             content_align, "THIS LAP")
            painter.setPen(self._warning_color if self._lap_wear[index] > 0 else QColor("#63D6AE"))
            painter.setFont(self._font(scale * 0.95, True))
            painter.drawText(QRectF(inner_left, split_y + scale * 0.72, left_width, scale * 1.0),
                             content_align, f"-{max(self._lap_wear[index], 0.0):.1f}%")

            # Temperatures as a compact vertical list with short heatmap markers.
            values = self._temps[index]
            temp_labels = ("I", "C", "O") if self._show_ico else ("",)
            temp_area_x = (main_divider_x - scale * 0.6) if mirrored else (main_divider_x + scale * 0.48)
            row_height = (body_bottom - body_top) / len(values)
            for temp_index, (value, bg, fg) in enumerate(values):
                row_y = body_top + temp_index * row_height
                marker = QRectF(temp_area_x, row_y + row_height * 0.25, scale * 0.12, row_height * 0.5)
                painter.setPen(Qt.NoPen)
                painter.setBrush(bg)
                painter.drawRoundedRect(marker, marker.width() / 2, marker.width() / 2)
                if temp_labels[temp_index]:
                    painter.setPen(QColor("#91A5B5"))
                    painter.setFont(self._font(scale * 0.5, True))
                    label_x = temp_area_x - scale * 1.43 if mirrored else temp_area_x + scale * 0.28
                    label_align = Qt.AlignRight | Qt.AlignVCenter if mirrored else Qt.AlignLeft | Qt.AlignVCenter
                    painter.drawText(QRectF(label_x, row_y, scale * 1.15, row_height),
                                     label_align, temp_labels[temp_index])
                painter.setPen(fg)
                painter.setFont(self._font(scale * (1.08 if self._show_ico else 1.4), True))
                text_offset = scale * (1.35 if self._show_ico else 0.28)
                if mirrored:
                    text_right = temp_area_x - text_offset
                    text_left = card.left() + scale * 0.35
                    text_rect = QRectF(text_left, row_y, max(text_right - text_left, 0), row_height)
                    text_align = Qt.AlignRight | Qt.AlignVCenter
                else:
                    text_left = temp_area_x + text_offset
                    text_rect = QRectF(text_left, row_y, card.right() - text_left - scale * 0.35, row_height)
                    text_align = Qt.AlignLeft | Qt.AlignVCenter
                painter.drawText(text_rect, text_align, value)


class Realtime(Overlay):
    """Draw combined inner-temperature and tread-remaining widget."""

    def __init__(self, config, widget_name):
        super().__init__(config, widget_name)
        wear_cfg = self.cfg.user.setting["tyre_wear"]
        self.wear_warning_threshold = wear_cfg["warning_threshold_remaining"]
        self.wear_warning_color = QColor(wear_cfg["font_color_warning"])
        self.show_ico = self.wcfg["show_inner_center_outer"]
        self.show_degree = self.wcfg["show_degree_sign"]
        self.unit_temp = units.set_unit_temperature(self.cfg.units["temperature_unit"])
        self.heatmap_styles = [
            load_heatmap_color(
                heatmap_name=self.wcfg["heatmap_name"],
                default_name=HEATMAP_DEFAULT_TYRE,
                swap_style=self.wcfg["swap_style"],
                fg_color=self.wcfg["font_color_inner_layer"],
                bg_color=self.wcfg["background_color_inner_layer"],
            )
            for _ in range(4)
        ]
        self.panel = TyreConditionPanel(
            self,
            self.wcfg["font_name"],
            self.wcfg["font_size"],
            self.wcfg["font_weight"],
            self.show_ico,
        )
        self.set_primary_layout(self.set_grid_layout(), align=Qt.AlignLeft | Qt.AlignTop)
        self.layout().addWidget(self.panel)
        self.last_in_pits = -1
        self.last_compounds = ("", "", "", "")

    def timerEvent(self, event):
        """Update tyre temperatures, compounds and remaining tread."""
        in_pits = api.read.vehicle.in_pits()
        if in_pits or self.last_in_pits != in_pits:
            self.last_in_pits = in_pits
            compounds = api.read.tyre.compound_class()
            if compounds != self.last_compounds:
                if self.wcfg["enable_heatmap_auto_matching"]:
                    for index, compound in enumerate(compounds):
                        if self.last_compounds[index] != compound:
                            self.heatmap_styles[index] = load_heatmap_color(
                                heatmap_name=select_tyre_heatmap_name(compound),
                                default_name=HEATMAP_DEFAULT_TYRE,
                                swap_style=self.wcfg["swap_style"],
                                fg_color=self.wcfg["font_color_inner_layer"],
                                bg_color=self.wcfg["background_color_inner_layer"],
                            )
                self.last_compounds = compounds
        else:
            compounds = self.last_compounds

        if self.show_ico:
            raw_temps = api.read.tyre.inner_temperature_ico()
            temp_rows = [raw_temps[index * 3:index * 3 + 3] for index in range(4)]
        else:
            raw_temps = api.read.tyre.inner_temperature_avg()
            temp_rows = [(raw_temps[index],) for index in range(4)]

        display_temps = []
        for tyre_index, row in enumerate(temp_rows):
            row_data = []
            for temp in row:
                if temp < -100:
                    value, bg, fg = TEXT_PLACEHOLDER, QColor("#293642"), QColor("#91A5B5")
                else:
                    value = f"{self.unit_temp(temp):.1f}"
                    if self.show_degree:
                        value += "°"
                    fg, bg = calc.select_grade(self.heatmap_styles[tyre_index], temp)
                    bg, fg = QColor(bg), QColor(fg)
                row_data.append((value, bg, fg))
            display_temps.append(row_data)

        compounds_display = []
        for compound in compounds:
            symbol = select_compound_symbol(compound) if self.wcfg["show_tyre_compound"] else ""
            color = QColor(select_compound_color(compound)) if self.wcfg["show_compound_color_by_type"] else QColor("#91A5B5")
            compounds_display.append((symbol, color))

        self.panel.set_data(
            display_temps,
            tuple(minfo.wheels.currentTreadDepth),
            tuple(minfo.wheels.currentLapTreadWear),
            compounds_display,
            self.wear_warning_threshold,
            self.wear_warning_color,
        )
