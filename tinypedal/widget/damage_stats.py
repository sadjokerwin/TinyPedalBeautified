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
Damage stats widget with compact integrity cards.
"""

from PySide2.QtCore import QRectF, Qt
from PySide2.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen

from ..api_control import api
from ..const_common import TEXT_NA
from ..regex_pattern import FONT_WEIGHT_MAP
from ._base import Overlay


PANEL = QColor("#F0121B26")
PANEL_EDGE = QColor("#557F9BAA")
CARD = QColor("#FF202B36")
CARD_EDGE = QColor("#283F4D5A")
TEXT = QColor("#F1F5F8")
MUTED = QColor("#91A5B5")
FAINT = QColor("#5F7382")
HEALTHY = QColor("#58D6C7")
WARNING = QColor("#F6C445")
CRITICAL = QColor("#FF785F")
TRACK = QColor("#35434F5B")


class Realtime(Overlay):
    """Show aero, body, and suspension integrity as readable health cards."""

    def __init__(self, config, widget_name):
        super().__init__(config, widget_name)
        self._font = self.config_font(
            self.wcfg["font_name"], self.wcfg["font_size"], self.wcfg["font_weight"]
        )
        self.setFont(self._font)
        self._font_size = max(float(self.wcfg["font_size"]), 10.0)
        self._font_weight = FONT_WEIGHT_MAP[self.wcfg["font_weight"]]
        self._pad = max(self._font_size * 0.3, 4)
        self._gap = max(self._font_size * 0.2, 2)
        self._card_height = max(self._font_size * 4.0, 58)
        self._values = {}

        definitions = (
            ("aero", "AERO", "show_aero_integrity", "low_aero_integrity_threshold",
             "display_order_aero_integrity", QColor("#8BC8FF")),
            ("body", "BODY", "show_body_integrity", "low_body_integrity_threshold",
             "display_order_body_integrity", QColor("#F6C445")),
            ("suspension", "SUSP", "show_suspension_integrity", "low_suspension_integrity_threshold",
             "display_order_suspension_integrity", QColor("#C5A4F2")),
        )
        self._metrics = [
            {"key": key, "label": label, "threshold": self.wcfg[threshold], "accent": accent,
             "value": None, "order": self.wcfg[order]}
            for key, label, enabled, threshold, order, accent in definitions
            if self.wcfg[enabled]
        ]
        self._metrics.sort(key=lambda metric: metric["order"])
        value_width = self.fontMetrics().horizontalAdvance("100%") * 1.7
        self._card_width = max(self._font_size * 5.2, value_width + self._font_size * 0.8)
        count = max(len(self._metrics), 1)
        width = self._pad * 2 + count * self._card_width + max(count - 1, 0) * self._gap
        height = self._pad * 2 + self._card_height
        self.setFixedSize(round(width), round(height))

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

    def timerEvent(self, event):
        """Refresh integrity readings from the telemetry API."""
        readings = {
            "aero": self._aero_integrity(),
            "body": max(min(1 - sum(api.read.vehicle.damage_severity()) / 16, 1), 0),
            "suspension": self._suspension_integrity(),
        }
        changed = False
        for metric in self._metrics:
            value = readings[metric["key"]]
            if metric["value"] != value:
                metric["value"] = value
                changed = True
        if changed:
            self.update()

    @staticmethod
    def _aero_integrity():
        damage = api.read.vehicle.aero_damage()
        return max(min(1 - damage, 1), 0) if damage >= 0 else None

    @staticmethod
    def _suspension_integrity():
        damage = max(api.read.wheel.suspension_damage())
        if damage >= 0:
            return max(min(1 - damage, 1), 0)
        return float(not any(api.read.wheel.is_detached()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        outer = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        self._round_rect(painter, outer, self._font_size * 0.6, PANEL, PANEL_EDGE)

        x = self._pad
        y = self._pad
        for metric in self._metrics:
            card = QRectF(x, y, self._card_width, self._card_height)
            self._round_rect(painter, card, self._font_size * 0.48, CARD, CARD_EDGE)

            rail = QRectF(card.left() + 1, card.top() + self._font_size * 0.32,
                          max(self._font_size * 0.14, 2), self._font_size * 0.62)
            self._round_rect(painter, rail, rail.width() / 2, metric["accent"])

            label_rect = QRectF(card.left() + self._font_size * 0.58,
                                card.top() + self._font_size * 0.16,
                                card.width() - self._font_size * 0.8,
                                self._font_size * 0.68)
            painter.setPen(MUTED)
            painter.setFont(self._font_for(self._font_size * 0.72, True))
            painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, metric["label"])

            value = metric["value"]
            if value is None:
                value_text = TEXT_NA
                health_color = FAINT
                status = "NO DATA"
                ratio = 0.0
            else:
                ratio = max(min(value, 1.0), 0.0)
                value_text = f"{round(ratio * 100):d}%"
                threshold = metric["threshold"]
                if ratio <= threshold:
                    health_color, status = CRITICAL, "CRITICAL"
                elif ratio <= min(threshold + 0.2, 1.0):
                    health_color, status = WARNING, "CHECK"
                else:
                    health_color, status = HEALTHY, "NOMINAL"

            value_rect = QRectF(card.left() + self._font_size * 0.58,
                                card.top() + self._font_size * 0.82,
                                card.width() - self._font_size * 0.76,
                                self._font_size * 1.75)
            painter.setPen(TEXT if value is None else health_color)
            painter.setFont(self._font_for(self._font_size * 1.7, True, True))
            painter.drawText(value_rect, Qt.AlignLeft | Qt.AlignVCenter, value_text)

            status_rect = QRectF(card.left() + self._font_size * 0.58,
                                 card.top() + self._font_size * 2.9,
                                 card.width() - self._font_size * 0.8,
                                 self._font_size * 0.58)
            painter.setPen(health_color)
            painter.setFont(self._font_for(self._font_size * 0.58, True))
            painter.drawText(status_rect, Qt.AlignLeft | Qt.AlignVCenter, status)

            track = QRectF(card.left() + self._font_size * 0.58,
                           card.bottom() - self._font_size * 0.34,
                           card.width() - self._font_size * 1.1,
                           max(self._font_size * 0.16, 2))
            self._round_rect(painter, track, track.height() / 2, TRACK)
            if ratio > 0:
                fill = QRectF(track.left(), track.top(), track.width() * ratio, track.height())
                gradient = QLinearGradient(fill.topLeft(), fill.topRight())
                gradient.setColorAt(0, health_color.darker(112))
                gradient.setColorAt(1, health_color.lighter(112))
                self._round_rect(painter, fill, track.height() / 2, gradient)
            x += self._card_width + self._gap
