import sys, math, os, ctypes
from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QShortcut
from PyQt5.QtCore import Qt, QPointF, QRectF, QEvent, QSize, QTimer
from PyQt5.QtGui import (
    QPainter,
    QConicalGradient,
    QColor,
    QFont,
    QPainterPath,
    QPixmap,
    QPalette,
    QBrush,
    QPen,
    QIcon,
)

# ---------- Knob settings ----------
DEGREES_PER_TICK = 8
CLOCKWISE_IS_UP = True
MIN_COUNT = 0
MAX_COUNT = 100
KNOB_RADIUS = 250  # Active area radius in pixels



# ---------- Resource resolver (works in dev and PyInstaller onefile) ----------
def resource_path(relative_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


# ---------- Background image (place file next to this script / in the bundle) ----------
BACKGROUND_IMAGE = resource_path("FORTEC-Integrated_BG_4k.png")


def normalize_deg(d):
    if d > 180:
        d -= 360
    elif d < -180:
        d += 360
    return d


def dist(a: QPointF, b: QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())


class GradientRingWidget(QWidget):
    """
    Draws a conical gradient ring (0..100). The widget background is transparent
    so the main window's background image shows through.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0  # 0..100
        self.setMinimumSize(280, 280)

        # Transparent background so the window's image is visible behind this widget
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        # Optional fixed-center support
        self._use_fixed_center = False
        self._fixed_cx = None
        self._fixed_cy = None

        # Per-widget drawing-center offsets (in pixels)
        self.center_dx = 0.0
        self.center_dy = 0.0

    def set_center_offset(self, dx: float, dy: float):
        """Shift the ring's drawing center by (dx, dy) pixels inside this widget."""
        self.center_dx = float(dx)
        self.center_dy = float(dy)
        self.update()

    def sizeHint(self):
        return QSize(360, 360)

    # ----- Fixed center API -----
    def set_fixed_center(self, x: float, y: float):
        self._use_fixed_center = True
        self._fixed_cx = float(x)
        self._fixed_cy = float(y)
        self.update()

    def clear_fixed_center(self):
        self._use_fixed_center = False
        self._fixed_cx = None
        self._fixed_cy = None
        self.update()

    def lock_center_to_current(self):
        w, h = self.width(), self.height()
        self.set_fixed_center(w / 2.0, h / 2.0)

    # ----- Value API -----
    def setValue(self, v: int):
        v = max(0, min(100, int(v)))
        if v != self._value:
            self._value = v
            self.update()

    def value(self) -> int:
        return self._value

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # Choose center: fixed if set, else live center
        if (
            self._use_fixed_center
            and self._fixed_cx is not None
            and self._fixed_cy is not None
        ):
            cx, cy = self._fixed_cx, self._fixed_cy
        else:
            cx, cy = w / 2.0, h / 2.0

        # Apply per-widget center offset (so donut + text move together)
        cx += self.center_dx
        cy += self.center_dy

        # Ring size
        R_outer = min(w, h) * 0.25
        R_inner = R_outer * 0.50  # keep it a donut (not a pie)

        # Geometry rects
        rect_outer = QRectF(cx - R_outer, cy - R_outer, 2 * R_outer, 2 * R_outer)
        rect_inner = QRectF(cx - R_inner, cy - R_inner, 2 * R_inner, 2 * R_inner)

        # Conical gradient (top = -90°)
        gradient = QConicalGradient(QPointF(cx, cy), -90)
        c0 = QColor(220, 30, 10)  # Red
        c1 = QColor(255, 165, 0)  # Orange
        c2 = QColor(255, 220, 0)  # Yellow
        c3 = QColor(0, 200, 0)  # Green
        gradient.setColorAt(0.0, c0)
        gradient.setColorAt(0.33, c1)
        gradient.setColorAt(0.66, c2)
        gradient.setColorAt(1.0, c3)

        # Visible donut sector (CLOCKWISE)
        visible_angle = 360.0 * (self._value / 100.0)
        start_deg = -90.0  # top (12 o'clock)

        sector = QPainterPath()
        sector.moveTo(QPointF(cx, cy))
        sector.arcMoveTo(rect_outer, start_deg)
        sector.arcTo(rect_outer, start_deg, -visible_angle)  # negative = clockwise
        end_deg = start_deg - visible_angle
        # Close back using inner arc
        sector.lineTo(self._point_on_circle(cx, cy, 0, end_deg))
        sector.arcTo(rect_inner, end_deg, +visible_angle)  # CCW inner arc back to start
        sector.closeSubpath()

        # -------- 3D ENHANCEMENTS (visual only) --------

        # 1) Soft drop shadow behind the sector
        if visible_angle > 0.5:
            shadow = QPainterPath(sector)
            shadow.translate(4, 6)  # subtle offset
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 90))
            painter.drawPath(shadow)

        # 2) Base fill with your conical gradient
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(sector)

        # 3) Beveled outer rim (dark stroke + slight inner highlight)
        painter.setBrush(Qt.NoBrush)
        # dark outer rim
        painter.setPen(
            QPen(QColor(0, 0, 0, 100), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        )
        painter.drawArc(rect_outer, int(start_deg * 16), int(-visible_angle * 16))
        # inner highlight (slightly inset)
        inset = 4
        rect_inset = QRectF(rect_outer.adjusted(inset, inset, -inset, -inset))
        painter.setPen(
            QPen(QColor(255, 255, 255, 110), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        )
        painter.drawArc(rect_inset, int(start_deg * 16), int(-visible_angle * 16))

        # 4) Specular shine clipped to the sector
        painter.save()
        painter.setClipPath(sector)

        # 8-stop specular shine (white with fading alpha)
        shine = QConicalGradient(QPointF(cx, cy), -90)
        shine.setColorAt(0.00, QColor(255, 255, 255, 80))
        shine.setColorAt(0.08, QColor(255, 255, 255, 64))
        shine.setColorAt(0.16, QColor(255, 255, 255, 48))
        shine.setColorAt(0.24, QColor(255, 255, 255, 32))
        shine.setColorAt(0.32, QColor(255, 255, 255, 20))
        shine.setColorAt(0.40, QColor(255, 255, 255, 10))
        shine.setColorAt(0.70, QColor(255, 255, 255, 0))
        shine.setColorAt(1.00, QColor(255, 255, 255, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(shine)
        painter.drawEllipse(rect_outer)
        painter.restore()

        # ---- White arrow: fixed size, hidden inside inner radius, invisible at 0 ----
        if self._value > 0:
            # Angle: start at south (90°) and rotate CLOCKWISE with visible_angle
            theta_deg = start_deg + 180.0 + visible_angle
            theta = math.radians(theta_deg)
            dirx, diry = math.cos(theta), math.sin(theta)

            # Fixed size (relative to R_outer)
            L_max_frac = 1.0  # total arrow length (center -> tip)
            head_len_frac = 0.12  # head length
            head_base_frac = 0.06  # half base width of head
            shaft_width_frac = 0.04  # shaft stroke width

            L = R_outer * L_max_frac
            head_len = R_outer * head_len_frac
            half_base = R_outer * head_base_frac
            shaft_w = max(2.0, R_outer * shaft_width_frac)

            # Start just outside the inner radius (hide inside hole)
            inner_gap = max(2.0, R_outer * 0.02)
            r_start = R_inner + inner_gap

            base_len = max(r_start, L - head_len)

            # Points
            sx, sy = cx + r_start * dirx, cy + r_start * diry
            bx, by = cx + base_len * dirx, cy + base_len * diry
            tx, ty = cx + L * dirx, cy + L * diry

            # Perpendicular for head base
            perpx, perpy = -diry, dirx
            lx, ly = bx + perpx * half_base, by + perpy * half_base
            rx, ry = bx - perpx * half_base, by - perpy * half_base

            # Draw shaft
            painter.setPen(
                QPen(
                    QColor(255, 255, 255, 220),
                    shaft_w,
                    Qt.SolidLine,
                    Qt.RoundCap,
                    Qt.RoundJoin,
                )
            )
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(QPointF(sx, sy), QPointF(bx, by))

            # Draw head (filled triangle)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 230))
            head = QPainterPath()
            head.moveTo(QPointF(tx, ty))
            head.lineTo(QPointF(lx, ly))
            head.lineTo(QPointF(rx, ry))
            head.closeSubpath()
            painter.drawPath(head)

        # ===== TEXT COLOR BY VALUE BUCKETS (8 stops: green -> red) =====
        v = self._value
        if v == 0:
            text_color = QColor(0, 0, 0)
        elif v <= 12:
            text_color = QColor(0, 200, 0)  # Green
        elif v <= 25:
            text_color = QColor(80, 210, 0)  # Yellow-Green 1
        elif v <= 37:
            text_color = QColor(150, 220, 0)  # Yellow-Green 2
        elif v <= 50:
            text_color = QColor(220, 220, 0)  # Yellow
        elif v <= 62:
            text_color = QColor(255, 200, 0)  # Amber
        elif v <= 75:
            text_color = QColor(255, 165, 0)  # Orange
        elif v <= 87:
            text_color = QColor(255, 100, 0)  # Orange-Red
        else:
            text_color = QColor(220, 30, 10)  # Red

        # Value text
        painter.setPen(text_color)
        font = QFont()
        font.setPointSize(int(min(w, h) * 0.015))
        font.setBold(True)
        painter.setFont(font)
        text = f"{self._value}"
        fm = painter.fontMetrics()
        painter.drawText(
            QRectF(
                cx - R_inner, cy - 0.6 * fm.height(), 2 * R_inner, 0.9 * fm.height()
            ),
            Qt.AlignCenter,
            text,
        )

        # # ================= DEBUG: EFFECTIVE KNOB AREA =================
        # # This shows the interaction radius (KNOB_RADIUS)
        # painter.setPen(QPen(QColor(255, 0, 0, 120), 2, Qt.DashLine))
        # painter.setBrush(Qt.NoBrush)

        # painter.drawEllipse(QPointF(cx, cy), KNOB_RADIUS, KNOB_RADIUS)
        # # ==============================================================

    @staticmethod
    def _point_on_circle(cx, cy, r, deg):
        rad = math.radians(deg)
        return QPointF(cx + r * math.cos(rad), cy + r * math.sin(rad))


class DualKnobRings(QWidget):
    """
    Two interactive knob zones (left/right). Each knob controls a ring (0..100).
    Background image is applied to THIS widget via palette (like your reference code).
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dual Knob Rings")
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.setMouseTracking(True)
        # Close the app when Escape is pressed
        self._esc = QShortcut(Qt.Key_Escape, self)
        self._esc.activated.connect(QApplication.quit)

        # --- Load and set background (reference-style) ---
        self._bg_pixmap = QPixmap(BACKGROUND_IMAGE.replace("\\", "/"))
        if not self._bg_pixmap.isNull():
            pal = self.palette()
            pal.setBrush(
                QPalette.Window,
                QBrush(
                    self._bg_pixmap.scaled(
                        self.size(),
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation,
                    )
                ),
            )
            self.setPalette(pal)
            self.setAutoFillBackground(True)
        else:
            print(f"Could not load image: {BACKGROUND_IMAGE}")

        # Centers & counters
        self.center_left = QPointF(0, 0)
        self.center_right = QPointF(0, 0)
        self.last_angle_left = None
        self.last_angle_right = None
        self.accum_left = 0.0
        self.accum_right = 0.0
        self.value_left = 0
        self.value_right = 0

        # Layout with two transparent ring widgets on top of the background
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(30)

        self.ring_left = GradientRingWidget()
        self.ring_right = GradientRingWidget()
        layout.addWidget(self.ring_left, 1)
        layout.addWidget(self.ring_right, 1)

        # Lock each ring's center after first layout (optional)
        QTimer.singleShot(0, self._lock_centers_once)

    def _lock_centers_once(self):
        self.ring_left.lock_center_to_current()
        self.ring_right.lock_center_to_current()

    def resizeEvent(self, e):
        GLOBAL_OFFSET_X = -250    # pixels
        GLOBAL_OFFSET_Y = 0    # pixels

        # Rescale background image when window size changes (reference-style)
        if not self._bg_pixmap.isNull():
            pal = self.palette()
            pal.setBrush(
                QPalette.Window,
                QBrush(
                    self._bg_pixmap.scaled(
                        self.size(),
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation,
                    )
                ),
            )
            self.setPalette(pal)

        # Update live centers for interaction (if you use them)
        w, h = self.width(), self.height()
        dpi_x = self.logicalDpiX()  # screen DPI (horizontal)
        shift_px = (3.0 / 2.54) * dpi_x  # 2 cm -> pixels

        # Move the knob interaction zones
        self.center_left = QPointF(w * 0.25 + GLOBAL_OFFSET_X, h * 0.50 + GLOBAL_OFFSET_Y)  # left knob 2 cm left
        self.center_right = QPointF(
            w * 0.75 - GLOBAL_OFFSET_X, h * 0.50 + GLOBAL_OFFSET_Y
        )  # right knob 2 cm right

        # Move the donut + text drawing centers by the same amount
        self.ring_left.set_center_offset(GLOBAL_OFFSET_X, GLOBAL_OFFSET_Y)
        self.ring_right.set_center_offset(-GLOBAL_OFFSET_X, GLOBAL_OFFSET_Y) 

        super().resizeEvent(e)

    def angle_from(self, p: QPointF, c: QPointF) -> float:
        return math.degrees(math.atan2(p.y() - c.y(), p.x() - c.x()))

    def _apply_delta(self, is_left: bool, diff_deg: float):
        sign = 1 if CLOCKWISE_IS_UP else -1
        diff_deg *= sign

        if is_left:
            self.accum_left += diff_deg
            while self.accum_left >= DEGREES_PER_TICK:
                if self.value_left < MAX_COUNT:
                    self.value_left += 1
                self.accum_left -= DEGREES_PER_TICK
            while self.accum_left <= -DEGREES_PER_TICK:
                if self.value_left > MIN_COUNT:
                    self.value_left -= 1
                self.accum_left += DEGREES_PER_TICK
            self.ring_left.setValue(self.value_left)
        else:
            self.accum_right += diff_deg
            while self.accum_right >= DEGREES_PER_TICK:
                if self.value_right < MAX_COUNT:
                    self.value_right += 1
                self.accum_right -= DEGREES_PER_TICK
            while self.accum_right <= -DEGREES_PER_TICK:
                if self.value_right > MIN_COUNT:
                    self.value_right -= 1
                self.accum_right += DEGREES_PER_TICK
            self.ring_right.setValue(self.value_right)

    def event(self, ev):
        if ev.type() in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd):
            pts = ev.touchPoints()
            if pts:
                self._process_point(pts[0].pos())
            ev.accept()
            return True
        return super().event(ev)

    def mouseMoveEvent(self, ev):
        self._process_point(ev.pos())

    def _process_point(self, p: QPointF):
        if dist(p, self.center_left) <= KNOB_RADIUS:
            angle = self.angle_from(p, self.center_left)
            if self.last_angle_left is not None:
                diff = normalize_deg(angle - self.last_angle_left)
                if abs(diff) >= 0.2:
                    self._apply_delta(True, diff)
            self.last_angle_left = angle

        elif dist(p, self.center_right) <= KNOB_RADIUS:
            angle = self.angle_from(p, self.center_right)
            if self.last_angle_right is not None:
                diff = normalize_deg(angle - self.last_angle_right)
                if abs(diff) >= 0.2:
                    self._apply_delta(False, diff)
            self.last_angle_right = angle
        else:
            self.last_angle_left = None
            self.last_angle_right = None


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # (Optional but recommended for Windows taskbar pinning consistency)
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Fortec.DualKnobRings"
        )
    except Exception:
        pass

    # Set the icon for the app and the main window AFTER QApplication exists
    icon_path = resource_path("app_icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    w = DualKnobRings()
    w.setWindowIcon(QIcon(icon_path))  # redundant but harmless
    w.showFullScreen()
    sys.exit(app.exec_())
