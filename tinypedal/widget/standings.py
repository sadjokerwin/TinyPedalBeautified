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

"""Standings overlay with a compact, purpose-built timing board."""

from PySide2.QtCore import QRectF, Qt
from PySide2.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide2.QtWidgets import QWidget

import os
from pathlib import Path
from time import strftime

from .. import calculation as calc, units
from ..api_control import api
from ..const_common import MAX_SECONDS, TEXT_NOLAPTIME, TEXT_TREND_SIGN
from ..formatter import shorten_driver_name
from ..module_info import minfo
from ..userfile.custom_image import load_brand_logo_image
from ..userfile.heatmap import select_compound_color, select_compound_symbol
from ..regex_pattern import FONT_WEIGHT_MAP
from ._base import Overlay
from .weather import TrendTimer, laps_to_rubber, rubber_to_laps


# Dark glass surfaces and restrained telemetry accents shared with the
# battery, delta, tyre and gear instruments.
PANEL = QColor("#F0121B26")
PANEL_EDGE = QColor("#557F9BAA")
CARD = QColor("#FF202B36")
CARD_EDGE = QColor("#283F4D5A")
CARD_PLAYER = QColor("#FF19343A")
TEXT = QColor("#F1F5F8")
MUTED = QColor("#91A5B5")
FAINT = QColor("#5F7382")
TEAL = QColor("#58D6C7")
GREEN = QColor("#63D6AE")
RED = QColor("#FF785F")
AMBER = QColor("#F6C445")
BLUE = QColor("#8BC8FF")
YELLOW_ACCENT = QColor("#FFD21F")

CLASS_COLORS = {
    "HY": ("#3A2227", "#E31E24"),
    "HYPERCAR": ("#3A2227", "#E31E24"),
    "LMH": ("#3A2227", "#E31E24"),
    "LMDH": ("#3A2227", "#E31E24"),
    "GT3": ("#3A2227", "#009B4A"),
    "LMP2": ("#192C43", "#183F88"),
    "LMP3": ("#302641", "#C5A4F2"),
    "GTE": ("#3B3423", "#FFF200"),
}


def readable_class_text(background, preferred):
    """Keep class text legible against custom class backgrounds."""
    background = QColor(background)
    preferred = QColor(preferred)

    def luminance(color):
        channels = []
        for channel in (color.red(), color.green(), color.blue()):
            value = channel / 255
            channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    bg_luminance = luminance(background)

    def contrast(color):
        color_luminance = luminance(color)
        return (max(bg_luminance, color_luminance) + 0.05) / (min(bg_luminance, color_luminance) + 0.05)

    if preferred.isValid() and contrast(preferred) >= 4.5:
        return preferred.name()
    light = QColor("#F1F5F8")
    dark = QColor("#10161C")
    return light.name() if contrast(light) >= contrast(dark) else dark.name()


class StandingsBoard(QWidget):
    """Paint the full timing board in one measured, fixed-width surface."""

    COLUMNS = (
        ("position", "POS", 4.0, Qt.AlignCenter),
        ("class_position", "C POS", 5.8, Qt.AlignCenter),
        ("change", "CHG", 4.2, Qt.AlignCenter),
        ("driver", "DRIVER", 13.0, Qt.AlignLeft),
        ("class", "CLASS", 7.5, Qt.AlignCenter),
        ("brand", "CAR", 5.0, Qt.AlignCenter),
        ("damage", "DAMAGE", 5.8, Qt.AlignCenter),
        ("gap", "GAP", 5.6, Qt.AlignRight),
        ("interval", "INT", 5.4, Qt.AlignRight),
        ("laptime", "LAST LAP", 8.0, Qt.AlignRight),
        ("energy", "VE", 5.4, Qt.AlignCenter),
        ("tyre", "TYRE", 4.8, Qt.AlignCenter),
        ("status", "PIT", 5.2, Qt.AlignCenter),
    )
    SEPARATORS = {3, 7, 9, 10, 11, 12}

    def __init__(self, parent, font, font_size, font_weight, columns, max_rows):
        super().__init__(parent)
        self._font = QFont(font)
        self._font_size = max(float(font_size), 10.0)
        self._font_weight = FONT_WEIGHT_MAP[font_weight]
        self._rows = []
        self._lap_header = "LAST LAP"
        self._session_info = ("--:--:--", "-- / --", "--:--:--")
        self._weather_info = (("-- / --", "●", MUTED), "--", ("DRY 0%", GREEN))
        self._column_data = columns
        self._max_rows = max_rows
        self._count = 0
        self._em = max(self.fontMetrics().averageCharWidth(), self._font_size * 0.46)
        self._pad = self._font_size * 0.88
        self._column_widths = []
        self._column_x = []
        x = self._pad
        for _, label, units, _ in self.COLUMNS:
            width = max(units * self._em, self.fontMetrics().horizontalAdvance(label) + self._font_size * 0.8)
            self._column_x.append(x)
            self._column_widths.append(width)
            x += width
        self._board_width = round(x + self._pad)
        self._header_height = self._font_size * 1.55
        self._row_height = max(self._font_size * 2.05, 30)
        self._row_gap = max(self._font_size * 0.22, 3)
        self._group_height = max(self._font_size * 1.48, 22)
        self._weather_height = self._font_size * 2.25
        self._top = self._font_size * 0.2
        self._info_height = self._font_size * 1.5
        self._header_y = self._top + self._info_height
        self._rows_y = self._header_y + self._header_height
        self.setFont(self._font)
        self._resize_for_rows()

    def _resize_for_rows(self):
        height = self._rows_y
        if self._rows:
            for row in self._rows:
                height += self._group_height if row.get("group") else self._row_height
                height += self._row_gap
        else:
            height += self._row_height + self._row_gap
        height += self._weather_height + self._pad * 0.12
        self.setFixedSize(self._board_width, round(height + self._pad * 0.12))

    def set_session_info(self, time_left, lap_info, local_time):
        info = (time_left, lap_info, local_time)
        if info != self._session_info:
            self._session_info = info
            self.update()

    def set_weather_info(self, temperature, trend_symbol, trend_color, rain, surface, surface_color):
        info = ((temperature, trend_symbol, trend_color), rain, (surface, surface_color))
        if info != self._weather_info:
            self._weather_info = info
            self.update()

    def set_lap_mode(self, in_race):
        label = "LAST LAP" if in_race else "BEST LAP"
        if label != self._lap_header:
            self._lap_header = label
            self.update()

    def set_rows(self, rows):
        if rows == self._rows:
            return
        self._rows = rows
        self._count = sum(not row.get("group") for row in rows)
        self._resize_for_rows()
        self.update()

    def _font_for(self, size, bold=False, mono=False):
        font = QFont(self._font)
        font.setPixelSize(max(round(size), 1))
        font.setWeight(QFont.Bold if bold else self._font_weight)
        if mono:
            font.setStyleHint(QFont.Monospace)
            font.setFixedPitch(True)
        return font

    @staticmethod
    def _round_rect(painter, rect, radius, color, border=None):
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setPen(Qt.NoPen)
        painter.fillPath(path, QBrush(color))
        if border is not None:
            painter.setPen(QPen(border, 0.8))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        bounds = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        self._round_rect(painter, bounds, self._font_size * 0.68, PANEL, PANEL_EDGE)

        # Session snapshot across the top of the timing board.
        info_rect = QRectF(self._pad, self._top,
                           self.width() - self._pad * 2, self._info_height * 0.88)
        section_width = info_rect.width() / 3
        info_colors = (AMBER, TEAL, TEXT)
        alignments = (Qt.AlignLeft, Qt.AlignHCenter, Qt.AlignRight)
        for index, (value, color, alignment) in enumerate(
                zip(self._session_info, info_colors, alignments)):
            section = QRectF(info_rect.left() + section_width * index, info_rect.top(),
                             section_width, info_rect.height())
            if index:
                painter.setPen(QPen(QColor("#33455260"), 0.8))
                divider_x = section.left()
                painter.drawLine(round(divider_x), round(section.top() + self._font_size * 0.18),
                                 round(divider_x), round(section.bottom() - self._font_size * 0.18))
            painter.setPen(color)
            painter.setFont(self._font_for(self._font_size * 1.2, True, True))
            value_rect = section.adjusted(self._font_size * 0.55, 0,
                                          -self._font_size * 0.55, 0)
            painter.drawText(value_rect, alignment | Qt.AlignVCenter, value)

        # Compact field headings aligned to their measured columns.
        header_top = self._header_y
        painter.setPen(QPen(QColor("#33455260"), 0.8))
        painter.drawLine(round(self._pad), round(header_top),
                         round(self.width() - self._pad), round(header_top))
        painter.setPen(MUTED)
        painter.setFont(self._font_for(self._font_size * 0.72, True))
        for index, (_, label, _, align) in enumerate(self.COLUMNS):
            if label == "LAST LAP":
                label = self._lap_header
            rect = QRectF(self._column_x[index], header_top + self._font_size * 0.18,
                          self._column_widths[index], self._header_height - self._font_size * 0.18)
            painter.drawText(rect, align | Qt.AlignVCenter, label)

        y = self._rows_y
        if not self._rows:
            painter.setPen(MUTED)
            painter.setFont(self._font_for(self._font_size * 0.82))
            painter.drawText(QRectF(self._pad, y, self.width() - self._pad * 2, self._row_height),
                             Qt.AlignCenter, "Waiting for standings data")
            y += self._row_height + self._row_gap
        else:
            for row in self._rows:
                if row.get("group"):
                    y = self._draw_group(painter, y, row)
                    continue
                self._draw_row(painter, y, row)
                y += self._row_height + self._row_gap
        self._draw_weather_footer(painter, y)

    def _draw_weather_footer(self, painter, y):
        footer = QRectF(self._pad, y, self.width() - self._pad * 2, self._weather_height)
        painter.setPen(QPen(QColor("#33455260"), 0.8))
        painter.drawLine(round(footer.left()), round(footer.top()),
                         round(footer.right()), round(footer.top()))
        section_width = footer.width() / 3
        labels = ("", "RAIN", "TRACK STATE")
        for index in range(3):
            section = QRectF(footer.left() + section_width * index, footer.top() + self._font_size * 0.08,
                            section_width, footer.height() - self._font_size * 0.08)
            if index:
                painter.setPen(QPen(QColor("#33455260"), 0.8))
                painter.drawLine(round(section.left()), round(section.top() + self._font_size * 0.12),
                                 round(section.left()), round(section.bottom() - self._font_size * 0.12))
            painter.setPen(MUTED)
            painter.setFont(self._font_for(self._font_size * 0.58, True))
            label_rect = QRectF(section.left() + self._font_size * 0.55, section.top(),
                                section.width() - self._font_size * 0.85,
                                self._font_size * 0.58)
            align = Qt.AlignLeft if index == 0 else Qt.AlignHCenter if index == 1 else Qt.AlignRight
            painter.drawText(label_rect, align | Qt.AlignVCenter, labels[index])

            value_rect = QRectF(section.left() + self._font_size * 0.55,
                                section.top() + self._font_size * 0.65,
                                section.width() - self._font_size * 1.1,
                                self._font_size * 1.42)
            painter.setFont(self._font_for(self._font_size * 1, True, True))
            if index == 0:
                temperature, symbol, trend_color = self._weather_info[0]
                painter.setPen(TEXT)
                painter.drawText(value_rect, Qt.AlignLeft | Qt.AlignVCenter, temperature)
                arrow_rect = QRectF(value_rect.left() + painter.fontMetrics().horizontalAdvance(temperature)
                                    + self._font_size * 0.25, value_rect.top(),
                                    self._font_size, value_rect.height())
                painter.setPen(trend_color)
                painter.drawText(arrow_rect, Qt.AlignLeft | Qt.AlignVCenter, symbol)
            elif index == 1:
                painter.setPen(BLUE)
                painter.drawText(value_rect, Qt.AlignHCenter | Qt.AlignVCenter, self._weather_info[1])
            else:
                surface, surface_color = self._weather_info[2]
                painter.setPen(surface_color)
                painter.drawText(value_rect, Qt.AlignRight | Qt.AlignVCenter, surface)

    def _draw_group(self, painter, y, row):
        center_y = y + self._group_height / 2
        x0 = self._pad
        x1 = self.width() - self._pad
        text = row["name"].upper()
        color = QColor(row["class_text"])
        painter.setPen(QPen(QColor("#33455260"), 0.8))
        painter.drawLine(round(x0), round(center_y), round(x1), round(center_y))
        badge_width = max(self._font_size * 6, self.fontMetrics().horizontalAdvance(text) + self._font_size * 1.8)
        badge = QRectF(x0 + self._font_size * 0.55, y + self._font_size * 0.12,
                       badge_width, self._group_height - self._font_size * 0.24)
        self._round_rect(painter, badge, badge.height() / 2, QColor(row["class_bg"]))
        painter.setPen(color)
        painter.setFont(self._font_for(self._font_size * 0.66, True))
        painter.drawText(badge, Qt.AlignCenter, text)
        return y + self._group_height + self._row_gap

    def _draw_row(self, painter, y, row):
        x0 = self._pad * 0.55
        card = QRectF(x0, y, self.width() - x0 * 2, self._row_height)
        fill = CARD_PLAYER if row["player"] else CARD
        border = QColor("#557F9BAA") if row["player"] else CARD_EDGE
        self._round_rect(painter, card, self._font_size * 0.48, fill, border)

        # Thin identity rail instead of class-colored row fills.
        rail_color = TEAL if row["player"] else QColor(row["class_bg"])
        rail = QRectF(card.left() + 1, card.top() + self._row_height * 0.23,
                      max(self._font_size * 0.12, 2), self._row_height * 0.54)
        self._round_rect(painter, rail, rail.width() / 2, rail_color)

        # Light separators define groups without adding visual clutter.
        painter.setPen(QPen(QColor("#33455260"), 0.7))
        for index in self.SEPARATORS:
            x = self._column_x[index] - self._font_size * 0.34
            painter.drawLine(round(x), round(card.top() + self._row_height * 0.23),
                             round(x), round(card.bottom() - self._row_height * 0.23))

        for index, (key, label, _, align) in enumerate(self.COLUMNS):
            rect = QRectF(self._column_x[index], y, self._column_widths[index], self._row_height)
            self._draw_cell(painter, rect, key, row, align)

    def _draw_cell(self, painter, rect, key, row, align):
        player_color = TEAL if row["player"] else TEXT
        small = self._font_size * 0.86
        normal = self._font_size * 1.0
        center = rect.adjusted(self._font_size * 0.18, 0, -self._font_size * 0.18, 0)

        if key == "position":
            rank = row[key]
            color = {1: AMBER, 2: QColor("#C5D0DB"), 3: QColor("#D39B79")}.get(rank, player_color)
            painter.setPen(color)
            painter.setFont(self._font_for(self._font_size * 0.98, True, True))
            painter.drawText(center, Qt.AlignCenter, f"{rank:02d}")
        elif key == "class_position":
            painter.setPen(player_color if row["player"] else MUTED)
            painter.setFont(self._font_for(normal, True, True))
            painter.drawText(center, Qt.AlignCenter, f"{row[key]:02d}")
        elif key == "change":
            change = row[key]
            if change > 0:
                text, color = f"▲ {change}", GREEN
            elif change < 0:
                text, color = f"▼ {-change}", RED
            else:
                text, color = "—", FAINT
            painter.setPen(player_color if row["player"] else color)
            painter.setFont(self._font_for(small, True))
            painter.drawText(center, Qt.AlignCenter, text)
        elif key == "driver":
            painter.setPen(player_color)
            painter.setFont(self._font_for(normal, True))
            name = self.fontMetrics().elidedText(row[key], Qt.ElideRight,
                                                 max(round(center.width()), 1))
            painter.drawText(center, Qt.AlignLeft | Qt.AlignVCenter, name)
        elif key == "class":
            chip = QRectF(center.left() + self._font_size * 0.1,
                          center.top() + self._row_height * 0.22,
                          center.width() - self._font_size * 0.2,
                          self._row_height * 0.56)
            self._round_rect(painter, chip, chip.height() * 0.34, QColor(row["class_bg"]))
            painter.setPen(QColor(row["class_text"]))
            painter.setFont(self._font_for(small, True))
            painter.drawText(chip, Qt.AlignCenter, row[key])
        elif key == "brand":
            pixmap = row.get(key)
            if pixmap is not None and not pixmap.isNull():
                target = QRectF(center.left(), center.top() + self._font_size * 0.13,
                                center.width(), center.height() - self._font_size * 0.26)
                scaled = pixmap.scaled(round(target.width()), round(target.height()),
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.drawPixmap(round(target.center().x() - scaled.width() / 2),
                                   round(target.center().y() - scaled.height() / 2), scaled)
        elif key == "damage":
            damage = row[key]
            label = f"{round(damage):d}%"
            color = RED if damage >= 25 else AMBER if damage >= 10 else GREEN
            painter.setPen(TEAL if row["player"] else color)
            painter.setFont(self._font_for(small, True, True))
            painter.drawText(center, Qt.AlignCenter, label)
        elif key in ("gap", "interval"):
            value = row[key]
            color = AMBER if value in (row["gap_leader"], row["interval_leader"]) else (BLUE if key == "interval" else MUTED)
            if row["player"]:
                color = TEAL
            painter.setPen(color)
            painter.setFont(self._font_for(normal, True, True))
            painter.drawText(center, Qt.AlignRight | Qt.AlignVCenter, value)
        elif key == "laptime":
            color = TEAL if row["player"] else (AMBER if row["best"] else TEXT)
            painter.setPen(color)
            painter.setFont(self._font_for(normal, True, True))
            painter.drawText(center, Qt.AlignRight | Qt.AlignVCenter, row[key])
        elif key == "energy":
            value = row[key]
            if value < 0:
                color, label, ratio = MUTED, "—", 0.0
            else:
                color = RED if value <= 0.10 else AMBER if value <= 0.30 else GREEN
                label = f"{value:0{self._column_data['energy_width']}.{self._column_data['energy_decimals']}%}"
                ratio = min(max(value, 0.0), 1.0)
            painter.setPen(TEAL if row["player"] else color)
            painter.setFont(self._font_for(small, True, True))
            label_rect = QRectF(center.left(), center.top() + self._font_size * 0.02,
                                center.width(), self._row_height * 0.61)
            painter.drawText(label_rect, Qt.AlignCenter, label)
            track = QRectF(center.left() + self._font_size * 0.35,
                           center.bottom() - self._font_size * 0.34,
                           center.width() - self._font_size * 0.7,
                           max(self._font_size * 0.13, 2))
            self._round_rect(painter, track, track.height() / 2, QColor("#35434F5B"))
            if ratio > 0:
                fill = QRectF(track.left(), track.top(), track.width() * ratio, track.height())
                gradient = QLinearGradient(fill.topLeft(), fill.topRight())
                gradient.setColorAt(0, color.darker(112))
                gradient.setColorAt(1, color.lighter(112))
                self._round_rect(painter, fill, track.height() / 2, gradient)
        elif key == "tyre":
            symbols = row["tyre_symbols"]
            colors = row["tyre_colors"]
            if not symbols:
                symbols, colors = ("—",), (FAINT,)
            gap = self._font_size * 0.12
            chip_width = min(self._font_size * 1.05,
                             (center.width() - gap * (len(symbols) - 1)) / len(symbols))
            total = chip_width * len(symbols) + gap * (len(symbols) - 1)
            start = center.center().x() - total / 2
            for symbol, color in zip(symbols, colors):
                chip = QRectF(start, center.center().y() - self._font_size * 0.48,
                              chip_width, self._font_size * 0.96)
                tint = QColor(color)
                tint.setAlpha(54)
                self._round_rect(painter, chip, chip.height() * 0.3, tint)
                painter.setPen(QColor(color))
                painter.setFont(self._font_for(small * 0.9, True))
                painter.drawText(chip, Qt.AlignCenter, symbol)
                start += chip_width + gap
        elif key == "status":
            label = row["status"]
            color = row["status_color"]
            if row["status_fill"]:
                chip = QRectF(center.left() + self._font_size * 0.1,
                              center.top() + self._row_height * 0.19,
                              center.width() - self._font_size * 0.2,
                              self._row_height * 0.62)
                self._round_rect(painter, chip, chip.height() / 2, color)
            elif not label:
                painter.setPen(FAINT)
                painter.setFont(self._font_for(small, True))
                painter.drawText(center, Qt.AlignCenter, "—")
            else:
                chip = QRectF(center.left() + self._font_size * 0.1,
                              center.top() + self._row_height * 0.19,
                              center.width() - self._font_size * 0.2,
                              self._row_height * 0.62)
                tint = QColor(color)
                tint.setAlpha(82 if row["status_emphasis"] else 54)
                self._round_rect(painter, chip, chip.height() / 2, tint)
                painter.setPen(color)
                painter.setFont(self._font_for(small, True))
                painter.drawText(chip, Qt.AlignCenter, label)


class Realtime(Overlay):
    """Gather timing data and feed the custom standings board."""

    def __init__(self, config, widget_name):
        super().__init__(config, widget_name)

        self._font = self.config_font(
            self.wcfg["font_name"], self.wcfg["font_size"], self.wcfg["font_weight"]
        )
        metrics = self.get_font_metrics(self._font)
        font_size = self.wcfg["font_size"]
        self.setFont(self._font)

        if self.wcfg["enable_single_class_exclusive_mode"]:
            max_display = self.wcfg["maximum_vehicles_exclusive_mode"]
        elif self.wcfg["enable_multi_class_split_mode"]:
            max_display = self.wcfg["maximum_vehicles_split_mode"]
        else:
            max_display = self.wcfg["maximum_vehicles_combined_mode"]
        self.veh_range = min(max(int(max_display), 5), 126)

        self._energy_decimals = max(int(self.wcfg["decimal_places_energy_remaining"]), 0)
        self._energy_width = 3 + self._energy_decimals + bool(self._energy_decimals)
        self._gap_decimals = max(int(self.wcfg["decimal_places_time_gap"]), 0)
        self._interval_decimals = max(int(self.wcfg["decimal_places_time_interval"]), 0)
        self._class_gap = (
            self.wcfg["enable_multi_class_split_mode"]
            and self.wcfg["show_time_gap_from_same_class"]
        )
        self._class_interval = (
            self.wcfg["enable_multi_class_split_mode"]
            and self.wcfg["show_time_interval_from_same_class"]
        )
        self._show_groups = self.wcfg["split_gap"] > 0
        self._show_each_tyre = self.wcfg["show_compound_for_each_wheel"]
        self._mixed_tyre = self.wcfg["mixed_compound_symbol"][:1] or "?"
        self._brand_logos = {}
        self._weather_cfg = self.cfg.user.setting["weather"]
        self._temperature_trend = TrendTimer(self._weather_cfg["temperature_trend_interval"])
        self._temperature_unit = units.set_unit_temperature(self.cfg.units["temperature_unit"])
        self._temperature_symbol = units.set_symbol_temperature(self.cfg.units["temperature_unit"])
        self._temperature_decimals = min(max(int(self._weather_cfg["decimal_places_temperature"]), 0), 6)
        self._trend_colors = {
            0: QColor(self._weather_cfg["font_color_trend_constant"]),
            1: QColor(self._weather_cfg["font_color_trend_increasing"]),
            -1: QColor(self._weather_cfg["font_color_trend_decreasing"]),
        }
        self._rubber_median_laps = max(int(self._weather_cfg["rubber_median_laps"]), 100)
        self._rubber_time_scale = (
            self._weather_cfg["rubber_time_scale_practice"],
            self._weather_cfg["rubber_time_scale_practice"],
            self._weather_cfg["rubber_time_scale_qualifying"],
            self._weather_cfg["rubber_time_scale_race"],
            self._weather_cfg["rubber_time_scale_race"],
        )
        self._rubber_starting = (
            self._weather_cfg["starting_rubber_practice"],
            self._weather_cfg["starting_rubber_practice"],
            self._weather_cfg["starting_rubber_qualifying"],
            self._weather_cfg["starting_rubber_race"],
            self._weather_cfg["starting_rubber_race"],
        )

        columns = {"energy_width": self._energy_width, "energy_decimals": self._energy_decimals}
        self.board = StandingsBoard(
            self, self._font, font_size, self.wcfg["font_weight"], columns, self.veh_range
        )
        layout = self.set_grid_layout(gap=0, margin=0)
        layout.addWidget(self.board, 0, 0)
        self.set_primary_layout(layout=layout, margin=0, align=Qt.AlignLeft | Qt.AlignTop)

    def timerEvent(self, event):
        """Collect the current order and refresh the painted board."""
        self.update_weather_footer()
        race_session = api.read.session.session_type() == 4
        time_left = max(api.read.session.remaining() - minfo.vehicles.finishTimeOffset, 0)
        lap_number = api.read.lap.number()
        lap_progress = api.read.lap.progress()
        if race_session and api.read.session.finish_type(minfo.vehicles.finishAsLap):
            lap_total_text = f"{api.read.lap.maximum():d}"
        else:
            lap_total = lap_number + calc.end_timer_laps_remain(
                lap_progress, minfo.delta.lapTimePace, time_left
            )
            lap_total_text = f"~{lap_total:.1f}"
        lap_info = f"{lap_number + lap_progress:.1f} / {lap_total_text}"
        self.board.set_session_info(
            calc.sec2countdown(time_left), lap_info, strftime("%H:%M:%S")
        )
        self.board.set_lap_mode(race_session)

        standings = minfo.relative.standings
        if not standings:
            self.board.set_rows([])
            return

        rows = []
        in_race = api.read.session.in_race()
        usable = standings[:-1]  # final -1 is the API's list terminator
        for index, std_idx in enumerate(usable[:self.veh_range]):
            if std_idx == -1:
                if self._show_groups:
                    next_idx = next((item for item in usable[index + 1:] if item >= 0), None)
                    if next_idx is not None:
                        class_name = minfo.vehicles.dataSet[next_idx].vehicleClass
                        class_bg, class_text, class_label = self.class_style(class_name)
                        rows.append({"group": True, "name": class_label,
                                     "class_bg": class_bg, "class_text": class_text})
                continue
            if std_idx < 0:
                continue

            vehicle = minfo.vehicles.dataSet[std_idx]
            is_player = bool(self.wcfg["show_player_highlighted"] and vehicle.isPlayer)
            if self.wcfg["show_position_change_in_class"]:
                change = vehicle.qualifyInClass - vehicle.positionInClass
            else:
                change = vehicle.qualifyOverall - vehicle.positionOverall

            is_class_leader = (
                vehicle.classLeaderIndex == std_idx or vehicle.positionInClass == 1
            )
            if is_class_leader:
                gap = f"{int(vehicle.totalLapProgress)}L"
            elif in_race:
                if self._class_gap:
                    gap = self.gap_to_leader_race(vehicle.gapBehindLeaderInClass, vehicle.positionInClass)
                else:
                    gap = self.gap_to_leader_race(vehicle.gapBehindLeader, vehicle.positionOverall)
            else:
                if self._class_gap:
                    gap = self.gap_to_leader_best(vehicle.bestLapTime, vehicle.classBestLapTime)
                else:
                    gap = self.gap_to_leader_best(vehicle.bestLapTime, minfo.vehicles.leaderBestLapTime)

            if self._class_interval:
                interval = self.interval_to_next(vehicle.positionInClass, vehicle.gapBehindNextInClass)
            else:
                interval = self.interval_to_next(vehicle.positionOverall, vehicle.gapBehindNext)

            if race_session and vehicle.pitTimer.pitting:
                laptime = self.pit_laptime(vehicle.inPit, vehicle.pitTimer.elapsed)
                is_best = False
            elif race_session:
                laptime = self.format_laptime(vehicle.lastLapTime, vehicle.isValidLap)
                is_best = bool(vehicle.isClassFastestLastLap)
            else:
                laptime = self.format_laptime(vehicle.bestLapTime)
                is_best = (vehicle.bestLapTime > 0
                           and vehicle.bestLapTime < MAX_SECONDS
                           and abs(vehicle.bestLapTime - vehicle.classBestLapTime) < 0.001)

            class_name = vehicle.vehicleClass
            class_bg, class_text, class_label = self.class_style(class_name)
            tire_names = tuple(vehicle.tireCompoundName)
            if self._show_each_tyre:
                symbols = tuple(select_compound_symbol(name) for name in tire_names)
                tire_colors = tuple(select_compound_color(name) for name in tire_names)
            else:
                first = tire_names[0] if tire_names else ""
                mixed = any(name != first for name in tire_names)
                symbols = (self._mixed_tyre if mixed else select_compound_symbol(first),)
                tire_colors = (select_compound_color(first),) if first else (FAINT.name(),)

            pit_index = 4 if vehicle.isFinished else int(vehicle.inPit)
            if vehicle.isYellow and pit_index == 0:
                pit_index = 3
            pit_index = min(max(pit_index, 0), 4)
            status_text = (
                "", self.wcfg["pit_status_text"] or "PIT",
                self.wcfg["garage_status_text"] or "GRG",
                "",
                self.wcfg["finish_status_text"] or "FIN",
            )[pit_index]
            status_color = (BLUE, GREEN, YELLOW_ACCENT, QColor("#CFD8DF"))[pit_index - 1] if pit_index else FAINT

            name = vehicle.driverName
            if self.wcfg["driver_name_shorten"]:
                name = shorten_driver_name(name)
            if self.wcfg["driver_name_uppercase"]:
                name = name.upper()

            rows.append({
                "position": int(vehicle.positionOverall),
                "class_position": int(vehicle.positionInClass),
                "change": int(change),
                "driver": name,
                "class": class_label,
                "class_bg": class_bg,
                "class_text": class_text,
                "brand": self.brand_logo(vehicle.vehicleBrand),
                "damage": min(max((1.0 - float(vehicle.vehicleIntegrity)) * 100.0, 0.0), 100.0),
                "gap": gap,
                "interval": interval,
                "gap_leader": self.wcfg["time_gap_leader_text"],
                "interval_leader": self.wcfg["time_interval_leader_text"],
                "laptime": laptime,
                "best": is_best,
                "energy": vehicle.energyRemaining,
                "tyre_symbols": symbols,
                "tyre_colors": tire_colors,
                "status": status_text,
                "status_color": status_color,
                "status_emphasis": pit_index in (1, 3),
                "status_fill": pit_index == 3,
                "player": is_player,
            })
        self.board.set_rows(rows)

    def update_weather_footer(self):
        """Mirror the current weather widget's key track conditions."""
        track_temp = api.read.session.track_temperature()
        air_temp = api.read.session.ambient_temperature()
        temp_reading = round(track_temp + air_temp, 1)
        trend = self._temperature_trend.update(temp_reading, api.read.timing.elapsed())
        decimals = self._temperature_decimals
        track_text = f"{self._temperature_unit(track_temp):.{decimals}f}{self._temperature_symbol}"
        air_text = f"{self._temperature_unit(air_temp):.{decimals}f}{self._temperature_symbol}"
        temperature = f"{track_text} ({air_text})"
        trend_symbol = TEXT_TREND_SIGN[trend]

        rain = round(api.read.session.raininess(), 2)
        rain_text = f"{rain:.0%}"
        wet_min, wet_max, wet_avg = api.read.session.wetness()
        if wet_avg >= 0.01:
            surface_text = f"{self._weather_cfg['prefix_wetness_wet']} {wet_avg:.0%}"
            surface_color = BLUE
        elif self._weather_cfg["show_rubber_coverage_while_dry"]:
            session_type = api.read.session.session_type()
            rubber_laps = rubber_to_laps(
                self._rubber_starting[session_type], self._rubber_median_laps
            )
            rubber_scale = self._rubber_time_scale[session_type]
            if rubber_scale > 0:
                rubber_laps += minfo.vehicles.totalCompletedLaps * rubber_scale
            coverage = laps_to_rubber(rubber_laps, self._rubber_median_laps)
            surface_text = f"{self._weather_cfg['prefix_wetness_dry']} {coverage:.0%}"
            surface_color = GREEN
        else:
            surface_text = f"{self._weather_cfg['prefix_wetness_dry']} 0%"
            surface_color = GREEN

        self.board.set_weather_info(
            temperature, trend_symbol, self._trend_colors[trend], rain_text,
            surface_text, surface_color,
        )

    def class_style(self, class_name):
        """Use each class accent as the badge/rail color with readable text."""
        normalized = "".join(char for char in (class_name or "").upper() if char.isalnum())
        key = ""
        for candidate in ("HYPERCAR", "LMDH", "LMH", "LMP2", "LMP3", "GT3", "GTE", "HY"):
            if normalized == candidate or candidate in normalized:
                key = candidate
                break

        style = self.cfg.user.classes.get(class_name)
        label = style["alias"] if style is not None else class_name
        if key in CLASS_COLORS:
            preferred_surface, accent = CLASS_COLORS[key]
            # GT3 shares the requested red accent with Hypercar. Reuse the
            # existing palette hex rather than introducing or changing one.
            return accent, readable_class_text(accent, preferred_surface), label

        if style is not None:
            accent = QColor(style["color"]).name()
            return accent, readable_class_text(accent, "#10161C"), label
        if class_name:
            hue = (sum(ord(char) for char in class_name) * 47) % 360
            accent = QColor.fromHsv(hue, 115, 205).name()
            return accent, readable_class_text(accent, "#10161C"), class_name
        return "#25333D", MUTED.name(), class_name

    def brand_logo(self, brand_name):
        """Find the matching make logo across configured and bundled folders."""
        key = brand_name or ""
        if key not in self._brand_logos:
            logo = None
            requested = "".join(char.casefold() for char in key if char.isalnum())
            aliases = {requested}
            if "corvette" in requested or "chevrolet" in requested or "chevrolette" in requested:
                aliases.update(("chevrolet", "chevrolette"))
            if "mustang" in requested or "ford" in requested:
                aliases.add("ford")
            if "lambo" in requested or "lamborghini" in requested:
                aliases.add("lamborghini")

            folders = []
            configured = self.cfg.path.brand_logo
            if configured:
                folders.append(Path(configured))
            folders.append(Path(__file__).resolve().parents[2] / "brandlogo")
            seen = set()
            for folder in folders:
                try:
                    folder_key = str(folder.resolve()).casefold()
                    if folder_key in seen or not folder.is_dir():
                        continue
                    seen.add(folder_key)
                    candidates = [item for item in folder.iterdir()
                                  if item.suffix.casefold() == ".png"]
                    match = None
                    for candidate in candidates:
                        stem = "".join(char.casefold() for char in candidate.stem if char.isalnum())
                        if stem in aliases or (len(stem) >= 4 and stem in requested):
                            match = candidate
                            break
                    if match is not None:
                        logo = load_brand_logo_image(
                            filepath=str(match.parent) + os.sep,
                            filename=match.stem,
                            max_width=round(self.wcfg["font_size"] * 3.6),
                            max_height=round(self.wcfg["font_size"] * 1.25),
                        )
                        break
                except OSError:
                    continue
            self._brand_logos[key] = logo
        return self._brand_logos[key]

    def format_laptime(self, laptime, valid=True):
        if 0 < laptime < MAX_SECONDS:
            value = calc.sec2laptime_full(laptime)
            return value if valid else f"*{value}"
        return TEXT_NOLAPTIME

    def pit_laptime(self, in_pit, pit_time):
        if 0 < pit_time < MAX_SECONDS:
            return f"{'PIT' if in_pit else 'OUT'}{pit_time:>5.1f}"
        return TEXT_NOLAPTIME

    def gap_to_leader_best(self, player_best, leader_best):
        gap = player_best - leader_best
        if gap == 0 and player_best > 0:
            return self.wcfg["time_gap_leader_text"]
        if gap < 0 or player_best < 1:
            return "0.0"
        return f"{gap:.{self._gap_decimals}f}"

    def gap_to_leader_race(self, gap_behind, position):
        if position == 1:
            return self.wcfg["time_gap_leader_text"]
        if isinstance(gap_behind, int):
            return f"{gap_behind:.0f}L"
        return f"{gap_behind:.{self._gap_decimals}f}"

    def interval_to_next(self, position, gap_behind):
        if position == 1:
            return self.wcfg["time_interval_leader_text"]
        if isinstance(gap_behind, int):
            return f"{gap_behind:.0f}L"
        return f"{gap_behind:.{self._interval_decimals}f}"
