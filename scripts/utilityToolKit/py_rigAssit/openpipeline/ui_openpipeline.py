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
except:
    from CommonUse.qtCompat import *
    from CommonUse.widgetsUse import Widgets

_widgets = Widgets()


def _load_maya_icon(*names):
    """按顺序尝试加载 Maya 内置图标，返回第一个可用的 QIcon；全失败返回空 QIcon。"""
    for name in names:
        for cand in (":" + name, name):
            pm = QtGui.QPixmap(cand)
            if not pm.isNull():
                return QtGui.QIcon(pm)
    return QtGui.QIcon()


def _set_maya_button_icon(button, names, size=14):
    """统一为按钮设置 Maya 图标；图标不存在时保留按钮原样。

    Args:
        button: 需要设置图标的 QPushButton。
        names: 按优先级排列的候选图标名称列表或元组。
        size: 图标宽高，默认 14。
    Returns:
        bool: 是否成功加载并设置图标。
    """
    icon = _load_maya_icon(*names)
    if icon.isNull():
        return False
    button.setIcon(icon)
    button.setIconSize(QtCore.QSize(size, size))
    return True

def _make_snapshot_icon(kind="camera"):
    """使用 QPainter 绘制图标，不依赖 Maya 图标资源；兼容 PySide2。"""
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


class AutoScalePixmapLabel(QtWidgets.QLabel):
    """QLabel 尺寸变化时自动缩放预览图，避免 splitter 缩放后图片尺寸不变。"""
    def __init__(self, parent=None):
        QtWidgets.QLabel.__init__(self, parent)
        self._source_pixmap = QtGui.QPixmap()
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

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


def _style_float_camera_button(btn, has_icon=True):
    """预览框右上角的浮动圆形按钮（框选截图 / 直接截图共用）"""
    btn.setFixedSize(32, 32)
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    if has_icon:
        btn.setStyleSheet("""
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
        """)
    else:
        btn.setStyleSheet("""
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
        """)


class ScreenRegionSelector(QtWidgets.QWidget):
    """
    全屏截图选区控件：
      - 显示全屏截图作为背景
      - 用户拖拽鼠标框选区域
      - 选区内显示原图（不透明），选区外被半透明黑遮罩
      - 鼠标释放后发射 region_selected(QRect 全局屏幕坐标)
      - ESC 取消 -> cancelled
    """
    region_selected = QtCore.Signal(QtCore.QRect)
    cancelled = QtCore.Signal()

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

        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 120))

        if self._start and self._current:
            rect = QtCore.QRect(self._start, self._current).normalized()

            if (not self._screenshot.isNull()
                    and self.width() > 0 and self.height() > 0
                    and rect.width() > 0 and rect.height() > 0):
                sx = int(rect.x() * self._screenshot.width() / self.width())
                sy = int(rect.y() * self._screenshot.height() / self.height())
                sw = int(rect.width() * self._screenshot.width() / self.width())
                sh = int(rect.height() * self._screenshot.height() / self.height())
                src_rect = QtCore.QRect(sx, sy, max(1, sw), max(1, sh))
                painter.drawPixmap(rect, self._screenshot, src_rect)

            pen = QtGui.QPen(QtGui.QColor(77, 208, 225), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            text = u"{} × {}".format(rect.width(), rect.height())
            painter.setPen(QtGui.QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            fm = painter.fontMetrics()
            text_rect = fm.boundingRect(text).adjusted(-8, -3, 8, 3)
            text_rect.moveTopLeft(
                rect.topLeft() + QtCore.QPoint(0, -text_rect.height() - 4)
            )
            if text_rect.top() < 0:
                text_rect.moveTopLeft(
                    rect.bottomLeft() + QtCore.QPoint(0, 4)
                )
            painter.fillRect(text_rect, QtGui.QColor(0, 0, 0, 180))
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
        if event.button() == QtCore.Qt.LeftButton and self._start:
            rect = QtCore.QRect(self._start, event.pos()).normalized()
            self._start = None
            self._current = None
            self.update()

            if rect.width() >= 10 and rect.height() >= 10:
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
    """从全屏截图中裁切出全局屏幕坐标 global_rect 对应的区域，返回 QPixmap"""
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

def build_openpipeline_ui(main_window):

    self = main_window

    main_layout = QtWidgets.QVBoxLayout(self)
    main = QtWidgets.QVBoxLayout()
    main.setContentsMargins(0, 0, 0, 0)
    main.setSpacing(6)
    main_layout.addLayout(main)
    root_row = QtWidgets.QHBoxLayout()
    root_row.setSpacing(6)
    path_card = QtWidgets.QFrame()
    path_card.setProperty("card", True)
    path_card_layout = QtWidgets.QHBoxLayout(path_card)
    path_card_layout.setContentsMargins(10, 4, 10, 4)
    path_card_layout.setSpacing(8)

    icon_label = QtWidgets.QLabel()
    try:
        icon_label.setPixmap(
            self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon).pixmap(16, 16)
        )
    except Exception:
        pass
    icon_label.setFixedWidth(16)
    icon_label.setAlignment(QtCore.Qt.AlignCenter)

    lbl_root = QtWidgets.QLabel(u'项目根路径:')
    self.root_path_label = QtWidgets.QLabel(u'未设置')
    self.root_path_label.setProperty("isText", True)
    self.root_path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    self.root_path_label.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
    )
    self.root_path_label.setMinimumWidth(200)

    path_card_layout.addWidget(icon_label)
    path_card_layout.addWidget(lbl_root)
    path_card_layout.addWidget(self.root_path_label, 1)
    root_row.addWidget(path_card, 1)

    btn_set_root = QtWidgets.QPushButton(u'[设置路径]')
    btn_set_root.setProperty("cld_main", True)
    btn_set_root.setCursor(QtCore.Qt.PointingHandCursor)
    btn_set_root.setMinimumHeight(28)
    btn_set_root.clicked.connect(self.set_project_root_path)

    btn_check_root = QtWidgets.QPushButton(u'检查项目')
    btn_check_root.setProperty("secondary", True)
    btn_check_root.setCursor(QtCore.Qt.PointingHandCursor)
    btn_check_root.setMinimumHeight(28)
    btn_check_root.clicked.connect(self.check_projects_in_root)

    btn_check_config = QtWidgets.QPushButton(u'检查配置')
    btn_check_config.setProperty("secondary", True)
    btn_check_config.setCursor(QtCore.Qt.PointingHandCursor)
    btn_check_config.setMinimumHeight(28)
    btn_check_config.clicked.connect(self.check_config)

    root_row.addWidget(btn_set_root)
    root_row.addWidget(btn_check_root)
    root_row.addWidget(btn_check_config)
    main.addLayout(root_row)

    prow = QtWidgets.QHBoxLayout()
    prow.setSpacing(6)
    prow.addSpacing(10)

    proj_icon = QtWidgets.QLabel()
    try:
        proj_icon.setPixmap(
            self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon).pixmap(16, 16)
        )
    except Exception:
        pass
    proj_icon.setFixedWidth(16)
    proj_icon.setAlignment(QtCore.Qt.AlignCenter)

    lbl = QtWidgets.QLabel(u'当前项目:')
    self.project_combo = QtWidgets.QComboBox()
    self.project_combo.setMinimumWidth(220)
    self.project_combo.setMinimumHeight(28)
    self.project_combo.setSizePolicy(
        QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
    )
    self.project_combo.currentTextChanged.connect(self.on_project_changed)

    btn_new = QtWidgets.QPushButton(u'新建')
    btn_new.setProperty("cld_main", True)
    btn_new.setCursor(QtCore.Qt.PointingHandCursor)
    btn_new.setMinimumHeight(28)
    _set_maya_button_icon(btn_new, ("add.png", "new.png", "fileNew.png"), 14)
    btn_new.clicked.connect(self.create_project_dialog)

    btn_open = QtWidgets.QPushButton('打开')
    btn_open.setToolTip("打开位置")
    btn_open.setProperty("secondary", True)
    btn_open.setCursor(QtCore.Qt.PointingHandCursor)
    btn_open.setMinimumHeight(28)
    _set_maya_button_icon(btn_open, ("folder-open.png", "folder.png", "openFolder.png"), 16)
    btn_open.clicked.connect(self.open_existing_project)

    btn_refresh = QtWidgets.QPushButton()
    btn_refresh.setIcon(QtGui.QIcon(":refresh.png"))
    btn_refresh.setIconSize(QtCore.QSize(16, 16))
    btn_refresh.setToolTip(u"刷新项目列表")
    btn_refresh.setProperty("class", "iconBtn")
    btn_refresh.setProperty("help", True)
    btn_refresh.setFixedSize(28, 28)
    btn_refresh.clicked.connect(self.load_projects)

    btn_about = QtWidgets.QPushButton()
    btn_about.setIcon(QtGui.QIcon(":help.png"))
    btn_about.setIconSize(QtCore.QSize(16, 16))
    btn_about.setToolTip(u"帮助")
    btn_about.setProperty("class", "iconBtn")
    # btn_about.setProperty("help", True)
    btn_about.setFixedSize(28, 28)
    btn_about.clicked.connect(about)

    prow.addWidget(proj_icon)
    prow.addWidget(lbl)
    prow.addWidget(self.project_combo)
    prow.addWidget(btn_new)
    prow.addWidget(btn_open)
    prow.addStretch(1)
    prow.addWidget(btn_refresh)
    prow.addWidget(btn_about)
    main.addLayout(prow)

    _widgets.separator(main, True)

    splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

    leftw = QtWidgets.QWidget()
    leftl = QtWidgets.QVBoxLayout()
    leftl.setContentsMargins(0, 0, 0, 0)
    leftl.setSpacing(0)
    type_row_group = QtWidgets.QGroupBox(u"类型")
    type_row = QtWidgets.QHBoxLayout(type_row_group)
    type_row.setContentsMargins(4, 4, 4, 4)
    self.type_combo = QtWidgets.QComboBox()
    self.type_combo.currentTextChanged.connect(self.on_asset_type_changed)

    btn_addtype = QtWidgets.QPushButton('+')
    btn_addtype.setFixedWidth(24)
    btn_addtype.setMaximumHeight(24)
    btn_addtype.setStyleSheet("font: bold 16px; {} color: green;".format(_widgets.button_bgc))
    btn_addtype.clicked.connect(self.add_asset_type)
    btn_deltype = QtWidgets.QPushButton('-')
    btn_deltype.setFixedWidth(24)
    btn_deltype.setMaximumHeight(24)
    btn_deltype.setStyleSheet("font: bold 16px; {} color: red;".format(_widgets.button_bgc))
    btn_deltype.clicked.connect(self.delete_asset_type)

    btn_box = QtWidgets.QHBoxLayout()
    btn_box.setContentsMargins(0, 0, 0, 0)
    btn_box.setSpacing(0)
    btn_box.addWidget(btn_addtype)
    btn_box.addWidget(btn_deltype)

    type_row.addWidget(self.type_combo, 1)
    type_row.addLayout(btn_box)
    leftl.addWidget(type_row_group)

    asset_group = QtWidgets.QGroupBox(u"对象名称")
    asset_layout = QtWidgets.QVBoxLayout(asset_group)
    asset_layout.setContentsMargins(4, 4, 4, 4)
    self.asset_sort_block = _widgets.create_radiogroup(
        "",[(" Name ", 1, None), (" Date ", 2, None),],
        default_id=1
    )
    self.search_edit = QtWidgets.QLineEdit()
    self.search_edit.setPlaceholderText(u'搜索资产...')
    self.search_edit.textChanged.connect(self.filter_assets)

    leftl.addWidget(asset_group)

    self.asset_list = QtWidgets.QListWidget()
    self.asset_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.asset_list.setAlternatingRowColors(True)
    self.asset_list.itemClicked.connect(self.on_asset_clicked)
    self.asset_list.customContextMenuRequested.connect(self.show_asset_context_menu)
    self.asset_sort_block.idClicked.connect(self.on_asset_sort_changed)
    asset_layout.addWidget(self.asset_sort_block)
    asset_layout.addWidget(self.search_edit)
    asset_layout.addWidget(self.asset_list)

    asset_btn_row = QtWidgets.QHBoxLayout()
    self.asset_count = _widgets.create_text("")

    self.btn_create_asset = QtWidgets.QPushButton(u'new')
    self.btn_create_asset.setProperty("cld_main", True)
    self.btn_create_asset.setCursor(QtCore.Qt.PointingHandCursor)
    self.btn_create_asset.setMinimumHeight(24)
    _set_maya_button_icon(self.btn_create_asset, ("add.png", "new.png", "fileNew.png"), 14)
    self.btn_create_asset.clicked.connect(self.create_asset_dialog)
    self.btn_create_asset.setEnabled(False)

    self.btn_delete_asset = QtWidgets.QPushButton(u'del')
    self.btn_delete_asset.setProperty("danger", True)
    self.btn_delete_asset.setCursor(QtCore.Qt.PointingHandCursor)
    self.btn_delete_asset.setMinimumHeight(24)
    _set_maya_button_icon(self.btn_delete_asset, ("delete.png", "remove.png", "trash.png"), 14)
    self.btn_delete_asset.clicked.connect(self.delete_asset_dialog)
    self.btn_delete_asset.setEnabled(False)
    self.btn_delete_asset.setVisible(False)
    self.btn_create_asset.setToolTip("新建资产")
    self.btn_delete_asset.setToolTip("删除选择的资产")
    asset_btn_row.addWidget(self.asset_count)
    asset_btn_row.addWidget(self.btn_create_asset)
    asset_btn_row.addWidget(self.btn_delete_asset)
    asset_btn_row.addStretch()
    asset_layout.addLayout(asset_btn_row)

    leftw.setLayout(leftl)
    leftw.setMinimumWidth(100)

    centerw = QtWidgets.QWidget()
    center_layout = QtWidgets.QVBoxLayout(centerw)
    center_layout.setContentsMargins(0, 0, 0, 0)
    subtype_frame = QtWidgets.QGroupBox(u"任务")
    subtype_layout = QtWidgets.QVBoxLayout(subtype_frame)
    subtype_layout.setContentsMargins(4, 4, 4, 4)
    subtype_layout.setSpacing(6)
    self.info_label = QtWidgets.QLabel(u'未选择资产')
    self.info_label.setWordWrap(True)
    self.info_label.setAlignment(QtCore.Qt.AlignLeft)
    self.info_label.setMaximumHeight(15)
    self.info_label.setStyleSheet('color:yellow; font-size: 12px;')
    subtype_layout.addWidget(self.info_label)

    self.subtype_list = QtWidgets.QListWidget()
    self.subtype_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.subtype_list.setAlternatingRowColors(True)
    self.subtype_list.itemClicked.connect(self.on_subtype_clicked)
    self.subtype_list.itemDoubleClicked.connect(self.on_subtype_double_clicked)
    self.subtype_list.customContextMenuRequested.connect(self.show_subtype_context_menu)
    subtype_layout.addWidget(self.subtype_list)

    sub_btns = QtWidgets.QHBoxLayout()
    self.btn_add_sub = QtWidgets.QPushButton(u'new')
    self.btn_del_sub = QtWidgets.QPushButton(u'delete')
    self.btn_rename_sub = QtWidgets.QPushButton(u'rename')
    self.btn_add_sub.setEnabled(False)
    self.btn_rename_sub.setEnabled(False)
    self.btn_del_sub.setEnabled(False)
    self.btn_add_sub.setStyleSheet('font: bold 12px;')
    self.btn_del_sub.setStyleSheet('font: bold 12px;')
    self.btn_rename_sub.setStyleSheet('font: bold 12px;')
    _set_maya_button_icon(self.btn_add_sub,("add.png", "new.png", "fileNew.png"), 14)
    _set_maya_button_icon(self.btn_rename_sub, ("edit.png", "rename.png", "pencil.png"), 14)
    _set_maya_button_icon(self.btn_del_sub, ("delete.png", "remove.png", "trash.png"), 14)
    sub_btns.addWidget(self.btn_add_sub)
    sub_btns.addWidget(self.btn_rename_sub)
    sub_btns.addWidget(self.btn_del_sub)

    subtype_layout.addLayout(sub_btns)

    self.btn_add_sub.clicked.connect(self.add_subtype_dialog)
    self.btn_del_sub.clicked.connect(self.delete_subtype)
    self.btn_rename_sub.clicked.connect(self.rename_subtype)

    version_frame = QtWidgets.QGroupBox(u"版本")
    version_layout = QtWidgets.QVBoxLayout(version_frame)
    version_layout.setContentsMargins(4, 4, 4, 4)
    version_title_layout = QtWidgets.QHBoxLayout()
    version_title_layout.addWidget(QtWidgets.QLabel(''))
    self.version_count_text = _widgets.create_text('')
    self.version_count_text.setWordWrap(True)
    version_title_layout.addWidget(self.version_count_text)
    version_layout.addLayout(version_title_layout)

    self.version_list = QtWidgets.QListWidget()
    self.version_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.version_list.setAlternatingRowColors(True)
    self.version_list.itemDoubleClicked.connect(self.open_selected_version)
    self.version_list.customContextMenuRequested.connect(self.show_version_context_menu)
    version_layout.addWidget(self.version_list)

    vbtn_row1 = QtWidgets.QHBoxLayout()

    self.btn_save_new_version = QtWidgets.QPushButton('save Workshop')
    self.btn_save_new_version.setCursor(QtCore.Qt.PointingHandCursor)
    self.btn_save_new_version.setMinimumHeight(24)
    _set_maya_button_icon(self.btn_save_new_version, ("save.png", "fileSave.png", "saveAs.png", "fileSaveAs.png"), 14)
    self.btn_save_new_version.clicked.connect(self.save_new_version)
    self.btn_save_new_version.setProperty("main", True)
    self.btn_save_new_version.setStyleSheet("color: gray;")
    self.btn_save_new_version.setEnabled(False)

    self.btn_set_master = QtWidgets.QPushButton('save Master')
    self.btn_set_master.setCursor(QtCore.Qt.PointingHandCursor)
    self.btn_set_master.setMinimumHeight(24)
    _set_maya_button_icon(self.btn_set_master, ("publish.png", "checkin.png", "checkMark.png", "save.png", "fileSave.png"), 14)
    self.btn_set_master.clicked.connect(self.save_new_master)
    self.btn_set_master.setProperty("main", True)
    self.btn_set_master.setStyleSheet("color: gray;")
    self.btn_set_master.setEnabled(False)

    save_btn_about = QtWidgets.QPushButton()
    save_btn_about.clicked.connect(partial(self.show_help, u"save Workshop 保存过程版\nsave Master 保存完好版(publish)\n打开\引用 Master 文件,可在任务列表里选择任务右键"))
    save_btn_about.setIcon(QtGui.QIcon(":help.png"))
    save_btn_about.setIconSize(QtCore.QSize(24, 24))
    save_btn_about.setProperty("class", "iconBtn")
    save_btn_about.setFixedSize(28, 28)
    save_btn_about.setSizePolicy(
        QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
    )

    vbtn_row1.addWidget(self.btn_save_new_version, 1)
    vbtn_row1.addWidget(self.btn_set_master, 1)
    vbtn_row1.addWidget(save_btn_about, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    version_layout.addLayout(vbtn_row1)

    vsplitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
    vsplitter.addWidget(subtype_frame)
    vsplitter.addWidget(version_frame)
    vsplitter.setSizes([200, 600])
    center_layout.addWidget(vsplitter)
    centerw.setMinimumWidth(150)

    rightw = QtWidgets.QWidget()
    rightw.setMinimumWidth(150)
    right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

    top_container = QtWidgets.QWidget()
    top_layout = QtWidgets.QVBoxLayout(top_container)
    top_layout.setContentsMargins(0, 0, 0, 0)
    pv_col_grp = QtWidgets.QGroupBox(u"预览")
    pv_col = QtWidgets.QVBoxLayout(pv_col_grp)
    pv_col.setContentsMargins(4, 6, 4, 4)
    # 预览容器
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
    # 框选截图
    self.btn_snapshot = QtWidgets.QPushButton()
    self.btn_snapshot.setToolTip(u"框选截图：点击后拖拽鼠标框选区域（Esc 取消）")
    self.btn_snapshot.setIcon(_make_snapshot_icon("region"))
    self.btn_snapshot.setIconSize(QtCore.QSize(20, 20))
    _style_float_camera_button(self.btn_snapshot, has_icon=True)
    self.btn_snapshot.clicked.connect(self.take_snapshot)
    self.btn_snapshot.setEnabled(False)
    # 直接截图
    self.btn_snapshot_direct = QtWidgets.QPushButton()
    self.btn_snapshot_direct.setToolTip(u"直接截图：立即截取当前 Maya 场景视图")
    self.btn_snapshot_direct.setIcon(_make_snapshot_icon("camera"))
    self.btn_snapshot_direct.setIconSize(QtCore.QSize(20, 20))
    _style_float_camera_button(self.btn_snapshot_direct, has_icon=True)
    self.btn_snapshot_direct.clicked.connect(self.take_snapshot_direct)
    self.btn_snapshot_direct.setEnabled(False)
    # 两个按钮纵向堆叠在右上角
    btn_wrapper = QtWidgets.QWidget()
    btn_wrapper_layout = QtWidgets.QVBoxLayout(btn_wrapper)
    btn_wrapper_layout.setContentsMargins(0, 6, 6, 0)
    btn_wrapper_layout.setSpacing(6)
    btn_wrapper_layout.addWidget(self.btn_snapshot, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
    btn_wrapper_layout.addWidget(self.btn_snapshot_direct, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
    btn_wrapper_layout.addStretch(1)

    preview_grid.addWidget(self.preview_label, 0, 0)
    preview_grid.addWidget(btn_wrapper, 0, 0)
    pv_col.addWidget(preview_container)
    top_layout.addWidget(pv_col_grp)
    top_container.setMinimumHeight(200)
    top_container.setMaximumHeight(500)

    bottom_container = QtWidgets.QGroupBox("Notes")
    bottom_layout = QtWidgets.QVBoxLayout(bottom_container)
    bottom_layout.setContentsMargins(4, 6, 4, 4)
    self.notes_text = QtWidgets.QTextEdit()
    self.notes_text.setReadOnly(True)
    self.notes_text.setProperty("isNotes", True)
    self.notes_text.setMinimumHeight(150)
    bottom_layout.addWidget(self.notes_text)

    right_splitter.addWidget(top_container)
    right_splitter.addWidget(bottom_container)
    right_splitter.setStretchFactor(0, 0)
    right_splitter.setStretchFactor(1, 1)
    # Description
    description_con = QtWidgets.QGroupBox("Description")
    description_con.setFixedHeight(80)
    description_layout = QtWidgets.QVBoxLayout(description_con)
    description_layout.setContentsMargins(4, 4, 4, 4)
    self.description_text = QtWidgets.QTextEdit()
    self.description_text.setPlaceholderText(u'临时备注')
    self.description_text.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    self.description_text.textChanged.connect(self.on_description_changed)
    description_layout.addWidget(self.description_text)

    right_layout = QtWidgets.QVBoxLayout(rightw)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(0)
    right_layout.addWidget(right_splitter, 1)
    right_layout.addWidget(description_con, 0)

    splitter.addWidget(leftw)
    splitter.addWidget(centerw)
    splitter.addWidget(rightw)
    splitter.setSizes([120, 220, 160])
    main.addWidget(splitter)

    _widgets.create_copyrightText(main_layout, self.timeStamp)

    main_layout.setStretch(0, 1)
    main_layout.setStretch(1, 0)
    main_layout.setStretch(2, 0)


def about():
    from HelpImageUI import HelpImage
    HelpImage("", "pypenpipeline")

