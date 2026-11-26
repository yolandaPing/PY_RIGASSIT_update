# -*- coding: utf-8 -*-

# .FileName:description_manager.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/9/30 20:23
# .Finish time:

import io
import os
import sys
import logging

PY2 = (sys.version_info[0] == 2)
logger = logging.getLogger(__name__)


def _to_unicode(s):
    """把任意字符串安全转成 unicode（兼容 Python 2 / 3）"""
    if s is None:
        return u''
    if PY2:
        if isinstance(s, unicode):  # noqa: F821  (py2 内建)
            return s
        if isinstance(s, str):
            try:
                return s.decode('utf-8')
            except Exception:
                return s.decode('utf-8', 'replace')
        return unicode(s)  # noqa: F821
    else:
        if isinstance(s, bytes):
            try:
                return s.decode('utf-8')
            except Exception:
                return s.decode('utf-8', 'replace')
        return s


class DescriptionMixin(object):
    """资产级 Description 读写（存于 <asset>/description.txt）

    说明：
      - 路径与 subtype 无关，直接在 asset 目录下
      - 输入防抖 500ms 后保存；失焦时立即保存
      - 内容为空时写入空字符串（文件保留，不删除）
      - 使用 io.open(encoding='utf-8')，兼容 Python 2.7
      - 资产 hover tooltip 显示 description 内容
    """

    DESCRIPTION_SAVE_DELAY_MS = 500

    # --- 资产元数据缓存（.color / description.txt 等小文件） ---------------
    # key 为文件绝对路径，天然隔离不同项目/类型/资产，无需在切换时手动清空。
    # 写入方在落盘后调用 _set_asset_text_cache 更新对应条目。
    def _get_asset_meta_cache(self):
        cache = getattr(self, '_asset_meta_cache', None)
        if cache is None:
            cache = {}
            self._asset_meta_cache = cache
        return cache

    def _read_asset_text(self, path):
        """带缓存读文本文件，返回 (exists, content)。

        重复 load_assets（切排序/增删资产/切类型再切回）时直接命中缓存，
        避免逐资产反复磁盘 IO。
        """
        cache = self._get_asset_meta_cache()
        if path in cache:
            return cache[path]
        result = (False, u'')
        if path and os.path.exists(path):
            try:
                with io.open(path, 'r', encoding='utf-8') as f:
                    result = (True, f.read())
            except Exception:
                result = (False, u'')
        cache[path] = result
        return result

    def _set_asset_text_cache(self, path, exists, content):
        self._get_asset_meta_cache()[path] = (bool(exists), content)

    def _invalidate_asset_text(self, path):
        self._get_asset_meta_cache().pop(path, None)

    def _description_qt_core(self):
        """延迟获取 QtCore，避免本模块在非 UI 环境下导入失败。"""
        try:
            from ui_framework.core.qtCompat import QtCore
            return QtCore
        except Exception:
            try:
                from PySide2 import QtCore
                return QtCore
            except Exception:
                try:
                    from PySide import QtCore
                    return QtCore
                except Exception:
                    return None

    def _ensure_description_save_timer(self):
        """首次输入时创建定时器并安装失焦监听。"""
        if getattr(self, '_description_save_ready', False):
            return getattr(self, '_description_save_timer', None)

        text_edit = getattr(self, 'description_text', None)
        if text_edit is None:
            return None

        QtCore = self._description_qt_core()
        if QtCore is None:
            return None

        try:
            timer = QtCore.QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._flush_description_save)
            self._description_save_timer = timer
            text_edit.installEventFilter(self)
            self._description_save_ready = True
            return timer
        except Exception:
            return None

    def eventFilter(self, obj, event):
        """description_text 失焦时立即落盘，不等防抖定时器。"""
        if obj is getattr(self, 'description_text', None):
            try:
                QtCore = self._description_qt_core()
                qevent = getattr(QtCore, 'QEvent', None) if QtCore else None
                focus_out = getattr(qevent, 'FocusOut', None)
                if focus_out is not None and event.type() == focus_out:
                    self._flush_description_save()
            except Exception:
                pass
        try:
            return super(DescriptionMixin, self).eventFilter(obj, event)
        except Exception:
            return False

    def _get_description_file_path(self, asset_name):
        if not (getattr(self, 'pm', None) and self.current_asset_type and asset_name):
            return None
        asset_dir = self.pm.get_asset_dir(self.current_asset_type, asset_name)
        return os.path.join(asset_dir, 'description.txt')

    def ensure_unicode_text(self, txt):
        return _to_unicode(txt)

    def load_description(self):
        """选中 asset 时调用，加载内容到 UI（blockSignals 防止误保存）"""
        if not (getattr(self, 'pm', None) and self.selected_asset):
            self.clear_description_ui()
            return

        path = self._get_description_file_path(self.selected_asset)
        exists, content = self._read_asset_text(path)

        self.description_text.blockSignals(True)
        self.description_text.setPlainText(_to_unicode(content))
        self.description_text.blockSignals(False)

    def on_description_changed(self):
        """textChanged 触发：记录待保存内容并启动 500ms 防抖定时器。

        保存时带上触发时的资产名和路径，避免切换资产后把内容写到别的资产上。
        """
        if not (getattr(self, 'pm', None) and self.selected_asset):
            return

        asset_name = self.selected_asset
        path = self._get_description_file_path(asset_name)
        if not path:
            return

        content = _to_unicode(self.description_text.toPlainText())
        pending = (asset_name, path, content)

        timer = self._ensure_description_save_timer()
        self._pending_description_save = pending
        if timer is None:
            # 没有 Qt 定时器（非 UI 环境）时退化为立即保存
            self._flush_description_save()
        else:
            timer.start(self.DESCRIPTION_SAVE_DELAY_MS)

    def _flush_description_save(self):
        """把防抖期间最后一次文本内容写入磁盘。"""
        pending = getattr(self, '_pending_description_save', None)
        if not pending:
            return
        self._pending_description_save = None

        timer = getattr(self, '_description_save_timer', None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass

        asset_name, path, content = pending
        try:
            dir_path = os.path.dirname(path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            with io.open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._set_asset_text_cache(path, True, content)
        except Exception as e:
            self._invalidate_asset_text(path)
            logger.warning(u"保存 description 失败: %s", e)

        # 同步更新对应资产在列表里的 tooltip（用触发时的资产名，不用当前选中项）
        if hasattr(self, 'asset_list'):
            stripped = content.strip()
            for i in range(self.asset_list.count()):
                item = self.asset_list.item(i)
                if item and item.text() == asset_name:
                    item.setToolTip(stripped if stripped else asset_name)
                    break

    def clear_description_ui(self):
        if hasattr(self, 'description_text'):
            self.description_text.blockSignals(True)
            self.description_text.clear()
            self.description_text.blockSignals(False)

    # ToolTip 支持
    def get_asset_description(self, asset_name):
        """读取指定资产的 description 文本（用于 tooltip），走元数据缓存。"""
        path = self._get_description_file_path(asset_name)
        exists, content = self._read_asset_text(path)
        return _to_unicode(content).strip() if exists else u''

    def update_asset_tooltips(self):
        """批量给 asset_list 的每一项设置 tooltip（hover 显示 description）"""
        if not hasattr(self, 'asset_list'):
            return
        for i in range(self.asset_list.count()):
            item = self.asset_list.item(i)
            if not item:
                continue
            desc = self.get_asset_description(item.text())
            item.setToolTip(desc if desc else item.text())