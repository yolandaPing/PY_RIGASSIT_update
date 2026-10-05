# -*- coding: utf-8 -*-

# .FileName:manager.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2025/7/24 21:19
# .Finish time:
import os, webbrowser
import traceback
import xml.etree.ElementTree as ET

from py_rigAssit import QtWidgets, QtCore, QtGui, QAction, Widgets, PyouPersistentWindow
from py_rigAssit.dialogs import base_dir, icon_dir
from py_rigAssit.dialogs.MarkingMenuLite import PYMarkingMenuLite
from py_rigAssit.dialogs.theme_manager import ThemeManager
from py_rigAssit.common.command_dispatcher import CommandDispatcher
import py_rigAssit.common.menu_commands
import py_rigAssit.common.commands

import Utils.json_info as json_info
import user_defined as ud
import maya.cmds as cmds

_widgest = Widgets()
_WINDOW_CACHE = None

_MENU_CONFIG_CACHE = None
_MARKING_CONFIG_CACHE = None
_MENU_CONFIG_FILE = "menu_config.xml"


try:
    text_type = unicode
except NameError:
    text_type = str


def _to_text(s):
    """统一转成 text_type，用于 Qt / XML。"""
    if s is None:
        return None
    if isinstance(s, text_type):
        return s
    try:
        return s.decode("utf-8")
    except Exception:
        try:
            return s.decode("gbk")
        except Exception:
            return s


def _read_xml_root():
    """读取 XML，剥离 BOM，返回 root element；失败返回 None。"""
    xml_path = os.path.join(os.path.dirname(__file__), _MENU_CONFIG_FILE)
    if not os.path.exists(xml_path):
        print("[menu_config] not found: {}".format(xml_path))
        return None
    try:
        with open(xml_path, "rb") as f:
            raw = f.read()
        if raw[:3] == b"\xef\xbb\xbf":
            raw = raw[3:]
        return ET.fromstring(raw)
    except Exception as e:
        print("[menu_config] parse failed: {}".format(e))
        return None


def _bool_attr(el, key, default=False):
    v = el.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _parse_args(args_str):
    """解析 args 属性字符串 -> tuple。支持 True/False/None/数字/字符串。"""
    if not args_str:
        return ()
    result = []
    for part in args_str.split(","):
        part = part.strip()
        if not part:
            continue
        low = part.lower()
        if low == "true":
            result.append(True)
        elif low == "false":
            result.append(False)
        elif low == "none":
            result.append(None)
        else:
            try:
                result.append(int(part))
            except ValueError:
                try:
                    result.append(float(part))
                except ValueError:
                    result.append(part)
    return tuple(result)

def load_menu_config(force_reload=False):
    """
    读取 menu_config.xml 中的 <menu> 节点（带缓存）。
    返回: { menu_name: [item_dict, ...] }
    """
    global _MENU_CONFIG_CACHE
    if _MENU_CONFIG_CACHE is not None and not force_reload:
        return _MENU_CONFIG_CACHE

    data = {}
    root = _read_xml_root()
    if root is None:
        _MENU_CONFIG_CACHE = data
        return data

    for menu_el in root:
        if menu_el.tag.lower() != "menu":
            continue

        menu_name = _to_text(menu_el.get("name"))
        if not menu_name:
            continue
        menu_name = menu_name.strip()
        if not menu_name:
            continue

        items = []
        for child in menu_el:
            tag = child.tag.lower()

            if tag == "separator":
                items.append({"type": "separator"})
                continue

            if tag != "item":
                continue

            label = _to_text(child.get("label")) or ""
            command = _to_text(child.get("command"))
            if command is not None:
                command = command.strip() or None

            item_id = _to_text(child.get("id"))
            if item_id is not None:
                item_id = item_id.strip() or None

            items.append({
                "type": "item",
                "label": label.strip(),
                "command": command,
                "bold": _bool_attr(child, "bold", False),
                "enabled": _bool_attr(child, "enabled", True),
                "checkable": _bool_attr(child, "checkable", False),
                "checked": _bool_attr(child, "checked", False),
                "item_id": item_id,
            })

        data[menu_name] = items

    _MENU_CONFIG_CACHE = data
    # print("[menu_config] loaded menus: {}".format(list(data.keys())))
    return data

def load_marking_config(force_reload=False):
    """
    读取 menu_config.xml 中的 <marking_menu> 节点（带缓存）。
    返回: { marking_name(lower): [item_dict, ...] }

    item_dict:
        {
            "label": text_type,
            "command": text_type or None,
            "args": tuple,
            "enabled": bool,
        }
    """
    global _MARKING_CONFIG_CACHE
    if _MARKING_CONFIG_CACHE is not None and not force_reload:
        return _MARKING_CONFIG_CACHE

    data = {}
    root = _read_xml_root()
    if root is None:
        _MARKING_CONFIG_CACHE = data
        return data

    for mm_el in root:
        if mm_el.tag.lower() != "marking_menu":
            continue

        mm_name = _to_text(mm_el.get("name"))
        if not mm_name:
            continue
        mm_name = mm_name.strip().lower()
        if not mm_name:
            continue

        items = []
        for child in mm_el:
            if child.tag.lower() != "item":
                continue

            # 标记菜单 label 保留原始空格
            label = _to_text(child.get("label")) or ""

            command = _to_text(child.get("command"))
            if command is not None:
                command = command.strip() or None

            args_str = _to_text(child.get("args"))
            args = _parse_args(args_str) if args_str else ()

            items.append({
                "label": label,
                "command": command,
                "args": args,
                "enabled": _bool_attr(child, "enabled", True),
            })

        data[mm_name] = items

    _MARKING_CONFIG_CACHE = data
    # print("[menu_config] loaded markings: {}".format(list(data.keys())))
    return data


def return_checkBox(item_text, state):

    key_map = {
        "Use shelfButton New": "shelfButton_New",
        "Auto import Hotkey": "hotkey",
        "Auto add sec/pri grp": "Grp_prisec",
        "SkinPaint Hotkey": "skinPaint_hotkey",
    }

    key = key_map.get(item_text)
    if key:
        ud.set_value(key, bool(state))
        setattr(ud, key, bool(state))


def copy_to_clipboard(text, msg=None):
    QtWidgets.QApplication.clipboard().setText(_to_text(text))

    try:
        cmds.inViewMessage(
            amg=msg or "Copied: <hl>{}</hl>".format(text),
            pos="midCenter",
            fade=True
        )
    except:
        print(msg or "Copied: {}".format(text))


class PYAboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PYAboutDialog, self).__init__(parent)
        self.setWindowTitle("About")
        self.resize(200, 220)
        layout = QtWidgets.QVBoxLayout(self)
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setText(
            "PY_RIGASSIT\n\n"
            "Supported Maya Versions:\n"
            "2018 - 2026\n\n"
            "Features:\n"
            "- Joint\n"
            "- IKFK\n"
            "- Copy Weight/BlendShape/FFD/UV/SDK/Deform\n"
            "- Copy Attribute\n"
            "- Mirror Attribute/SDK/Deform Weight\n"
            "- Editor BlendShape/SDK\n"
            "- Dirver Pose system\n"
            "- Openpipeline\n"
            "- Rivet Follice Tool\n"
            "- Combine SDK Driven\n"
            "- Transfer uv shader Tool\n"
            "- Split SkinWeight Tool\n"
            "- Animation Tool\n"
            "- Hotbox Designer\n"
            "- ......\n"
            "Rebuilt for production pipeline."
        )
        layout.addWidget(text)


class PYRiggingDialogManager(PyouPersistentWindow):

    WINDOW_NAME = "PYRiggingDialogManager"
    TOOL_NAME = "PY_RIGASSITDockControl"
    VERSION = "0.6"

    try:
        _info = json_info.version_info("tip")
    except:
        _info = None

    if _info:
        VERSION = _info[0]
        timeStamp = _info[1]
        webs = _info[-1]
    else:
        timeStamp = "2022-2026"
        webs = None

    def __init__(self, dialog_data, parent=None):

        super(PYRiggingDialogManager, self).__init__(
            self.WINDOW_NAME,
            self.WINDOW_NAME,
            parent
        )

        self.dialog_data = dialog_data
        self.ui_contents = dialog_data.get("INIT_UI", {})
        self.tab_names = dialog_data.get("TABS", ())
        self.window_size = dialog_data.get("WITHHIGHT", [320, 780])
        self.title = dialog_data.get("UI_NAME", "PY_RIGASSIT")

        self.dispatcher = CommandDispatcher()

        # FIX：防 Qt GC
        self._actions = []

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowTitle(self.title)
        self.resize(*self.window_size)

        self.build_ui()

        try:
            ThemeManager.apply(self)
        except:
            pass

        self.loadWindowSettings()
        self.setFocus()

    def build_ui(self):

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setSpacing(4)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.build_menu_bar()
        self.build_logo_area()
        self.build_tabs()
        self.build_footer()
        self.init_marking_menu()

    def build_menu_bar(self):

        self.menu_bar = QtWidgets.QMenuBar()

        try:
            self.menu_bar.setNativeMenuBar(False)
        except Exception:
            pass

        def add(menu, label, callback=None, checkable=False, checked=False,
                item_id=None, bold=False):

            label = _to_text(label) or ""
            act = QAction(label, self)  # FIX parent

            if bold:
                f = QtGui.QFont(act.font())
                f.setBold(True)
                act.setFont(f)

            if checkable:
                act.setCheckable(True)
                act.setChecked(checked)

                name = item_id or label

                def _cb(n=name, a=act, *args):
                    return_checkBox(n, a.isChecked())

                act.triggered.connect(_cb)

            if callback:
                act.triggered.connect(callback)

            menu.addAction(act)

            # FIX GC
            self._actions.append(act)

            return act

        # 根据 XML 生成一个菜单
        def build_from_config(menu_name):
            items = load_menu_config().get(menu_name, [])

            if not items:
                print("[menu_config] no items for menu: {}".format(menu_name))
                return None

            menu = self.menu_bar.addMenu(_to_text(menu_name))

            def _make_callback(command):
                def _cb(*a, **kw):
                    return self.dispatcher.execute(command)
                return _cb

            for item in items:
                if item["type"] == "separator":
                    menu.addSeparator()
                    continue

                cmd = item.get("command")
                callback = _make_callback(cmd) if cmd else None

                act = add(
                    menu,
                    item["label"],
                    callback=callback,
                    checkable=item.get("checkable", False),
                    checked=item.get("checked", False),
                    item_id=item.get("item_id"),
                    bold=item.get("bold", False),
                )

                if not item.get("enabled", True):
                    act.setEnabled(False)

            return menu

        about = self.menu_bar.addMenu("About")
        sep = about.addAction("PY_RIGASSIT")
        sep.setEnabled(False)
        about.addSeparator()
        add(about, "bilibili: 我有一只猛犬",
            callback=lambda: webbrowser.open("https://space.bilibili.com/3493142019967757"))
        add(about, "pyrigassit@gmail.com", callback=self._copy_email)
        add(about, "Update", callback=lambda: webbrowser.open(self._info[-2] if self._info else ""))
        add(about, "Quark 夸克网盘", callback=lambda: webbrowser.open(self._info[-1] if self._info else ""))
        add(about, "About", callback=self.show_about)

        build_from_config("Clear")
        build_from_config("Tool")

        opt = self.menu_bar.addMenu("Options")
        opt.addAction("Convenient").setEnabled(False)
        add(opt, "Use shelfButton New",
            checkable=True, checked=ud.shelfButton_New)
        add(opt, "Auto import Hotkey",
            checkable=True, checked=ud.hotkey)
        add(opt, "Auto add sec/pri grp",
            checkable=True, checked=ud.Grp_prisec)
        add(opt, "SkinPaint Hotkey",
            checkable=True, checked=ud.skinPaint_hotkey)
        opt.addSeparator()
        opt.addAction("Window Display").setEnabled(False)
        add(opt, "Dock",
            callback=self.to_dock_mode)
        add(opt, "Reload Theme",
            callback=self.reload_theme)

        try:
            self.main_layout.setMenuBar(self.menu_bar)
        except AttributeError:
            self.main_layout.addWidget(self.menu_bar)

    def build_logo_area(self):

        wrap = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(wrap)

        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        lay.setAlignment(QtCore.Qt.AlignCenter)

        self.logo_img = QtWidgets.QLabel()
        self.logo_img.setFixedHeight(60)
        self.logo_img.setAlignment(QtCore.Qt.AlignCenter)

        self.logo_text = QtWidgets.QLabel("PY_RIGASSIT {}".format(self.VERSION))
        self.logo_text.setAlignment(QtCore.Qt.AlignCenter)

        self.load_logo()

        lay.addWidget(self.logo_img)
        lay.addWidget(self.logo_text)

        self.main_layout.addWidget(wrap)

    def load_logo(self):
        icon_path = os.path.join(icon_dir, "PyAssistant.png")

        if not os.path.exists(icon_path):
            return

        pix = QtGui.QPixmap(icon_path)

        if pix.isNull():
            return

        self.logo_img.setPixmap(
            pix.scaled(
                100,
                60,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
        )

    def build_tabs(self):

        self.tabs = QtWidgets.QTabWidget()
        self.main_layout.addWidget(self.tabs)

        self._tab_state = {}

        for name in self.tab_names:

            page = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(page)
            lay.setContentsMargins(1, 1, 1, 1)
            lay.setSpacing(2)

            self.tabs.addTab(page, _to_text(name))

            self._tab_state[name] = {
                "layout": lay,
                "loaded": False
            }

        self.tabs.currentChanged.connect(self._load_tab)
        self._load_tab(0)

    def _load_tab(self, idx):

        if idx < 0:
            return

        name = self.tabs.tabText(idx)
        state = self._tab_state.get(name)
        if state is None:
            for k, v in self._tab_state.items():
                if _to_text(k) == name:
                    state = v
                    break

        if not state or state["loaded"]:
            return

        builder = self.ui_contents.get(name)
        if builder is None:
            for k, v in self.ui_contents.items():
                if _to_text(k) == name:
                    builder = v
                    break

        try:
            if callable(builder):
                obj = builder()

                if isinstance(obj, QtWidgets.QLayout):
                    state["layout"].addLayout(obj)
                else:
                    state["layout"].addWidget(obj)

        except:
            traceback.print_exc()

        state["loaded"] = True

    def build_footer(self):
        _widgest.create_copyrightText(
            self.main_layout,
            self.timeStamp
        )

    def _copy_email(self, *args):
        email = "pyrigassit@gmail.com"
        copy_to_clipboard(email, "Email copied")
        QtWidgets.QMessageBox.information(self, u'Email copied', u'邮箱复制成功')

    def init_marking_menu(self):

        config = load_marking_config()

        def _build_pairs(name):
            """根据 XML 生成 PYMarkingMenuLite 需要的 [(label, callback), ...]"""
            pairs = []
            for item in config.get(name, []):
                if not item.get("enabled", True):
                    continue

                cmd = item.get("command")
                args = item.get("args", ())
                label = item.get("label") or ""

                if cmd:
                    # 用 def 内部函数 + 默认参数做值绑定
                    def _make(c=cmd, a=args):
                        def _cb():
                            if a:
                                return self.dispatcher.execute(c, *a)
                            return self.dispatcher.execute(c)
                        return _cb
                    pairs.append((label, _make()))
                else:
                    # 无 command 的项留空操作，避免菜单项消失
                    pairs.append((label, lambda: None))

            return pairs

        self.mm_normal = PYMarkingMenuLite(_build_pairs("normal"), self, variant="normal")
        self.mm_ctrl = PYMarkingMenuLite(_build_pairs("ctrl"), self, variant="ctrl")
        self.mm_shift = PYMarkingMenuLite(_build_pairs("shift"), self, variant="shift")

    def show_about(self):
        dlg = PYAboutDialog(self)
        dlg.show()

    def reload_theme(self):
        # 重新加载 XML 菜单配置（下次重建窗口生效）
        load_menu_config(force_reload=True)
        load_marking_config(force_reload=True)
        try:
            ThemeManager.reload(self)
        except:
            pass

    def to_dock_mode(self):

        try:
            from py_rigAssit.dialogs.DockWindowBase import DockWindowBase
            dialog_data = self.dialog_data
            title = self.title
            widget_cls = self.__class__

            self.close()

            QtCore.QTimer.singleShot(
                0,
                lambda: DockWindowBase.safe_dock(
                    lambda: widget_cls(dialog_data),
                    title
                )
            )

        except Exception as e:

            print("Dock Failed: {}".format(e))

    def mousePressEvent(self, event):

        if event.button() == QtCore.Qt.RightButton:

            global_pos = self.mapToGlobal(event.pos())

            if event.modifiers() & QtCore.Qt.ControlModifier:
                self.mm_ctrl.start(global_pos)
            elif event.modifiers() & QtCore.Qt.ShiftModifier:
                self.mm_shift.start(global_pos)
            else:
                self.mm_normal.start(global_pos)

            return

        super(PYRiggingDialogManager, self).mousePressEvent(event)

    def closeEvent(self, event):

        try:
            self.saveWindowSettings()
        except:
            pass

        PyouPersistentWindow.closeEvent(self, event)


def show(dialog_data=None):

    global _WINDOW_CACHE

    if dialog_data is None:
        dialog_data = {
            "UI_NAME": "PY_RIGASSIT",
            "TABS": (),
            "WITHHIGHT": [325, 780],
            "INIT_UI": {},
        }

    try:
        if _WINDOW_CACHE:
            _WINDOW_CACHE.close()
            _WINDOW_CACHE.deleteLater()
    except:
        pass

    _WINDOW_CACHE = PYRiggingDialogManager(dialog_data)
    _WINDOW_CACHE.show()

    return _WINDOW_CACHE