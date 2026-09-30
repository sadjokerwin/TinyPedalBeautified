"""Compact modern card shared by fuel and virtual-energy widgets."""

from PySide2.QtCore import QRectF, Qt
from PySide2.QtGui import QColor, QFont, QPainter, QPen
from PySide2.QtWidgets import QWidget


class ConsumptionStrategyCard(QWidget):
    """Show available supply, consumption pace, and stint extension targets."""

    def __init__(self, parent, kind, font_name, font_size):
        super().__init__(parent)
        self.kind = kind
        self.base = max(int(font_size), 12)
        self.family = font_name
        self.accent = QColor("#F6B84A" if kind == "fuel" else "#48D6C4")
        self.values = {}
        self.setFixedSize(round(self.base * 28), round(self.base * 11.8))

    def set_values(self, **values):
        if values != self.values:
            self.values = values
            self.update()

    def _font(self, pixels, weight=QFont.DemiBold):
        font = QFont(self.family)
        font.setPixelSize(max(round(pixels), 8))
        font.setWeight(weight)
        return font

    def _label(self, painter, rect, text):
        painter.setPen(QColor("#8FA1AF"))
        painter.setFont(self._font(self.base * .60, QFont.DemiBold))
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, text)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        scale = self.base
        w, h = self.width(), self.height()
        pad = scale * .82
        right = w - pad

        panel = QRectF(.5, .5, w - 1, h - 1)
        p.setPen(QPen(QColor("#354654"), 1))
        p.setBrush(QColor("#F0131C25"))
        p.drawRoundedRect(panel, scale * .72, scale * .72)
        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        p.drawRoundedRect(QRectF(pad, scale * .55, scale * 2.8, scale * .18), scale * .09, scale * .09)

        title = "FUEL STRATEGY" if self.kind == "fuel" else "VIRTUAL ENERGY"
        p.setPen(QColor("#ECF3F7"))
        p.setFont(self._font(scale * .92, QFont.Bold))
        p.drawText(QRectF(pad, scale * .82, scale * 18, scale * 1.0), Qt.AlignVCenter, title)

        content_top = scale * 1.9
        footer_top = h - scale * 2.55
        hero_w = w * .34
        divider_x = pad + hero_w
        p.setPen(QPen(QColor("#34434F"), 1))
        p.drawLine(int(divider_x), int(content_top), int(divider_x), int(footer_top - scale * .30))

        muted = QColor("#8FA1AF")
        primary = QColor("#EDF4F8")
        finish_label = (
            self.values.get("finish_fuel_label", "FUEL TO GO")
            if self.kind == "fuel" else self.values.get("finish_energy_label", "+1 LAP TARGET")
        )
        finish_value = (
            self.values.get("finish_fuel_text", "—")
            if self.kind == "fuel" else self.values.get(
                "finish_energy_text", self.values.get("extension_target_text", "—")
            )
        )
        # Left column: available amount, then laps remaining at the current average.
        # self._label(p, QRectF(pad, content_top, hero_w - scale * .55, scale * .72), "AVAILABLE")
        p.setPen(self.accent)
        p.setFont(self._font(scale * 1.72, QFont.Bold))
        p.drawText(QRectF(pad, content_top + scale * .62, hero_w - scale * .45, scale * 2.0),
                   Qt.AlignVCenter | Qt.AlignLeft, self.values.get("current_text", "—"))
        range_top = content_top + scale * 4.15
        p.setPen(QPen(QColor("#34434F"), 1))
        p.drawLine(int(pad), int(range_top - scale * .18), int(divider_x - scale * .55), int(range_top - scale * .18))
        # self._label(p, QRectF(pad, range_top, hero_w - scale * .55, scale * .75), "LAPS TO GO")
        p.setPen(primary)
        p.setFont(self._font(scale * 1.72, QFont.Bold))
        p.drawText(QRectF(pad, range_top + scale * .65, hero_w - scale * .5, scale * 1.8),
                   Qt.AlignVCenter | Qt.AlignLeft, self.values.get("range_text", "—"))

        # Right column: four metrics in an evenly filled 2 by 2 grid.
        stats_left = divider_x + scale * .42
        stats_w = right - stats_left
        gap_x = scale * .28
        gap_y = scale * .24
        cell_w = (stats_w - gap_x) / 2
        cell_h = (footer_top - content_top - gap_y) / 2
        stats = (
            ("AVG / LAP", self.values.get("average_text", "—"), self.accent, 0, 0),
            ("LAST LAP", self.values.get("last_lap_text", "—"), primary, 1, 0),
            ("Current lap delta", self.values.get("delta_text", "—"), self.values.get("delta_color", muted), 0, 1),
            (finish_label, finish_value, self.accent, 1, 1),
        )
        for label, value, color, col, row in stats:
            x = stats_left + col * (cell_w + gap_x)
            y = content_top + row * (cell_h + gap_y)
            rect = QRectF(x, y, cell_w, cell_h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#171F28"))
            p.drawRoundedRect(rect, scale * .34, scale * .34)
            inset = scale * .55
            self._label(p, QRectF(rect.left() + inset, rect.top() + scale * .38, cell_w - inset, scale * .86), label)
            p.setPen(color)
            p.setFont(self._font(scale * 1.28, QFont.DemiBold))
            p.drawText(QRectF(rect.left() + inset, rect.top() + scale * 1.28, cell_w - inset * 1.35,
                               cell_h - scale * 1.55), Qt.AlignVCenter | Qt.AlignLeft, value)

        # Bottom chips explain the target average consumption for each extra lap.
        p.setPen(QPen(QColor("#34434F"), 1))
        p.drawLine(int(pad), int(footer_top), int(right), int(footer_top))
        self._label(p, QRectF(pad, footer_top + scale * .15, right - pad, scale * .62),
                    "Alternate strategies")
        targets = self.values.get("targets", ())
        if targets:
            gap = scale * .28
            chip_w = (right - pad - gap * (len(targets) - 1)) / len(targets)
            chip_y = footer_top + scale * .82
            chip_h = scale * 1.48
            for index, (label, value) in enumerate(targets):
                chip = QRectF(pad + index * (chip_w + gap), chip_y, chip_w, chip_h)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#202A34"))
                p.drawRoundedRect(chip, scale * .36, scale * .36)
                p.setPen(muted)
                p.setFont(self._font(scale * .72, QFont.DemiBold))
                p.drawText(QRectF(chip.left(), chip.top() + scale * .02, chip.width(), scale * .70),
                           Qt.AlignCenter, label)
                p.setPen(self.accent)
                p.setFont(self._font(scale * .64, QFont.DemiBold))
                p.drawText(QRectF(chip.left(), chip.top() + scale * .72, chip.width(), scale * .72),
                           Qt.AlignCenter, value)
        else:
            p.setPen(muted)
            p.setFont(self._font(scale * .58, QFont.Medium))
            p.drawText(QRectF(pad, footer_top + scale * .82, right - pad, scale * 1.25),
                       Qt.AlignVCenter | Qt.AlignLeft, "No +1 / +2 / +3 lap option fits within a 15% reduction")
