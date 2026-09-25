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
Gear Widget
"""

from PySide2.QtCore import QRectF, Qt, QTimer
from PySide2.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide2.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import calculation as calc
from .. import units
from ..api_control import api
from ..const_common import FLOAT_INF, GEAR_SEQUENCE, TEXT_NA
from ..module_info import minfo
from ..regex_pattern import FONT_WEIGHT_MAP
from ._base import Overlay
from ._common import warning_flash
from ._painter import GearGaugeBar, PedalInputBar, ProgressBar


class RpmLedBar(QWidget):
    """RPM shift lights sized to fit the gear widget."""

    def __init__(self, parent, config, width):
        super().__init__(parent)
        self.cfg = config
        self.count = max(int(config["number_of_led"]), 3)
        self.margin = max(int(config["display_margin"]), 0)
        self.gap = max(int(config["inner_gap"]), 0)
        self.double_side = config["enable_double_side_led"]
        sides = 2 if self.double_side else 1
        led_gaps = self.gap * ((self.count - 1) * sides + sides - 1)
        available = max(width - self.margin * 2 - led_gaps, self.count * sides * 2)
        self.led_width = max(2, min(int(config["led_width"]), available // (self.count * sides)))
        self.led_height = max(3, min(int(config["led_height"]), round(self.led_width * 0.6)))
        self.radius = max(float(config["led_radius"]), 0)
        outline_width = max(int(config["led_outline_width"]), 0)
        if outline_width > 0:
            self.outline = QPen()
            self.outline.setColor(config["led_outline_color"])
            self.outline.setWidth(outline_width)
        else:
            self.outline = Qt.NoPen
        self.colors = tuple(
            QBrush(config[key], Qt.SolidPattern)
            for key in (
                "rpm_color_off", "rpm_color_low", "rpm_color_safe", "rpm_color_redline",
                "rpm_color_critical", "rpm_color_over_rev", "speed_limiter_flash_color",
            )
        )
        self.rpm_max = 0
        self.rpm_low = self.rpm_safe = self.rpm_redline = self.rpm_critical = self.rpm_overrev = 0
        self.rpm_scale = 0
        self.rpm = -1
        self.gear = self.gear_max = self.limiter = 0
        self.flicker = False
        self.warn_flash = (
            warning_flash(config["speed_limiter_flash_interval"],
                          config["speed_limiter_flash_interval"], FLOAT_INF)
            if config["show_speed_limiter_flash"] else None
        )
        self.setFixedSize(width, self.led_height + self.margin * 2)

    def update_data(self, rpm, gear):
        rpm_max = api.read.engine.rpm_max()
        if rpm_max != self.rpm_max:
            self.rpm_max = rpm_max
            self.rpm_low = rpm_max * self.cfg["rpm_multiplier_low"]
            self.rpm_safe = rpm_max * self.cfg["rpm_multiplier_safe"] - self.rpm_low
            self.rpm_redline = rpm_max * self.cfg["rpm_multiplier_redline"] - self.rpm_low
            self.rpm_critical = rpm_max * self.cfg["rpm_multiplier_critical"] - self.rpm_low
            self.rpm_overrev = rpm_max * self.cfg["rpm_multiplier_over_rev"] - self.rpm_low
            self.rpm_scale = self.count / max(self.rpm_critical, 0.0000001)
            self.gear_max = api.read.engine.gear_max()
        self.rpm = rpm
        self.gear = gear
        self.limiter = api.read.switch.speed_limiter() if self.cfg["show_speed_limiter_flash"] else 0
        self.update()

    def _color(self, rpm):
        if rpm < 0:
            return self.colors[0]
        if rpm < self.rpm_safe:
            return self.colors[1]
        if rpm < self.rpm_redline:
            return self.colors[2]
        if rpm < self.rpm_critical:
            return self.colors[3]
        return self.colors[0]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self.cfg["show_background"]:
            painter.fillRect(self.rect(), QColor(self.cfg["background_color"]))

        rpm_relative = self.rpm - self.rpm_low
        self.flicker = False
        if self.limiter and self.warn_flash is not None:
            self.flicker = self.warn_flash.send(True)
        elif (self.cfg["show_rpm_flickering_above_critical"]
              and rpm_relative >= self.rpm_critical and self.gear < self.gear_max):
            self.flicker = not self.flicker

        sides = 2 if self.double_side else 1
        per_side_width = self.count * self.led_width + (self.count - 1) * self.gap
        total_width = sides * per_side_width + (sides - 1) * self.gap
        x_start = max((self.width() - total_width) / 2, 0)
        painter.setPen(self.outline)
        for side in range(sides):
            for index in range(self.count):
                if self.limiter:
                    brush = self.colors[6 if self.flicker else 0]
                elif rpm_relative >= self.rpm_overrev:
                    brush = self.colors[0 if self.flicker else 5]
                elif rpm_relative >= self.rpm_critical:
                    brush = self.colors[0 if self.flicker else 4]
                elif rpm_relative < 0:
                    brush = self.colors[0]
                elif index < rpm_relative * self.rpm_scale:
                    brush = self._color(index / max(self.rpm_scale, 0.0000001))
                else:
                    brush = self.colors[0]
                x_index = index if side == 0 else self.count - index - 1
                x = x_start + side * (per_side_width + self.gap) + x_index * (self.led_width + self.gap)
                painter.setBrush(brush)
                rect = QRectF(x, self.margin, self.led_width, self.led_height)
                painter.drawRoundedRect(rect, self.radius, self.radius) if self.radius else painter.drawRect(rect)


class GearClusterPanel(QWidget):
    """Soft glass backing for the combined shift-light and pedal display."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        panel = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#557F9BAA"), 1))
        painter.setBrush(QColor("#E8121B26"))
        painter.drawRoundedRect(panel, 9, 9)


class GearDashboard(QWidget):
    """Purpose-built single-panel gear, speed, RPM and pedal display."""

    def __init__(self, parent, gear_cfg, pedal_cfg, rpm_cfg):
        super().__init__(parent)
        self.gear_cfg = gear_cfg
        self.pedal_cfg = pedal_cfg
        self.rpm_cfg = rpm_cfg
        self.family = gear_cfg["font_name"]
        self.base = max(int(gear_cfg["font_size"]), 18)
        self.gear_font = self._font(self.base * 1.18, gear_cfg["font_weight_gear"])
        self.speed_font = self._font(self.base * 0.92, gear_cfg["font_weight_speed"])
        self.gear = "N"
        self.speed = 0
        self.rpm = 0
        self.rpm_max = 0
        self.gear_max = 0
        self.speed_limiter = False
        self._pit_flash_phase = False
        self._pit_flash_timer = QTimer(self)
        self._pit_flash_timer.setInterval(250)
        self._pit_flash_timer.timeout.connect(self._toggle_pit_flash)
        self.rev_limiter = False
        self._rev_flash_phase = False
        self._rev_flash_timer = QTimer(self)
        self._rev_flash_timer.setInterval(250)
        self._rev_flash_timer.timeout.connect(self._toggle_rev_flash)
        self.pedals = {}
        self.led_count = max(int(rpm_cfg["number_of_led"]), 5)
        pedal_specs = (
            ("ffb", "show_ffb_meter", "ffb_color", "ffb_clipping_color", "font_color_ffb"),
            ("clutch", "show_clutch", "clutch_color", "clutch_color", "font_color_clutch"),
            ("brake", "show_brake", "brake_color", "brake_color", "font_color_brake"),
            ("throttle", "show_throttle", "throttle_color", "throttle_color", "font_color_throttle"),
        )
        self.pedal_specs = tuple(
            (name, QColor(pedal_cfg[color_key]), QColor(pedal_cfg[max_key]))
            for name, enabled_key, color_key, max_key, text_key in pedal_specs
            if pedal_cfg[enabled_key]
        )
        self.setFixedSize(round(self.base * 8.0), round(self.base * 4.0))

    def _font(self, size, weight="Bold"):
        font = QFont(self.family)
        font.setPixelSize(max(round(size), 1))
        font.setWeight(FONT_WEIGHT_MAP[weight])
        return font

    def set_telemetry(self, gear, speed, rpm, rpm_max, gear_max, limiter):
        limiter = bool(limiter)
        if limiter and not self.speed_limiter:
            self._pit_flash_phase = True
            self._pit_flash_timer.start()
        elif not limiter and self.speed_limiter:
            self._pit_flash_timer.stop()
            self._pit_flash_phase = False
        rev_limiter = bool(
            rpm_max > 0 and rpm >= rpm_max * self.rpm_cfg["rpm_multiplier_redline"]
        )
        if rev_limiter and not self.rev_limiter:
            self._rev_flash_phase = True
            self._rev_flash_timer.start()
        elif not rev_limiter and self.rev_limiter:
            self._rev_flash_timer.stop()
            self._rev_flash_phase = False
        self.gear = gear
        self.speed = speed
        self.rpm = rpm
        self.rpm_max = rpm_max
        self.gear_max = gear_max
        self.speed_limiter = limiter
        self.rev_limiter = rev_limiter
        self.update()

    def _toggle_rev_flash(self):
        self._rev_flash_phase = not self._rev_flash_phase
        self.update()

    def _toggle_pit_flash(self):
        self._pit_flash_phase = not self._pit_flash_phase
        self.update()

    def set_pedal(self, name, raw, filtered):
        self.pedals[name] = (min(max(float(raw), 0.0), 1.0), min(max(float(filtered), 0.0), 1.0))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        scale = self.base
        outer = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        panel_path = QPainterPath()
        panel_path.addRoundedRect(outer, scale * 0.32, scale * 0.32)
        p.fillPath(panel_path, QColor("#F7121B26"))
        p.setPen(QPen(QColor("#557F9BAA"), 1))
        p.drawPath(panel_path)

        pad = scale * 0.34
        left, right = pad, self.width() - pad
        # RPM arc rendered as a clean row of illuminated segments.
        led_gap = max(scale * 0.08, 2)
        led_h = max(scale * 0.16, 6)
        led_y = pad * 0.92
        led_w = (right - left - led_gap * (self.led_count - 1)) / self.led_count
        active_ratio = 0.0
        if self.rpm_max > 0:
            low = self.rpm_max * self.rpm_cfg["rpm_multiplier_low"]
            critical = self.rpm_max * self.rpm_cfg["rpm_multiplier_critical"]
            ramp_start = max(low - self.rpm_max * 0.15, 0)
            ramp_end = max(critical - self.rpm_max * 0.05, ramp_start + 1)
            ramp_span = ramp_end - ramp_start
            active_ratio = min(max((self.rpm - ramp_start) / ramp_span, 0.0), 1.0)
        led_colors = (
            QColor(self.rpm_cfg["rpm_color_low"]),
            QColor(self.rpm_cfg["rpm_color_safe"]),
            QColor(self.rpm_cfg["rpm_color_redline"]),
            QColor(self.rpm_cfg["rpm_color_critical"]),
            QColor(self.rpm_cfg["rpm_color_over_rev"]),
        )
        for i in range(self.led_count):
            rect = QRectF(left + i * (led_w + led_gap), led_y, led_w, led_h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#2636404B"))
            p.drawRoundedRect(rect, led_h / 2, led_h / 2)
            threshold = (i + 1) / self.led_count
            if self.rev_limiter:
                if self._rev_flash_phase:
                    p.setBrush(QColor("#38BDF8"))
                    p.drawRoundedRect(rect, led_h / 2, led_h / 2)
            elif self.speed_limiter:
                # Alternate the entire strip through blank / yellow intervals.
                if self._pit_flash_phase:
                    p.setBrush(QColor("#F6C445"))
                    p.drawRoundedRect(rect, led_h / 2, led_h / 2)
            elif active_ratio >= threshold:
                point = threshold
                color = led_colors[0] if point < 0.54 else led_colors[1] if point < 0.75 else led_colors[2] if point < 0.9 else led_colors[3]
                if self.rpm_max and self.rpm >= self.rpm_max * self.rpm_cfg["rpm_multiplier_over_rev"]:
                    color = led_colors[4]
                p.setBrush(color)
                p.drawRoundedRect(rect, led_h / 2, led_h / 2)

        # Gear and speed share the main face. Vertical pedal meters occupy the
        # right rail, keeping the primary readings large and uncluttered.
        core_top = led_y + led_h + scale * 0.22
        core_bottom = self.height() - pad * 0.8
        core_h = core_bottom - core_top
        pedal_left = right - (right - left) * 0.27
        center_x = left + (pedal_left - left) * 0.38
        accent = QColor("#58D6C7")
        if self.speed_limiter:
            # accent = QColor("#FF785F")
            accent = QColor("#F6C445")
        elif self.rev_limiter:
            accent = QColor("#38BDF8")
        gear_rect = QRectF(left, core_top, center_x - left - scale * 0.08, core_h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 24))
        p.drawRoundedRect(gear_rect, scale * 0.2, scale * 0.2)
        p.setPen(accent)
        p.setFont(self.gear_font)
        p.drawText(gear_rect, Qt.AlignCenter, self.gear)

        divider_x = center_x + scale * 0.02
        p.setPen(QPen(QColor("#41515E6A"), 1))
        p.drawLine(int(divider_x), int(core_top + scale * 0.12), int(divider_x), int(core_bottom - scale * 0.12))
        speed_left = divider_x + scale * 0.2
        speed_right = pedal_left - scale * 0.12
        p.setPen(QColor("#F1F5F8"))
        p.setFont(self.speed_font)
        speed_value = f"{int(round(self.speed)):03d}"
        if self.speed_limiter:
            pit_rect = QRectF(speed_left, core_top, speed_right - speed_left, core_h * 0.48)
            speed_rect = QRectF(speed_left, core_top + core_h * 0.42,
                                speed_right - speed_left, core_h * 0.58)
            p.setPen(QColor("#F6C445"))
            p.setFont(self.speed_font)
            p.drawText(pit_rect, Qt.AlignCenter, "PIT")
            p.setPen(QColor("#F1F5F8"))
            p.drawText(speed_rect, Qt.AlignCenter, speed_value)
        else:
            p.drawText(QRectF(speed_left, core_top, speed_right - speed_left, core_h),
                       Qt.AlignCenter, speed_value)

        # Colored vertical tracks identify each control without text labels.
        pedal_count = max(len(self.pedal_specs), 1)
        rail_left = pedal_left + scale * 0.08
        rail_width = right - rail_left
        cell_w = rail_width / pedal_count
        track_top = core_top + scale * 0.15
        track_bottom = core_bottom - scale * 0.38
        track_h = max(track_bottom - track_top, 1)
        for index, (name, color, clip_color) in enumerate(self.pedal_specs):
            x = rail_left + index * cell_w
            raw, filtered = self.pedals.get(name, (0.0, 0.0))
            track_w = min(scale * 0.25, cell_w * 0.54)
            track = QRectF(x + (cell_w - track_w) / 2, track_top, track_w, track_h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#2736404B"))
            p.drawRoundedRect(track, track_w / 2, track_w / 2)
            fill_h = track.height() * filtered
            fill = QRectF(track.left(), track.bottom() - fill_h, track.width(), fill_h)
            if fill.width() > 0:
                gradient = QLinearGradient(fill.bottomLeft(), fill.topLeft())
                gradient.setColorAt(0, color.darker(112))
                gradient.setColorAt(1, clip_color if name == "ffb" and filtered >= 0.98 else color.lighter(115))
                p.setBrush(gradient)
                p.drawRoundedRect(fill, track_w / 2, track_w / 2)


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
            self.wcfg["font_weight_gear"],
        )
        self.setFont(font)
        font_m = self.get_font_metrics(font)

        if self.wcfg["show_speed_below_gear"]:
            font_scale_speed = self.wcfg["font_scale_speed"]
        else:
            font_scale_speed = 1
        font_speed = self.config_font(
            self.wcfg["font_name"],
            round(self.wcfg["font_size"] * font_scale_speed),
            self.wcfg["font_weight_speed"]
        )

        font_batt = self.config_font(
            self.wcfg["font_name"],
            self.wcfg["font_size_battery"],
            self.wcfg["font_weight_battery"]
        )
        font_cons = self.config_font(
            self.wcfg["font_name"],
            self.wcfg["font_size_consumption"],
            self.wcfg["font_weight_consumption"]
        )

        # Config units
        self.unit_speed = units.set_unit_speed(self.cfg.units["speed_unit"])
        self.unit_fuel = units.set_unit_fuel(self.cfg.units["fuel_unit"])

        # Gear gauge
        (_, gauge_width, _, _, _) = self.set_gauge_size(font_m, font_scale_speed)
        # Battery bar
        if self.wcfg["show_battery_bar"]:
            font_batt_m = self.get_font_metrics(font_batt)
            self.decimals_batt = max(self.wcfg["decimal_places_battery"], 0)
            self.battbar_color = (
                self.wcfg["battery_bar_color"],
                self.wcfg["battery_bar_color_regen"],
                self.wcfg["warning_color_low_battery"],
                self.wcfg["warning_color_high_battery"],
            )
            self.bar_battbar = ProgressBar(
                self,
                font=font_batt,
                text=TEXT_NA,
                width=gauge_width,
                height=max(self.wcfg["battery_bar_height"], 1),
                offset_x=self.wcfg["battery_reading_offset_x"],
                offset_y=font_batt_m.voffset,
                input_color=self.battbar_color[0],
                fg_color=self.wcfg["font_color_battery"],
                bg_color=self.wcfg["background_color_battery_bar"],
                show_reading=self.wcfg["show_battery_reading"],
                align=self.set_text_alignment(self.wcfg["battery_reading_text_alignment"]),
                right_side=self.wcfg["show_inverted_battery"],
            )
            self.bar_battbar.state = None
            self.set_primary_orient(
                target=self.bar_battbar,
                column=self.wcfg["display_order_battery"],
            )

        # Consumption bar
        if self.wcfg["show_consumption_bar"]:
            font_cons_m = self.get_font_metrics(font_cons)
            self.decimals_cons = max(self.wcfg["decimal_places_consumption"], 0)
            self.consbar_color = (
                self.wcfg["consumption_color_normal"],
                self.wcfg["consumption_color_high"],
            )
            self.cons_exp = min(max(self.wcfg["consumption_progression_exponential_scale"], 1), 10)
            self.bar_consbar = ProgressBar(
                self,
                font=font_cons,
                text=TEXT_NA,
                width=gauge_width,
                height=max(self.wcfg["consumption_bar_height"], 1),
                offset_x=self.wcfg["consumption_reading_offset_x"],
                offset_y=font_cons_m.voffset,
                input_color=self.consbar_color[0],
                fg_color=self.wcfg["font_color_consumption"],
                bg_color=self.wcfg["background_color_consumption_bar"],
                show_reading=self.wcfg["show_consumption_reading"],
                align=self.set_text_alignment(self.wcfg["consumption_reading_text_alignment"]),
                right_side=self.wcfg["show_inverted_consumption"],
            )
            self.set_primary_orient(
                target=self.bar_consbar,
                column=self.wcfg["display_order_consumption"],
            )
            self.calc_ema_fuel_rate = calc.ema_filter(self.wcfg["maximum_average_consumption_samples"])

        # One purpose-built panel replaces the old collection of separate displays.
        rpm_led_cfg = self.cfg.user.setting["rpm_led"]
        pedal_cfg = self.cfg.user.setting["pedal"]
        self.pedal_cfg = pedal_cfg
        self.dashboard = GearDashboard(
            self, self.wcfg, pedal_cfg, rpm_led_cfg
        )
        self.set_primary_orient(target=self.dashboard, column=self.wcfg["display_order_gauge"])
        self.max_brake_pres = 0.01

        # Last data
        self.flicker = 0
        self.shifting_timer_start = 0
        self.shifting_timer = 0
        self.rpm_safe = 0
        self.rpm_red = 0
        self.rpm_crit = 0
        self.rpm_range = 0
        self.rpm_max = 0
        self.gear_max = 0
        self.last_gear = 0
        self.ema_fuel_rate = 0
        self.max_fuel_rate = 0

    def post_update(self):
        self.ema_fuel_rate = 0
        self.max_fuel_rate = 0
        self.max_brake_pres = 0.01

    def timerEvent(self, event):
        """Update when vehicle on track"""
        # RPM reference
        rpm_max = api.read.engine.rpm_max()
        if self.rpm_max != rpm_max:
            self.rpm_max = rpm_max
            self.rpm_safe = int(rpm_max * self.wcfg["rpm_multiplier_safe"])
            self.rpm_red = int(rpm_max * self.wcfg["rpm_multiplier_redline"])
            self.rpm_crit = int(rpm_max * self.wcfg["rpm_multiplier_critical"])
            self.rpm_range = rpm_max - self.rpm_safe
            self.gear_max = api.read.engine.gear_max()

        # Shifting timer
        gear = api.read.engine.gear()
        elapsed_time = api.read.timing.elapsed()
        if self.last_gear != gear:
            self.last_gear = gear
            self.shifting_timer_start = elapsed_time
        self.shifting_timer = elapsed_time - self.shifting_timer_start

        # Gauge
        rpm = api.read.engine.rpm()
        speed = api.read.vehicle.speed()
        limiter = api.read.switch.speed_limiter() if self.wcfg["show_speed_limiter"] else 0
        self.dashboard.set_telemetry(
            GEAR_SEQUENCE(gear, "N"), self.unit_speed(speed), rpm, rpm_max, self.gear_max, limiter
        )
        self.update_pedals()

        # Battery bar
        if self.wcfg["show_battery_bar"]:
            battery = minfo.hybrid.batteryCharge
            motor_state = minfo.hybrid.motorState
            self.update_battbar(self.bar_battbar, battery, motor_state)

        # Consumption bar
        if self.wcfg["show_consumption_bar"]:
            if self.wcfg["show_virtual_energy_if_available"] and minfo.energy.available:
                fuel_rate = minfo.energy.rateOfConsumption
            else:
                fuel_rate = self.unit_fuel(minfo.fuel.rateOfConsumption)
            self.update_consbar(self.bar_consbar, fuel_rate)

    # GUI update methods
    def update_gauge(self, target, rpm, gear, speed):
        """Gauge bar"""
        gauge_state = rpm + gear + speed
        if target.last != gauge_state:
            target.last = gauge_state
            color_index = self.color_rpm(rpm, gear, speed)
            target.update_input(
                GEAR_SEQUENCE(gear, "N"),
                self.unit_speed(speed),
                color_index,
                self.gauge_color[color_index],
            )

    def update_rpmbar(self, target, data):
        """RPM bar"""
        if target.last != data:
            target.last = data
            rpm_offset = data - self.rpm_safe
            if self.rpm_range > 0 <= rpm_offset:  # show only above offset
                rpm_percent = rpm_offset / self.rpm_range
            else:
                rpm_percent = 0
            if target.show_reading:
                target.text = f"{data:.{self.decimals_rpm}f}"
            target.update_input(rpm_percent)

    def update_battbar(self, target, data, state):
        """Battery bar"""
        available = state > 0  # available check only
        if target.state != available:
            target.state = available
            # Hide if electric motor unavailable
            target.setHidden(not available)
        charge = state + data  # add state to finalize last change
        if target.last != charge:
            target.last = charge
            if state == 3:
                color_index = 1
            elif data >= self.wcfg["high_battery_threshold"]:
                color_index = 3
            elif data <= self.wcfg["low_battery_threshold"]:
                color_index = 2
            else:
                color_index = 0
            if target.show_reading:
                target.text = f"{data:.{self.decimals_batt}f}"
            target.input_color = self.battbar_color[color_index]
            target.update_input(data * 0.01)

    def update_consbar(self, target, data):
        """Consumption bar"""
        if target.last != data:
            target.last = data
            # Filter out fluctuation & calculate average max rate
            self.ema_fuel_rate = self.calc_ema_fuel_rate(self.ema_fuel_rate, data)
            if self.max_fuel_rate < self.ema_fuel_rate:
                self.max_fuel_rate = self.ema_fuel_rate
            if target.show_reading:
                target.text = f"{data:.{self.decimals_cons}f}"
            rate = data / self.max_fuel_rate if self.max_fuel_rate else 0
            target.input_color = self.consbar_color[rate >= self.wcfg["high_consumption_threshold"]]
            target.update_input(rate ** self.cons_exp)

    def update_limiter(self, target, data):
        """Limiter"""
        if target.last != data:
            target.last = data
            target.setHidden(not data)

    # Additional methods
    def update_pedals(self):
        """Update embedded pedal and force feedback indicators."""
        cfg = self.pedal_cfg
        if cfg["show_throttle"]:
            raw = api.read.inputs.throttle_raw()
            filtered = api.read.inputs.throttle() if cfg["show_throttle_filtered"] else raw
            self.update_pedal("throttle", raw, filtered)
        if cfg["show_brake"]:
            raw = api.read.inputs.brake_raw()
            if cfg["show_brake_filtered"]:
                filtered = (
                    self.filtered_brake_pressure(api.read.brake.pressure())
                    if cfg["show_brake_pressure"] else api.read.inputs.brake()
                )
            else:
                filtered = raw
            self.update_pedal("brake", raw, filtered)
        if cfg["show_clutch"]:
            raw = api.read.inputs.clutch_raw()
            filtered = api.read.inputs.clutch() if cfg["show_clutch_filtered"] else raw
            self.update_pedal("clutch", raw, filtered)
        if cfg["show_ffb_meter"]:
            value = abs(api.read.inputs.force_feedback())
            self.update_pedal("ffb", value, value)

    def update_pedal(self, name, raw, filtered):
        """Update one embedded pedal indicator."""
        self.dashboard.set_pedal(name, raw, filtered)

    def filtered_brake_pressure(self, values):
        """Normalize brake pressure for the embedded brake indicator."""
        brake_pressure = sum(values)
        self.max_brake_pres = max(self.max_brake_pres, brake_pressure)
        return brake_pressure / self.max_brake_pres

    @staticmethod
    def set_pedal_size_from_config(config, font_m):
        """Compute pedal widget geometry from its existing settings."""
        gap = max(int(config["inner_gap"]), 0)
        length = max(int(config["bar_length"]), 10)
        extend = max(int(config["maximum_indicator_height"]), 0) + gap
        raw_width = max(int(config["bar_width_unfiltered"]), 1)
        filtered_width = max(int(config["bar_width_filtered"]), 1)
        total_width = raw_width + filtered_width
        reading_offset = length * (config["readings_offset"] - 0.5)
        if config["enable_horizontal_style"]:
            size = (0, 0, length, total_width)
            raw = (0, 0, length, raw_width)
            filtered = (0, raw_width, length, filtered_width)
            maximum = (length + gap, 0, extend - gap, total_width)
            reading = (reading_offset, font_m.voffset, length, total_width)
        else:
            size = (0, 0, total_width, length + extend)
            raw = (0, 0, raw_width, length + extend)
            filtered = (raw_width, 0, filtered_width, length + extend)
            maximum = (0, 0, total_width, extend - gap)
            reading = (0, reading_offset + font_m.voffset, total_width, length + extend)
        return length, extend, size, raw, filtered, maximum, reading

    def color_rpm(self, rpm, gear, speed):
        """RPM indicator color"""
        self.flicker = not self.flicker
        if (self.wcfg["show_rpm_flickering_above_critical"] and
            self.flicker and
            gear < self.gear_max and
            rpm >= self.rpm_crit):
            return -4
        if (not gear and
            speed > self.wcfg["neutral_warning_speed_threshold"] and
            self.shifting_timer >= self.wcfg["neutral_warning_time_threshold"]
            ) or rpm > self.rpm_max:
            return 3
        if rpm >= self.rpm_red:
            return 2
        if rpm >= self.rpm_safe:
            return 1
        return 0

    def set_gauge_size(self, font_m, font_scale_speed):
        """Set gauge size"""
        inner_gap = self.wcfg["inner_gap"]
        padx = round(font_m.width * self.wcfg["bar_padding_horizontal"])
        pady = round(font_m.capital * self.wcfg["bar_padding_vertical"])
        limiter_width = (
            font_m.width * len(self.wcfg["speed_limiter_text"])
            + round(font_m.width * self.wcfg["speed_limiter_padding_horizontal"]) * 2)

        gear_width = font_m.width + padx * 2
        gear_height = font_m.capital + pady * 2
        speed_width = round(font_m.width * 3 * font_scale_speed) + padx * 2
        speed_height = round(font_m.capital * font_scale_speed) + pady * 2

        if self.wcfg["show_speed_below_gear"]:
            gauge_width = gear_width
            gauge_height = gear_height + (inner_gap + speed_height) * self.wcfg["show_speed"]
            speed_size = (0, gear_height + inner_gap + font_m.voffset, gear_width, speed_height)

        else:
            gauge_width = gear_width + (inner_gap + speed_width) * self.wcfg["show_speed"]
            gauge_height = gear_height
            speed_size = (gear_width + inner_gap, font_m.voffset, speed_width, gear_height)
        gear_size = (0, font_m.voffset, gear_width, gear_height)
        return limiter_width, gauge_width, gauge_height, gear_size, speed_size
