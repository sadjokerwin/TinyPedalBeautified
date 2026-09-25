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
Battery and hybrid energy widget.
"""

from PySide2.QtCore import QRectF, Qt
from PySide2.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide2.QtWidgets import QWidget

from ..api_control import api
from ..module_info import minfo
from ..regex_pattern import FONT_WEIGHT_MAP
from ._base import Overlay


class BatteryPanel(QWidget):
    """Compact hybrid energy dashboard."""

    def __init__(self, parent, font_name: str, font_size: int, font_weight: str):
        super().__init__(parent)
        self._scale = max(font_size, 10)
        self._family = font_name
        self._weight = font_weight
        self._soc = 0.0
        self._net = 0.0
        self._state = 0
        self._warning = 0
        self._car_type = ""
        self._motor_map = -1
        self._map_label = "—"
        self._map_color = QColor("#748391")
        self.setFixedSize(round(self._scale * 19), round(self._scale * 9.2))

    def set_data(self, soc, net, state, warning, car_type, motor_map, map_label, map_color):
        data = (soc, net, state, warning, car_type, motor_map, map_label, map_color)
        old = (
            self._soc, self._net, self._state, self._warning,
            self._car_type, self._motor_map, self._map_label, self._map_color,
        )
        if old == data:
            return
        (
            self._soc, self._net, self._state, self._warning,
            self._car_type, self._motor_map, self._map_label, self._map_color,
        ) = data
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
        width, height = self.width(), self.height()
        margin = scale * 0.25
        panel = QRectF(margin, margin, width - margin * 2, height - margin * 2)

        # Dark glass panel with a fine cool edge.
        path = QPainterPath()
        path.addRoundedRect(panel, scale * 0.62, scale * 0.62)
        painter.fillPath(path, QColor("#E8121B26"))
        painter.setPen(QPen(QColor("#557F9BAA"), max(scale * 0.045, 0.6)))
        painter.drawPath(path)

        pad = scale * 0.8
        left = panel.left() + pad
        right = panel.right() - pad
        top = panel.top() + pad * 0.72
        accent = QColor("#58D6C7")
        if self._warning == 1:
            accent = QColor("#FF785F")
        elif self._warning == 2:
            accent = QColor("#C58BFF")

        # Header and live motor state.
        painter.setPen(QColor("#91A5B5"))
        painter.setFont(self._font(scale * 0.72, True))
        painter.drawText(QRectF(left, top, scale * 7, scale * 1.1), Qt.AlignLeft | Qt.AlignVCenter, "HYBRID ENERGY")
        state_label, state_color = {
            0: ("STANDBY", QColor("#91A5B5")),
            1: ("STANDBY", QColor("#91A5B5")),
            2: ("DEPLOYING", QColor("#58D6C7")),
            3: ("REGEN", QColor("#8BC8FF")),
        }.get(self._state, ("NO DATA", QColor("#748391")))
        pill_width = scale * 9
        pill = QRectF(right - pill_width, top + scale * 0.08, pill_width, scale * 0.92)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(state_color.red(), state_color.green(), state_color.blue(), 32))
        painter.drawRoundedRect(pill, scale * 0.4, scale * 0.4)
        painter.setPen(state_color)
        painter.setFont(self._font(scale * 0.75, True))
        painter.drawText(pill, Qt.AlignCenter, state_label)

        content_top = top + scale * 1.5
        # Large SOC readout.
        soc_color = accent if self._warning == 0 else accent
        painter.setPen(soc_color)
        painter.setFont(self._font(scale * 2.35, True))
        painter.drawText(QRectF(left, content_top, scale * 9, scale * 2.7), Qt.AlignLeft | Qt.AlignVCenter,
                         f"{self._soc:.1f}%")
        painter.setPen(QColor("#91A5B5"))
        painter.setFont(self._font(scale * 0.62, True))
        painter.drawText(QRectF(left, content_top + scale * 2.85, scale * 9, scale * 0.9),
                         Qt.AlignLeft | Qt.AlignVCenter, "STATE OF CHARGE")

        # Two compact telemetry cells on the right.
        split_x = left + scale * 9.7
        painter.setPen(QPen(QColor("#33455260"), max(scale * 0.05, 0.7)))
        painter.drawLine(int(split_x), int(content_top + scale * 0.15),
                         int(split_x), int(content_top + scale * 3.7))
        cell_x = split_x + scale * 0.72
        cell_width = right - cell_x
        painter.setPen(QColor("#91A5B5"))
        painter.setFont(self._font(scale * 0.6, True))
        painter.drawText(QRectF(cell_x, content_top + scale * 0.12, cell_width, scale * 0.9),
                         Qt.AlignLeft | Qt.AlignVCenter, "THIS LAP")
        net_color = QColor("#58D6C7") if self._net >= 0 else QColor("#FF9A6B")
        painter.setPen(net_color)
        painter.setFont(self._font(scale * 1.38, True))
        painter.drawText(QRectF(cell_x, content_top + scale * 0.85, cell_width, scale * 1.45),
                         Qt.AlignLeft | Qt.AlignVCenter, f"{self._net:+.1f}%")
        # SOC track: restrained color ramp, with a clear current level.
        bar = QRectF(left, panel.bottom() - scale * 1.35, right - left, scale * 0.42)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#35434F5B"))
        painter.drawRoundedRect(bar, bar.height() / 2, bar.height() / 2)
        fill = QRectF(bar.left(), bar.top(), bar.width() * min(max(self._soc, 0.0), 100.0) / 100.0, bar.height())
        gradient = QLinearGradient(fill.topLeft(), fill.topRight())
        gradient.setColorAt(0, QColor("#39BDB3"))
        gradient.setColorAt(1, QColor("#83E0C5"))
        if self._warning == 1:
            gradient.setColorAt(0, QColor("#E9574F"))
            gradient.setColorAt(1, QColor("#FF9A6B"))
        elif self._warning == 2:
            gradient.setColorAt(0, QColor("#9A64D6"))
            gradient.setColorAt(1, QColor("#D39BFF"))
        painter.setBrush(gradient)
        painter.drawRoundedRect(fill, bar.height() / 2, bar.height() / 2)

        # Map level and its meaning are shown together with the car's hybrid class.
        map_title = f"{self._car_type} MOTOR MAP" if self._car_type else "MOTOR MAP"
        painter.setPen(QColor("#91A5B5"))
        painter.setFont(self._font(scale * 0.58, True))
        painter.drawText(QRectF(cell_x, content_top + scale * 2.4, cell_width, scale * 0.72),
                         Qt.AlignLeft | Qt.AlignVCenter, map_title)
        map_text = f"{self._motor_map}  {self._map_label}" if self._motor_map >= 0 else "—  N/A"
        painter.setPen(self._map_color)
        painter.setFont(self._font(scale * 0.88, True))
        painter.drawText(QRectF(cell_x, content_top + scale * 3.05, cell_width, scale * 1.0),
                         Qt.AlignLeft | Qt.AlignVCenter, map_text)


class Realtime(Overlay):
    """Draw widget"""

    def __init__(self, config, widget_name):
        super().__init__(config, widget_name)
        self.set_primary_layout(self.set_grid_layout(), align=Qt.AlignLeft | Qt.AlignTop)
        self.freeze_duration = min(max(self.wcfg["freeze_duration"], 0), 30)
        self.panel = BatteryPanel(
            self,
            self.wcfg["font_name"],
            self.wcfg["font_size"],
            self.wcfg["font_weight"],
        )
        self.layout().addWidget(self.panel)
        self.warn_flash = None
        if self.wcfg["show_battery_charge_warning_flash"]:
            from ._common import warning_flash

            self.warn_flash = warning_flash(
                self.wcfg["warning_flash_highlight_duration"],
                self.wcfg["warning_flash_interval"],
                self.wcfg["number_of_warning_flashes"],
            )

    def timerEvent(self, event):
        """Update current energy, lap balance and motor map."""
        soc = minfo.hybrid.batteryCharge
        if soc >= self.wcfg["high_battery_threshold"]:
            warning = 2
        elif soc <= self.wcfg["low_battery_threshold"]:
            warning = 1
        else:
            warning = 0

        if self.warn_flash is not None:
            if not self.warn_flash.send(warning):
                warning = 0

        if 0 <= minfo.delta.lapTimeCurrent < self.freeze_duration:
            drain = minfo.hybrid.batteryDrainLast
            regen = minfo.hybrid.batteryRegenLast
        else:
            drain = minfo.hybrid.batteryDrain
            regen = minfo.hybrid.batteryRegen
        net = regen - drain

        class_name = api.read.vehicle.class_name().strip()
        class_lower = class_name.casefold()
        if "lmdh" in class_lower:
            car_type = "LMDh"
        elif "lmh" in class_lower:
            car_type = "LMH"
        else:
            map_max = api.read.switch.motor_map_max()
            if map_max == 5:
                car_type = "LMDh"
            elif map_max == 10:
                car_type = "LMH"
            else:
                car_type = class_name[:10].upper()

        motor_map = api.read.switch.motor_map_level()
        map_label, map_color = motor_map_label(motor_map, car_type)
        motor_state = 0 if (motor_map == 0 and api.read.emotor.state() != 3) else api.read.emotor.state()
        self.panel.set_data(
            round(soc, 1),
            round(net, 2),
            motor_state,
            warning,
            car_type,
            motor_map,
            map_label,
            map_color,
        )


def motor_map_label(level: int, car_type: str) -> tuple[str, QColor]:
    """Map a car's motor-map level to a short driver-facing description."""
    colors = {
        "OFF": QColor("#9AA8B4"),
        "LOW": QColor("#63C7E8"),
        "MEDIUM": QColor("#65D6AE"),
        "HIGH": QColor("#FFC66D"),
        "MAX": QColor("#FF8B73"),
        "UNKNOWN": QColor("#9AA8B4"),
        "MAP": QColor("#9AA8B4"),
    }
    if level == 0:
        label = "OFF"
    elif car_type == "LMH":
        if 1 <= level <= 4:
            label = "LOW"
        elif level == 5:
            label = "MEDIUM"
        elif 6 <= level <= 9:
            label = "HIGH"
        elif level == 10:
            label = "MAX"
        else:
            label = "UNKNOWN"
    elif car_type == "LMDh":
        if 1 <= level <= 2:
            label = "LOW"
        elif level == 3:
            label = "MEDIUM"
        elif level == 4:
            label = "HIGH"
        elif level == 5:
            label = "MAX"
        else:
            label = "UNKNOWN"
    else:
        label = "MAP"
    return label, colors[label]
