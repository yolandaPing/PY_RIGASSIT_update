# -*- coding: utf-8 -*-

# .FileName:ui_openpipeline.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/6/30 20:37
# .Finish time:
from functools import partial
import os
from datetime import datetime

try:
    from ui_framework.core.qtCompat import *
    from ui_framework.widgets.widgets import Widgets
except Exception:
    from CommonUse.qtCompat import *
    from CommonUse.widgetsUse import Widgets

_widgets = Widgets()


_ICON_SIZE_SMALL = 14
_ICON_SIZE_NORMAL = 16
_ICON_SIZE_LARGE = 24
_BUTTON_MIN_HEIGHT = 28
_SMALL_BUTTON_MIN_HEIGHT = 24
_ICON_BUTTON_FIXED = 28

_ICONS_SELECT = ("aselect.png", "selectFrontFacingUV.png", "menuIconSelected.png")
_ICONS_SET = ("menuIconAdd.png", "setEdRemoveCmd.png")
_ICONS_ADD = ("add.png", "new.png", "fileNew.png")
_ICONS_DELETE = ("delete.png", "remove.png", "trash.png")
_ICONS_RENAME = ("rename.png", "edit.png", "pencil.png")
_ICONS_FOLDER = ("folder-open.png", "folder.png", "openFolder.png")
_ICONS_SAVE = ("save.png", "fileSave.png", "saveAs.png", "fileSaveAs.png")
_ICONS_PUBLISH = ("publish.png", "checkin.png", "checkMark.png", "save.png", "fileSave.png")

_FLOAT_BUTTON_STYLE_ICON = """
    QPushButton {
        background-color: rgba(0, 0, 0, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.28);
        border-radius: 16px;
    }
    QPushButton:hover {
        background-color: rgba(77, 208, 225, 0.95);
        border-color: rgba(255, 255, 255, 0.6);
    }
    QPushButton:pressed {
        background-color: rgba(0, 156, 199, 1.0);
    }
    QPushButton:disabled {
        background-color: rgba(0, 0, 0, 0.30);
        border-color: rgba(255, 255, 255, 0.12);
    }
"""

_FLOAT_BUTTON_STYLE_TEXT = """
    QPushButton {
        background-color: rgba(0, 0, 0, 0.55);
        color: #d0d6df;
        border: 1px solid rgba(255, 255, 255, 0.28);
        border-radius: 16px;
        font-weight: 700;
        font-size: 9px;
    }
    QPushButton:hover {
        background-color: rgba(77, 208, 225, 0.95);
        color: #000000;
    }
    QPushButton:pressed {
        background-color: rgba(0, 156, 199, 1.0);
        color: #000000;
    }
    QPushButton:disabled {
        background-color: rgba(0, 0, 0, 0.30);
        color: #666666;
        border-color: rgba(255, 255, 255, 0.12);
    }
"""


def _u(value):
    """Py2/Py3 安全转 unicode。"""
    if value is None:
        return u''
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except Exception:
            try:
                return value.decode('gbk')
            except Exception:
                return value.decode('utf-8', 'replace')
    if isinstance(value, str):
        return value
    try:
        return unicode(value)  # noqa: F821
    except Exception:
        return u'{}'.format(value)


def _load_maya_icon(*names):
    for name in names:
        for cand in (":" + name, name):
            pm = QtGui.QPixmap(cand)
            if not pm.isNull():
                return QtGui.QIcon(pm)
    return QtGui.QIcon()


def _set_maya_button_icon(button, names, size=_ICON_SIZE_SMALL):
    icon = _load_maya_icon(*names)
    if icon.isNull():
        return False
    button.setIcon(icon)
    button.setIconSize(QtCore.QSize(size, size))
    return True


def _make_snapshot_icon(kind="camera"):
    pix = QtGui.QPixmap(32, 32)
    pix.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pix)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    pen = QtGui.QPen(QtGui.QColor(245, 250, 255), 2.0)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)

    if kind == "region":
        painter.drawLine(6, 12, 6, 6)
        painter.drawLine(6, 6, 12, 6)
        painter.drawLine(20, 6, 26, 6)
        painter.drawLine(26, 6, 26, 12)
        painter.drawLine(6, 20, 6, 26)
        painter.drawLine(6, 26, 12, 26)
        painter.drawLine(20, 26, 26, 26)
        painter.drawLine(26, 20, 26, 26)
        painter.drawLine(11, 16, 21, 16)
        painter.drawLine(16, 11, 16, 21)
    else:
        painter.drawRoundedRect(QtCore.QRectF(4, 10, 24, 17), 3, 3)
        painter.drawRoundedRect(QtCore.QRectF(10, 7, 8, 4), 1, 1)
        painter.drawEllipse(QtCore.QRectF(11, 13, 10, 10))
        painter.drawEllipse(QtCore.QRectF(14, 16, 4, 4))
    painter.end()
    return QtGui.QIcon(pix)


def _create_text_button(text, property_name=None,
                        height=_BUTTON_MIN_HEIGHT, icons=None):
    btn = QtWidgets.QPushButton(_u(text))
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.setMinimumHeight(height)
    if property_name:
        btn.setProperty(property_name, True)
    if icons:
        _set_maya_button_icon(btn, icons, _ICON_SIZE_SMALL)
    return btn


def _create_icon_button(icon_name, tooltip, extra_props=None):
    btn = QtWidgets.QPushButton()
    btn.setIcon(QtGui.QIcon(icon_name))
    btn.setIconSize(QtCore.QSize(_ICON_SIZE_NORMAL, _ICON_SIZE_NORMAL))
    btn.setToolTip(_u(tooltip))
    btn.setProperty("class", "iconBtn")
    btn.setFixedSize(_ICON_BUTTON_FIXED, _ICON_BUTTON_FIXED)
    if extra_props:
        for k, v in extra_props.items():
            btn.setProperty(k, v)
    return btn


def _create_small_text_button(text, icons=None):
    btn = QtWidgets.QPushButton(_u(text))
    btn.setStyleSheet('font: bold 12px;')
    if icons:
        _set_maya_button_icon(btn, icons, _ICON_SIZE_SMALL)
    return btn


def _style_float_camera_button(btn, has_icon=True):
    btn.setFixedSize(32, 32)
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.setStyleSheet(
        _FLOAT_BUTTON_STYLE_ICON if has_icon else _FLOAT_BUTTON_STYLE_TEXT
    )


class AutoScalePixmapLabel(QtWidgets.QLabel):
    def __init__(self, parent=None):
        QtWidgets.QLabel.__init__(self, parent)
        self._source_pixmap = QtGui.QPixmap()
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

    def setPixmap(self, pixmap):
        if pixmap is None or pixmap.isNull():
            self._source_pixmap = QtGui.QPixmap()
            QtWidgets.QLabel.setPixmap(self, QtGui.QPixmap())
            return
        self._source_pixmap = QtGui.QPixmap(pixmap)
        self._update_scaled_pixmap()

    def clear(self):
        self._source_pixmap = QtGui.QPixmap()
        QtWidgets.QLabel.clear(self)

    def resizeEvent(self, event):
        QtWidgets.QLabel.resizeEvent(self, event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if self._source_pixmap.isNull():
            return
        size = self.contentsRect().size()
        if size.width() < 1 or size.height() < 1:
            return
        scaled = self._source_pixmap.scaled(
            size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
        )
        QtWidgets.QLabel.setPixmap(self, scaled)


class ScreenRegionSelector(QtWidgets.QWidget):
    region_selected = QtCore.Signal(QtCore.QRect)
    cancelled = QtCore.Signal()

    MASK_COLOR = QtGui.QColor(0, 0, 0, 120)
    BORDER_COLOR = QtGui.QColor(77, 208, 225)
    TEXT_COLOR = QtGui.QColor(255, 255, 255)
    TEXT_BG_COLOR = QtGui.QColor(0, 0, 0, 180)
    BORDER_WIDTH = 2
    TEXT_POINT_SIZE = 10
    MIN_REGION_SIZE = 10

    def __init__(self, screenshot, screen_geometry, parent=None):
        super(ScreenRegionSelector, self).__init__(parent)
        self._screenshot = screenshot
        self._screen_geometry = screen_geometry
        self._start = None
        self._current = None

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setCursor(QtCore.Qt.CrossCursor)
        self.setGeometry(screen_geometry)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        if not self._screenshot.isNull():
            painter.drawPixmap(self.rect(), self._screenshot)
        painter.fillRect(self.rect(), self.MASK_COLOR)

        if not (self._start and self._current):
            return

        rect = QtCore.QRect(self._start, self._current).normalized()
        self._draw_selected_region(painter, rect)
        self._draw_size_label(painter, rect)

    def _draw_selected_region(self, painter, rect):
        shot = self._screenshot
        if (shot.isNull()
                or self.width() <= 0 or self.height() <= 0
                or rect.width() <= 0 or rect.height() <= 0):
            return

        sx = int(rect.x() * shot.width() / self.width())
        sy = int(rect.y() * shot.height() / self.height())
        sw = max(1, int(rect.width() * shot.width() / self.width()))
        sh = max(1, int(rect.height() * shot.height() / self.height()))
        painter.drawPixmap(rect, shot, QtCore.QRect(sx, sy, sw, sh))

        painter.setPen(QtGui.QPen(self.BORDER_COLOR, self.BORDER_WIDTH))
        painter.drawRect(rect)

    def _draw_size_label(self, painter, rect):
        text = u"{} × {}".format(rect.width(), rect.height())
        painter.setPen(self.TEXT_COLOR)
        font = painter.font()
        font.setPointSize(self.TEXT_POINT_SIZE)
        font.setBold(True)
        painter.setFont(font)

        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(text).adjusted(-8, -3, 8, 3)
        text_rect.moveTopLeft(
            rect.topLeft() + QtCore.QPoint(0, -text_rect.height() - 4)
        )
        if text_rect.top() < 0:
            text_rect.moveTopLeft(rect.bottomLeft() + QtCore.QPoint(0, 4))

        painter.fillRect(text_rect, self.TEXT_BG_COLOR)
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, text)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._start = event.pos()
            self._current = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self._start:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton or not self._start:
            return

        rect = QtCore.QRect(self._start, event.pos()).normalized()
        self._start = None
        self._current = None
        self.update()

        if (rect.width() >= self.MIN_REGION_SIZE
                and rect.height() >= self.MIN_REGION_SIZE):
            global_rect = QtCore.QRect(
                self._screen_geometry.topLeft() + rect.topLeft(),
                rect.size()
            )
            self.region_selected.emit(global_rect)
        else:
            self.cancelled.emit()
        self.close()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.cancelled.emit()
            self.close()


def crop_region_from_screenshot(screenshot, screen_geometry, global_rect):
    if screenshot.isNull() or screen_geometry.width() <= 0 or screen_geometry.height() <= 0:
        return QtGui.QPixmap()

    w_ratio = screenshot.width() / float(screen_geometry.width())
    h_ratio = screenshot.height() / float(screen_geometry.height())

    local_x = global_rect.x() - screen_geometry.x()
    local_y = global_rect.y() - screen_geometry.y()

    crop_x = int(round(local_x * w_ratio))
    crop_y = int(round(local_y * h_ratio))
    crop_w = int(round(global_rect.width() * w_ratio))
    crop_h = int(round(global_rect.height() * h_ratio))

    crop_x = max(0, min(crop_x, screenshot.width() - 1))
    crop_y = max(0, min(crop_y, screenshot.height() - 1))
    crop_w = max(1, min(crop_w, screenshot.width() - crop_x))
    crop_h = max(1, min(crop_h, screenshot.height() - crop_y))

    return screenshot.copy(QtCore.QRect(crop_x, crop_y, crop_w, crop_h))


def _build_root_path_row(self, parent_layout):
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(6)

    path_card = QtWidgets.QFrame()
    path_card.setProperty("card", True)
    path_layout = QtWidgets.QHBoxLayout(path_card)
    path_layout.setContentsMargins(10, 4, 10, 4)
    path_layout.setSpacing(8)

    icon_label = QtWidgets.QLabel()
    try:
        icon_label.setPixmap(
            self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon).pixmap(16, 16)
        )
    except Exception:
        pass
    icon_label.setFixedWidth(_ICON_SIZE_NORMAL)
    icon_label.setAlignment(QtCore.Qt.AlignCenter)

    lbl_root = QtWidgets.QLabel(u'项目根路径:')
    self.root_path_label = QtWidgets.QLabel(u'未设置')
    self.root_path_label.setProperty("isText", True)
    self.root_path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    self.root_path_label.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
    )
    self.root_path_label.setMinimumWidth(200)

    path_layout.addWidget(icon_label)
    path_layout.addWidget(lbl_root)
    path_layout.addWidget(self.root_path_label, 1)
    row.addWidget(path_card, 1)

    btn_set_root = _create_text_button(u'[设置路径]', "cld_main", icons=_ICONS_SELECT)
    btn_set_root.clicked.connect(self.set_project_root_path)

    btn_check_root = _create_text_button(u'检查项目', "secondary")
    btn_check_root.clicked.connect(self.check_projects_in_root)

    btn_check_config = _create_text_button(u'检查配置', "secondary")
    btn_check_config.clicked.connect(self.check_config)

    row.addWidget(btn_set_root)
    row.addWidget(btn_check_root)
    row.addWidget(btn_check_config)
    parent_layout.addLayout(row)


def _build_project_row(self, parent_layout):
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(6)
    row.addSpacing(10)
    proj_icon = QtWidgets.QLabel()
    try:
        proj_icon.setPixmap(
            self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon).pixmap(16, 16)
        )
    except Exception:
        pass
    proj_icon.setFixedWidth(_ICON_SIZE_NORMAL)
    proj_icon.setAlignment(QtCore.Qt.AlignCenter)

    lbl = QtWidgets.QLabel(u'当前项目:')
    self.project_combo = QtWidgets.QComboBox()
    self.project_combo.setMinimumWidth(220)
    self.project_combo.setMinimumHeight(_BUTTON_MIN_HEIGHT)
    self.project_combo.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    self.project_combo.currentTextChanged.connect(self.on_project_changed)

    btn_new = _create_text_button(u'新建', "cld_main", icons=_ICONS_ADD)
    btn_new.clicked.connect(self.create_project_dialog)

    btn_open = _create_text_button(u'打开', "secondary", icons=_ICONS_FOLDER)
    btn_open.setToolTip(u"打开位置")
    btn_open.clicked.connect(self.open_existing_project)

    wbl = QtWidgets.QLabel(u'  > workshop:')
    self.version_format_combo = QtWidgets.QComboBox()
    self.version_format_combo.addItem(u" 旧版", "legacy")
    self.version_format_combo.addItem(u" 新版", "new")
    self.version_format_combo.setToolTip(
        u"选择 workshop 版本保存时的文件命名格式\n"
        u"旧版: asset_subtype_workshop_001.ma\n"
        u"新版: asset.subtype.v001.ma\n"
    )
    self.version_format_combo.setMinimumHeight(_BUTTON_MIN_HEIGHT)
    self.version_format_combo.currentIndexChanged.connect(self.on_version_format_changed)

    btn_refresh = _create_icon_button(":refresh.png", u"刷新项目列表", extra_props={"help": True})
    btn_refresh.clicked.connect(self.load_projects)

    btn_about = _create_icon_button(":help.png", u"帮助")
    btn_about.clicked.connect(about)

    row.addWidget(proj_icon)
    row.addWidget(lbl)
    row.addWidget(self.project_combo)
    row.addWidget(btn_new)
    row.addWidget(btn_open)
    row.addWidget(wbl)
    row.addWidget(self.version_format_combo)
    row.addStretch(1)
    row.addWidget(btn_refresh)
    row.addWidget(btn_about)
    parent_layout.addLayout(row)


def _build_left_panel(self):
    panel = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    layout.addWidget(_build_type_group(self))
    layout.addWidget(_build_asset_group(self))

    panel.setMinimumWidth(100)
    return panel


def _build_type_group(self):
    group = QtWidgets.QGroupBox(u"类型")
    row = QtWidgets.QHBoxLayout(group)
    row.setContentsMargins(4, 4, 4, 4)

    self.type_combo = QtWidgets.QComboBox()
    self.type_combo.currentTextChanged.connect(self.on_asset_type_changed)

    btn_addtype = QtWidgets.QPushButton('+')
    btn_addtype.setFixedSize(24, 24)
    btn_addtype.setStyleSheet(
        "font: bold 16px; {} color: green;".format(_widgets.button_bgc)
    )
    btn_addtype.clicked.connect(self.add_asset_type)

    btn_deltype = QtWidgets.QPushButton('-')
    btn_deltype.setFixedSize(24, 24)
    btn_deltype.setStyleSheet(
        "font: bold 16px; {} color: red;".format(_widgets.button_bgc)
    )
    btn_deltype.clicked.connect(self.delete_asset_type)

    btn_box = QtWidgets.QHBoxLayout()
    btn_box.setContentsMargins(0, 0, 0, 0)
    btn_box.setSpacing(0)
    btn_box.addWidget(btn_addtype)
    btn_box.addWidget(btn_deltype)

    row.addWidget(self.type_combo, 1)
    row.addLayout(btn_box)
    return group


def _build_asset_group(self):
    group = QtWidgets.QGroupBox(u"对象名称")
    layout = QtWidgets.QVBoxLayout(group)
    layout.setContentsMargins(4, 4, 4, 4)

    self.asset_sort_block = _widgets.create_radiogroup(
        "", [(" Name ", 1, None), (" Date ", 2, None)],
        default_id=1
    )
    self.asset_sort_block.idClicked.connect(self.on_asset_sort_changed)

    self.search_edit = QtWidgets.QLineEdit()
    self.search_edit.setPlaceholderText(u'搜索资产...')
    self.search_edit.textChanged.connect(self.filter_assets)

    self.asset_list = QtWidgets.QListWidget()
    self.asset_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.asset_list.setAlternatingRowColors(True)
    self.asset_list.itemClicked.connect(self.on_asset_clicked)
    self.asset_list.customContextMenuRequested.connect(self.show_asset_context_menu)

    layout.addWidget(self.asset_sort_block)
    layout.addWidget(self.search_edit)
    layout.addWidget(self.asset_list)

    btn_row = QtWidgets.QHBoxLayout()
    self.asset_count = _widgets.create_text("")

    self.btn_create_asset = _create_text_button(
        u'new', "cld_main",
        height=_SMALL_BUTTON_MIN_HEIGHT, icons=_ICONS_ADD
    )
    self.btn_create_asset.setToolTip(u"新建资产")
    self.btn_create_asset.setEnabled(False)
    self.btn_create_asset.clicked.connect(self.create_asset_dialog)

    self.btn_delete_asset = _create_text_button(
        u'del', "danger",
        height=_SMALL_BUTTON_MIN_HEIGHT, icons=_ICONS_DELETE
    )
    self.btn_delete_asset.setToolTip(u"删除选择的资产")
    self.btn_delete_asset.setEnabled(False)
    self.btn_delete_asset.setVisible(False)
    self.btn_delete_asset.clicked.connect(self.delete_asset_dialog)

    btn_row.addWidget(self.asset_count)
    btn_row.addWidget(self.btn_create_asset)
    btn_row.addWidget(self.btn_delete_asset)
    btn_row.addStretch()
    layout.addLayout(btn_row)
    return group


def _build_center_panel(self):
    panel = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)

    vsplitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
    vsplitter.addWidget(_build_subtype_frame(self))
    vsplitter.addWidget(_build_version_frame(self))
    vsplitter.setSizes([200, 600])

    layout.addWidget(vsplitter)
    panel.setMinimumWidth(150)
    return panel


def _build_subtype_frame(self):
    frame = QtWidgets.QGroupBox(u"任务")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(6)

    self.info_label = QtWidgets.QLabel(u'未选择资产')
    self.info_label.setWordWrap(True)
    self.info_label.setAlignment(QtCore.Qt.AlignLeft)
    self.info_label.setMaximumHeight(15)
    self.info_label.setStyleSheet('color: yellow; font-size: 12px;')
    layout.addWidget(self.info_label)

    self.subtype_list = QtWidgets.QListWidget()
    self.subtype_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.subtype_list.setAlternatingRowColors(True)
    self.subtype_list.itemClicked.connect(self.on_subtype_clicked)
    self.subtype_list.itemDoubleClicked.connect(self.on_subtype_double_clicked)
    self.subtype_list.customContextMenuRequested.connect(self.show_subtype_context_menu)
    layout.addWidget(self.subtype_list)

    btn_row = QtWidgets.QHBoxLayout()
    self.btn_add_sub = _create_small_text_button(u'new', _ICONS_ADD)
    self.btn_add_sub.setEnabled(False)
    self.btn_add_sub.clicked.connect(self.add_subtype_dialog)

    self.btn_rename_sub = _create_small_text_button(u'rename', _ICONS_RENAME)
    self.btn_rename_sub.setEnabled(False)
    self.btn_rename_sub.clicked.connect(self.rename_subtype)

    self.btn_del_sub = _create_small_text_button(u'delete', _ICONS_DELETE)
    self.btn_del_sub.setEnabled(False)
    self.btn_del_sub.clicked.connect(self.delete_subtype)

    btn_row.addWidget(self.btn_add_sub)
    btn_row.addWidget(self.btn_rename_sub)
    btn_row.addWidget(self.btn_del_sub)
    layout.addLayout(btn_row)
    return frame


def _build_version_frame(self):
    frame = QtWidgets.QGroupBox(u"版本")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(4, 4, 4, 4)

    title_row = QtWidgets.QHBoxLayout()
    title_row.addWidget(QtWidgets.QLabel(''))
    self.version_count_text = _widgets.create_text('')
    self.version_count_text.setWordWrap(True)
    title_row.addWidget(self.version_count_text)
    layout.addLayout(title_row)

    self.version_list = QtWidgets.QListWidget()
    self.version_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.version_list.setAlternatingRowColors(True)
    self.version_list.itemDoubleClicked.connect(self.open_selected_version)
    self.version_list.customContextMenuRequested.connect(self.show_version_context_menu)
    layout.addWidget(self.version_list)

    btn_row = QtWidgets.QHBoxLayout()

    self.btn_save_new_version = _create_text_button(
        u'save Workshop', height=_SMALL_BUTTON_MIN_HEIGHT, icons=_ICONS_SAVE
    )
    self.btn_save_new_version.setProperty("main", True)
    self.btn_save_new_version.setStyleSheet("color: gray;")
    self.btn_save_new_version.setEnabled(False)
    self.btn_save_new_version.clicked.connect(self.save_new_version)

    self.btn_set_master = _create_text_button(
        u'save Master', height=_SMALL_BUTTON_MIN_HEIGHT, icons=_ICONS_PUBLISH
    )
    self.btn_set_master.setProperty("main", True)
    self.btn_set_master.setStyleSheet("color: gray;")
    self.btn_set_master.setEnabled(False)
    self.btn_set_master.clicked.connect(self.save_new_master)

    save_btn_about = QtWidgets.QPushButton()
    save_btn_about.setIcon(QtGui.QIcon(":help.png"))
    save_btn_about.setIconSize(QtCore.QSize(_ICON_SIZE_LARGE, _ICON_SIZE_LARGE))
    save_btn_about.setProperty("class", "iconBtn")
    save_btn_about.setFixedSize(_ICON_BUTTON_FIXED, _ICON_BUTTON_FIXED)
    save_btn_about.setSizePolicy(
        QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
    )
    save_btn_about.clicked.connect(partial(
        self.show_help,
        u"save Workshop 保存过程版\n"
        u"save Master 保存完好版(publish)\n"
        u"打开/引用 Master 文件,可在任务列表里选择任务右键"
    ))

    btn_row.addWidget(self.btn_save_new_version, 1)
    btn_row.addWidget(self.btn_set_master, 1)
    btn_row.addWidget(save_btn_about, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    layout.addLayout(btn_row)
    return frame


def _build_right_panel(self):
    panel = QtWidgets.QWidget()
    panel.setMinimumWidth(150)

    right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
    right_splitter.addWidget(_build_preview_container(self))
    right_splitter.addWidget(_build_notes_container(self))
    right_splitter.setStretchFactor(0, 0)
    right_splitter.setStretchFactor(1, 1)

    desc_box = _build_description_container(self)

    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(right_splitter, 1)
    layout.addWidget(desc_box, 0)
    return panel


def _build_preview_container(self):
    top_container = QtWidgets.QWidget()
    top_layout = QtWidgets.QVBoxLayout(top_container)
    top_layout.setContentsMargins(0, 0, 0, 0)

    pv_group = QtWidgets.QGroupBox(u"预览")
    pv_layout = QtWidgets.QVBoxLayout(pv_group)
    pv_layout.setContentsMargins(4, 6, 4, 4)

    preview_container = QtWidgets.QWidget()
    preview_container.setMinimumSize(0, 0)
    preview_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    preview_grid = QtWidgets.QGridLayout(preview_container)
    preview_grid.setContentsMargins(0, 0, 0, 0)
    preview_grid.setSpacing(0)

    self.preview_label = AutoScalePixmapLabel()
    self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
    self.preview_label.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
    self.preview_label.setStyleSheet("background-color: #2b2b2b; color: #888;")

    btn_wrapper = QtWidgets.QWidget()
    btn_wrapper_layout = QtWidgets.QVBoxLayout(btn_wrapper)
    btn_wrapper_layout.setContentsMargins(0, 6, 6, 0)
    btn_wrapper_layout.setSpacing(6)

    self.btn_snapshot = QtWidgets.QPushButton()
    self.btn_snapshot.setToolTip(u"框选截图：点击后拖拽鼠标框选区域（Esc 取消）")
    self.btn_snapshot.setIcon(_make_snapshot_icon("region"))
    self.btn_snapshot.setIconSize(QtCore.QSize(20, 20))
    _style_float_camera_button(self.btn_snapshot, has_icon=True)
    self.btn_snapshot.setEnabled(False)
    self.btn_snapshot.clicked.connect(self.take_snapshot)

    self.btn_snapshot_direct = QtWidgets.QPushButton()
    self.btn_snapshot_direct.setToolTip(u"直接截图：立即截取当前 Maya 场景视图")
    self.btn_snapshot_direct.setIcon(_make_snapshot_icon("camera"))
    self.btn_snapshot_direct.setIconSize(QtCore.QSize(20, 20))
    _style_float_camera_button(self.btn_snapshot_direct, has_icon=True)
    self.btn_snapshot_direct.setEnabled(False)
    self.btn_snapshot_direct.clicked.connect(self.take_snapshot_direct)

    btn_wrapper_layout.addWidget(
        self.btn_snapshot, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight
    )
    btn_wrapper_layout.addWidget(
        self.btn_snapshot_direct, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight
    )
    btn_wrapper_layout.addStretch(1)

    preview_grid.addWidget(self.preview_label, 0, 0)
    preview_grid.addWidget(btn_wrapper, 0, 0)

    pv_layout.addWidget(preview_container)
    top_layout.addWidget(pv_group)

    top_container.setMinimumHeight(200)
    top_container.setMaximumHeight(500)
    return top_container


def _build_notes_container(self):
    box = QtWidgets.QGroupBox(u"Notes")
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(4, 6, 4, 4)

    self.notes_text = QtWidgets.QTextEdit()
    self.notes_text.setReadOnly(True)
    self.notes_text.setProperty("isNotes", True)
    self.notes_text.setMinimumHeight(150)
    layout.addWidget(self.notes_text)
    return box


def _build_description_container(self):
    box = QtWidgets.QGroupBox(u"Description")
    box.setFixedHeight(80)
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(4, 4, 4, 4)

    self.description_text = QtWidgets.QTextEdit()
    self.description_text.setPlaceholderText(u'临时备注')
    self.description_text.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
    )
    self.description_text.textChanged.connect(self.on_description_changed)
    layout.addWidget(self.description_text)
    return box


def build_openpipeline_ui(main_window):
    self = main_window

    main_layout = QtWidgets.QVBoxLayout(self)
    main = QtWidgets.QVBoxLayout()
    main.setContentsMargins(0, 0, 0, 0)
    main.setSpacing(6)
    main_layout.addLayout(main)

    _build_root_path_row(self, main)
    _build_project_row(self, main)
    _widgets.separator(main, True)

    splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
    splitter.addWidget(_build_left_panel(self))
    splitter.addWidget(_build_center_panel(self))
    splitter.addWidget(_build_right_panel(self))
    splitter.setSizes([120, 220, 160])
    main.addWidget(splitter)

    _widgets.create_copyrightText(main_layout, self.timeStamp)

    main_layout.setStretch(0, 1)
    main_layout.setStretch(1, 0)
    main_layout.setStretch(2, 0)


def about():
    from HelpImageUI import HelpImage
    HelpImage("", "pypenpipeline")