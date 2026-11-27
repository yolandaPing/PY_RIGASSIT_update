# -*- coding: utf-8 -*-

# .FileName:quick_hash_rename.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/11/27 12:57
# .Finish time:
"""
用法：
    import quick_hash_rename
    quick_hash_rename.show_quick_rename_ui()
命名格式：
    name_###1_bind       -> name_001_bind
    name_###0_bind       -> name_000_bind
    name_###1_bind, hi=1 -> 同时处理选中对象的子层级
"""

import re

from py_rigAssit import QtWidgets, QtCore, QtGui, Widgets, PyouPersistentWindow

import maya.cmds as cmds


_WIDGETS = Widgets()
_py_quick_rename_ui = None

_FORMAT_RE = re.compile(u"(#+)(\\d+)", re.U)
_HI_RE = re.compile(u"[,;\\s]+hi\\s*=\\s*(\\d+)\\s*$", re.I | re.U)

try:
    _TEXT_TYPE = unicode  # noqa: F821  Python 2
except NameError:
    _TEXT_TYPE = str      # Python 3


def _to_unicode(value):
    if value is None:
        return u""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "mbcs", "cp936", "latin-1"):
            try:
                return value.decode(encoding)
            except Exception:
                pass
        return value.decode("utf-8", "replace")
    if isinstance(value, _TEXT_TYPE):
        return value
    try:
        return _TEXT_TYPE(value)
    except Exception:
        return _TEXT_TYPE(repr(value))


def parse_name_field(text):
    """解析输入框内容，返回 (命名模板, hi值或None)。"""
    # 低版本 PySide 的 text() 返回 QString，这里统一转成 unicode
    name = _to_unicode(text).strip()
    hi = None

    hi_match = _HI_RE.search(name)
    if hi_match:
        hi = int(hi_match.group(1))
        if hi not in (0, 1):
            raise ValueError(u"hi 只能是 0 或 1")
        name = name[:hi_match.start()].strip()

    match = _FORMAT_RE.search(name)
    if not match:
        raise ValueError(u"格式错误，应为 name_###1_bind")

    token = match.group(0)
    pad = len(match.group(1))
    start = int(match.group(2))
    fmt = "%0{}d".format(pad)

    prefix = name[:match.start()].replace("%", "%%")
    suffix = name[match.end():].replace("%", "%%")
    pattern = prefix + fmt + suffix

    return {
        "name": name,
        "pattern": pattern,
        "start": start,
        "hi": hi,
        "token": token,
    }

def _node_depth(path):
    return path.count("|")

def _is_transform_like(node):
    try:
        return "transform" in (cmds.nodeType(node, inherited=True) or [])
    except Exception:
        return False

def _get_hierarchy(selection):
    """获取选中对象及其子层级，只取 transform/joint 一类节点。"""
    if cmds is None:
        return []

    result = []
    seen = set()

    def add(node):
        if not node or node in seen or not cmds.objExists(node):
            return
        seen.add(node)
        result.append(node)

        children = cmds.listRelatives(
            node,
            children=True,
            fullPath=True,
            path=True,
        ) or []
        for child in children:
            if _is_transform_like(child):
                add(child)

    for obj in selection:
        add(obj)

    return result

def hash_rename(text_field=None, include_hierarchy=None):
    """
    text_field 可以是 QLineEdit，也可以是字符串
    include_hierarchy=True 时处理层级；None 时使用输入里的 hi 值。
    """
    if cmds is None:
        raise RuntimeError(u"hash_rename 必须在 Maya 中运行")
    if hasattr(text_field, "text"):
        raw_text = text_field.text()
    else:
        raw_text = text_field
    info = parse_name_field(raw_text)
    if include_hierarchy is None:
        include_hierarchy = bool(info["hi"])
    selection = cmds.ls(sl=True, l=True) or []
    if not selection:
        return []
    targets = _get_hierarchy(selection) if include_hierarchy else selection
    pairs = []
    idx = info["start"]
    for obj in targets:
        if not cmds.objExists(obj):
            continue
        pairs.append((obj, info["pattern"] % idx))
        idx += 1
    if not pairs:
        return []
    renamed = {}

    cmds.undoInfo(openChunk=True, chunkName="Quick Hash Rename")
    try:
        # 先从最深层改名，避免父级改名后子级长名称失效
        ordered = sorted(pairs, key=lambda item: _node_depth(item[0]), reverse=True)
        for old_path, new_name in ordered:
            new_path = cmds.rename(old_path, new_name)
            renamed[old_path] = new_path
            # 父级改名后，同步修正之前已改名子级的返回路径
            old_prefix = old_path + "|"
            new_prefix = new_path + "|"
            for key, value in list(renamed.items()):
                if key != old_path and value.startswith(old_prefix):
                    renamed[key] = new_prefix + value[len(old_prefix):]
    finally:
        cmds.undoInfo(closeChunk=True)
    return [renamed[old_path] for old_path, _ in pairs if old_path in renamed]


class QuickHashRenameWindow(PyouPersistentWindow):
    def __init__(self, parent=None):
        super(QuickHashRenameWindow, self).__init__("QuickHashRenameWindow", "QuickHashRenameWindow", parent)
        self.setWindowTitle(u"Quick Hash Rename")
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setMinimumWidth(320)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)
        row, self.name_field, self.apply_btn = _WIDGETS.create_QLineEdit_row(
            u"> ", label_width=30)
        self.name_field.setPlaceholderText(u"name_###1_bind, hi=1")
        self.name_field.setToolTip(
            u"name_###1_bind > name_001_bind\n"
            u"### 代表位数，紧随其后的数字是起始值（可为 0）\n"
            u", hi=1 包含子层级，, hi=0 只处理选中对象；回车也可执行"
        )
        self.name_field.setMinimumWidth(200)
        self.apply_btn.setText(u" Apply ")
        self.status_label = _WIDGETS.create_text(u"", self)
        self.status_label.setWordWrap(True)
        root.addLayout(row)
        root.addWidget(self.status_label)
        self.apply_btn.clicked.connect(self.apply_hash_rename)
        self.name_field.returnPressed.connect(self.apply_hash_rename)

    def apply_hash_rename(self):
        try:
            result = hash_rename(self.name_field.text())
        except Exception as exc:
            message = _to_unicode(exc)
            self.status_label.setText(u"重命名失败：{}".format(message))
            QtWidgets.QMessageBox.warning(self, u"重命名失败", message)
            return
        if not result:
            self.status_label.setText(u"未找到可重命名的对象，请先选择对象。")
            return
        self.status_label.setText(u"已重命名 {} 个对象。".format(len(result)))


def show():
    global _py_quick_rename_ui
    if _py_quick_rename_ui is None:
        _py_quick_rename_ui = QuickHashRenameWindow()
    _py_quick_rename_ui.show()
    _py_quick_rename_ui.raise_()
    _py_quick_rename_ui.activateWindow()
    return _py_quick_rename_ui


if __name__ == "__main__":
    show()
