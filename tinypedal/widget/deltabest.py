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
Deltabest Widget
"""

from PySide2.QtCore import QRectF, Qt
from PySide2.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen

from .. import calculation as calc
from ..module_info import minfo
from ._base import Overlay


class Realtime(Overlay):
    """Draw widget"""

    def __init__(self, config, widget_name):
        # Assign base setting
        super().__init__(config, widget_name)

        # Config font
        font = self.config_font(
            self.wcfg["font_name"],
            self.wcfg["font_size"],
            self.wcfg["font_weight"],
        )
        self.setFont(font)
        font_m = self.get_font_metrics(font)

        # Config variable
        self.laptime_source = f"lapTime{self.wcfg['deltabest_source']}"
        self.delta_source = f"delta{self.wcfg['deltabest_source']}"
        bar_gap = self.wcfg["bar_gap"]
        padx = round(font_m.width * self.wcfg["bar_padding_horizontal"])
        pady = round(font_m.capital * self.wcfg["bar_padding_vertical"])
        self.dbar_length = int(self.wcfg["delta_bar_length"] * 0.5)
        self.dbar_height = max(int(self.wcfg["delta_bar_height"]), 6)

        self.decimals = max(self.wcfg["decimal_places"], 1)
        self.delta_display_range = calc.decimal_strip(self.wcfg["delta_display_range"], self.decimals)
        self.max_padding = 4 + self.decimals
        self.delta_width = font_m.width * self.max_padding + padx * 2
        self.delta_height = font_m.capital + pady * 2
        self.bar_gap = max(int(bar_gap), 3)
        self.card_padding = max(round(self.wcfg["font_size"] * 0.38), 6)

        self.freeze_duration = min(max(self.wcfg["freeze_duration"], 0), 30)
        self.delta_color = (
            QColor(self.wcfg["background_color_time_gain"]),
            QColor(self.wcfg["background_color_time_loss"]),
        )

        content_width = max(self.dbar_length * 2, self.delta_width)
        content_height = self.delta_height
        if self.wcfg["show_delta_bar"]:
            content_height += self.bar_gap + self.dbar_height
        self.resize(content_width + self.card_padding * 2,
                     content_height + self.card_padding * 2)

        self.pen_text = QPen()

        # Last data
        self.delta_best = 0
        self.last_laptime = 0
        self.new_lap = True

    def timerEvent(self, event):
        """Update when vehicle on track"""
        if minfo.delta.lapTimeCurrent < self.freeze_duration:
            temp_best = minfo.delta.lapTimeLast - self.last_laptime
            self.new_lap = True
        else:
            if self.new_lap:
                self.last_laptime = getattr(minfo.delta, self.laptime_source)
                self.new_lap = False

            temp_best = getattr(minfo.delta, self.delta_source)

        if self.delta_best != temp_best:
            self.delta_best = temp_best
            self.update()

    # GUI update methods
    def paintEvent(self, event):
        """Draw"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        panel = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        panel_path = QPainterPath()
        radius = max(self.wcfg["font_size"] * 0.34, 8)
        panel_path.addRoundedRect(panel, radius, radius)
        painter.fillPath(panel_path, QColor("#FF121B26"))
        painter.setPen(QPen(QColor("#557F9BAA"), 1))
        painter.drawPath(panel_path)

        highlight_color = QColor(self.delta_color[self.delta_best > 0])
        pad = self.card_padding
        bar_width = self.width() - pad * 2
        value_text = f"{calc.sym_max(self.delta_best, self.delta_display_range):+.{self.decimals}f}"[:self.max_padding]
        if self.wcfg["layout"] == 0 and self.wcfg["show_delta_bar"]:
            bar_y = pad
            value_y = bar_y + self.dbar_height + self.bar_gap
        elif self.wcfg["show_delta_bar"]:
            value_y = pad
            bar_y = value_y + self.delta_height + self.bar_gap
        else:
            value_y = pad

        value_width = min(self.delta_width, bar_width)
        value_rect = QRectF(pad + (bar_width - value_width) / 2,
                            value_y, value_width, self.delta_height)
        if self.wcfg["swap_style"]:
            chip_path = QPainterPath()
            chip_path.addRoundedRect(value_rect, radius * 0.45, radius * 0.45)
            painter.fillPath(chip_path, highlight_color)
            self.pen_text.setColor(self.wcfg["font_color_deltabest"])
        else:
            self.pen_text.setColor(highlight_color)
        painter.setPen(self.pen_text)
        painter.drawText(value_rect, Qt.AlignCenter, value_text)

        # Fixed zero point: gains extend left in green and losses extend right in red.
        if self.wcfg["show_delta_bar"]:
            track = QRectF(pad, bar_y, bar_width, self.dbar_height)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#2736404B"))
            painter.drawRoundedRect(track, self.dbar_height / 2, self.dbar_height / 2)
            display_range = max(abs(self.wcfg["delta_bar_display_range"]), 0.001)
            fill_width = min(abs(self.delta_best) / display_range, 1.0) * track.width() / 2
            if fill_width > 0:
                fill_x = track.center().x() if self.delta_best > 0 else track.center().x() - fill_width
                fill = QRectF(fill_x, track.top(), fill_width, track.height())
                gradient = QLinearGradient(fill.topLeft(), fill.topRight())
                gradient.setColorAt(0, highlight_color.darker(112))
                gradient.setColorAt(1, highlight_color.lighter(118))
                painter.setBrush(gradient)
                radius = min(self.dbar_height / 2, fill_width / 2)
                fill_path = QPainterPath()
                if self.delta_best > 0:
                    fill_path.moveTo(fill.left(), fill.top())
                    fill_path.lineTo(fill.right() - radius, fill.top())
                    fill_path.quadTo(fill.right(), fill.top(), fill.right(), fill.top() + radius)
                    fill_path.lineTo(fill.right(), fill.bottom() - radius)
                    fill_path.quadTo(fill.right(), fill.bottom(), fill.right() - radius, fill.bottom())
                    fill_path.lineTo(fill.left(), fill.bottom())
                else:
                    fill_path.moveTo(fill.left() + radius, fill.top())
                    fill_path.lineTo(fill.right(), fill.top())
                    fill_path.lineTo(fill.right(), fill.bottom())
                    fill_path.lineTo(fill.left() + radius, fill.bottom())
                    fill_path.quadTo(fill.left(), fill.bottom(), fill.left(), fill.bottom() - radius)
                    fill_path.lineTo(fill.left(), fill.top() + radius)
                    fill_path.quadTo(fill.left(), fill.top(), fill.left() + radius, fill.top())
                fill_path.closeSubpath()
                painter.drawPath(fill_path)
            painter.setPen(QPen(QColor("#99DCE5EC"), 1))
            center_x = track.center().x()
            painter.drawLine(int(center_x), int(track.top() - 2),
                             int(center_x), int(track.bottom() + 2))

