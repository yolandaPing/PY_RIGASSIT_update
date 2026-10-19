# -*- coding: utf-8 -*-

# .FileName:description_manager.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/9/30 20:23
# .Finish time:

import io
import os
import sys

PY2 = (sys.version_info[0] == 2)


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
      - 实时保存；内容为空时写入空字符串（文件保留，不删除）
      - 使用 io.open(encoding='utf-8')，兼容 Python 2.7
      - 资产 hover tooltip 显示 description 内容
    """

    def _get_description_file_path(self, asset_name):
        if not (getattr(self, 'pm', None) and self.current_asset_type and asset_name):
            return None
        asset_dir = self.pm.get_asset_dir(self.current_asset_type, asset_name)
        return os.path.join(asset_dir, 'description.txt')

    def load_description(self):
        """选中 asset 时调用，加载内容到 UI（blockSignals 防止误保存）"""
        if not (getattr(self, 'pm', None) and self.selected_asset):
            self.clear_description_ui()
            return

        path = self._get_description_file_path(self.selected_asset)
        content = u''
        if path and os.path.exists(path):
            try:
                with io.open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(u"读取 description 失败: {}".format(e))

        self.description_text.blockSignals(True)
        self.description_text.setPlainText(_to_unicode(content))
        self.description_text.blockSignals(False)

    def on_description_changed(self):
        """textChanged 触发，实时保存；空内容写入空字符串，文件保留"""
        if not (getattr(self, 'pm', None) and self.selected_asset):
            return

        path = self._get_description_file_path(self.selected_asset)
        if not path:
            return

        content = _to_unicode(self.description_text.toPlainText())
        try:
            dir_path = os.path.dirname(path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            with io.open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(u"保存 description 失败: {}".format(e))

        # 同步更新当前选中资产在列表里的 tooltip
        if hasattr(self, 'asset_list'):
            stripped = content.strip()
            for i in range(self.asset_list.count()):
                item = self.asset_list.item(i)
                if item and item.text() == self.selected_asset:
                    item.setToolTip(stripped if stripped else self.selected_asset)
                    break

    def clear_description_ui(self):
        if hasattr(self, 'description_text'):
            self.description_text.blockSignals(True)
            self.description_text.clear()
            self.description_text.blockSignals(False)

    # ToolTip 支持
    def get_asset_description(self, asset_name):
        """读取指定资产的 description 文本（用于 tooltip）"""
        path = self._get_description_file_path(asset_name)
        if not (path and os.path.exists(path)):
            return u''
        try:
            with io.open(path, 'r', encoding='utf-8') as f:
                return _to_unicode(f.read()).strip()
        except Exception:
            return u''

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