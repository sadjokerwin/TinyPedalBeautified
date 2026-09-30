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

"""Simple design controls for the redesigned telemetry widgets."""

import time

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ..design_options import STANDINGS_COLUMN_OPTIONS
from ..setting import cfg
from ._common import BaseDialog, UIScaler, singleton_dialog


@singleton_dialog("redesigned_widget_design")
class RedesignedWidgetConfig(BaseDialog):
    """Small, focused design dialog for new-style widget controls."""

    def __init__(self, parent, widget_name, reload_func):
        super().__init__(parent)
        self.widget_name = widget_name
        self.setting = cfg.user.setting[widget_name]
        self.reload_func = reload_func
        self.set_config_title(f"{widget_name.replace('_', ' ').title()} Design", cfg.filename.setting)

        self._font_size = QSpinBox(self)
        self._font_size.setRange(1, 150)
        self._font_size.setValue(int(self.setting["font_size"]))
        font_group = QGroupBox("Text size", self)
        font_layout = QFormLayout(font_group)
        font_layout.addRow(QLabel("Main font size"), self._font_size)
        if widget_name == "gear":
            font_layout.addRow(QLabel("Adjusts the gear, speed, and small readouts together."))

        layout_main = QVBoxLayout()
        layout_main.addWidget(font_group)
        self._column_checks = {}
        if widget_name == "standings":
            columns_group = QGroupBox("Visible columns", self)
            columns_layout = QGridLayout(columns_group)
            for index, (_, label, setting_key) in enumerate(STANDINGS_COLUMN_OPTIONS):
                checkbox = QCheckBox(label, columns_group)
                checkbox.setChecked(bool(self.setting[setting_key]))
                row, column = divmod(index, 2)
                columns_layout.addWidget(checkbox, row, column)
                self._column_checks[setting_key] = checkbox
            layout_main.addWidget(columns_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Apply | QDialogButtonBox.Save | QDialogButtonBox.Cancel, self
        )
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.applying)
        buttons.button(QDialogButtonBox.Save).clicked.connect(self.saving)
        buttons.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)
        layout_main.addWidget(buttons, alignment=Qt.AlignRight)
        layout_main.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.setLayout(layout_main)
        self.setMinimumWidth(UIScaler.size(25))

    def applying(self):
        """Save these design choices and reload the widget."""
        original_font_size = max(int(self.setting["font_size"]), 1)
        new_font_size = self._font_size.value()
        if self.widget_name == "gear":
            ratio = new_font_size / original_font_size
            for key, value in tuple(self.setting.items()):
                if key.startswith("font_size_"):
                    self.setting[key] = max(round(value * ratio), 1)
        self.setting["font_size"] = new_font_size

        for setting_key, checkbox in self._column_checks.items():
            self.setting[setting_key] = checkbox.isChecked()
        if self.widget_name == "standings" and not any(
            checkbox.isChecked() for checkbox in self._column_checks.values()
        ):
            position_setting = self._column_checks["show_position"]
            position_setting.setChecked(True)
            self.setting["show_position"] = True

        cfg.save(0)
        while cfg.is_saving:
            time.sleep(0.01)
        self.reload_func()

    def saving(self):
        """Save choices and close."""
        self.applying()
        self.accept()
