# -*- coding: utf-8 -*-
# .FileName:version_context.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2025/12/13 13:02
from functools import partial

import os
import io
import shutil
from datetime import datetime

try:
    from importlib import reload
except ImportError:
    pass

from ui_framework.core.qtCompat import *
from Pipeline import file_operations as file_ops
from Pipeline.pipelineConfig import OpenPipelineConfig
from Pipeline.projectManager import ProjectManager
from .text_utils import _u
from .fbx_service import FBXExporter, add_fbx_menu

try:
    from Pipeline.pipelineUtils import (
        load_projects_from_xml,
        get_projects_xml_path,
        ensure_projects_xml,
        add_project_to_xml,
        open_folder_in_explorer,
        open_file_in_explorer
    )
except ImportError:
    try:
        from .pipelineUtils import *
    except ImportError:
        print(u"version_context导入工具pipeline_utils模块失败")

from py_rigAssit.common.quick_ng_transfer import export_to, import_from, cleanup_scene_ng
from Utils.undo import undo

try:
    import maya.cmds as cmds
    import maya.mel as mel
    IN_MAYA = True
except Exception:
    IN_MAYA = False

_cfg = OpenPipelineConfig()

_color_options = [
    (u"🟡 黄色", "yellow"),
    (u"🔴 红色", "red"),
    (u"🔵 蓝色", "blue"),
    (u"🟢 绿色", "green"),
    (u"❌ 清除标记", None)
]


def _show_info_inview(title=u"Finished", color='yellow'):
    import HelpImageUI as help
    help.inView_Message(color, u"{}".format(_u(title)))


def add_menu_label(menu, text, color="yellow"):
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(widget)
    label = QtWidgets.QLabel(_u(text))
    label.setStyleSheet("color: {};".format(color))
    layout.addWidget(label)
    layout.setContentsMargins(20, 2, 5, 2)
    widget.setLayout(layout)
    label_action = QtWidgets.QWidgetAction(menu)
    label_action.setDefaultWidget(widget)
    menu.addAction(label_action)


class PipelineContext(object):

    def __init__(self, main_window):
        self.ui = main_window

    @property
    def pm(self):
        return self.ui.pm

    @property
    def asset_type(self):
        return self.ui.current_asset_type

    @property
    def asset(self):
        return self.ui.selected_asset

    @property
    def subtype(self):
        return self.ui.selected_subtype

    def validate_asset(self):
        return bool(self.pm and self.asset_type)

    def validate_subtype(self):
        return bool(
            self.pm and
            self.asset_type and
            self.asset and
            self.subtype
        )


class PathService(PipelineContext):

    def asset_dir(self, asset_name=None):
        asset_name = asset_name or self.asset
        return self.pm.get_asset_dir(self.asset_type, asset_name)

    def subtype_dir(self, subtype_name=None):
        subtype_name = subtype_name or self.subtype
        return os.path.join(self.asset_dir(), 'components', subtype_name)

    def workshop_dir(self):
        return os.path.join(self.subtype_dir(), 'workshop')

    def version_path(self, version_name):
        return os.path.join(self.workshop_dir(), version_name)

    def skin_dir(self):
        return os.path.join(self.subtype_dir(), 'skin')

    def open_asset_path(self, asset_name):
        if not self.validate_asset():
            self.ui.show_warning(u'错误', u'请先选择资产类型')
            return

        path = self.asset_dir(asset_name)

        if os.path.exists(path):
            open_folder_in_explorer(_u(path).replace("/", "\\"))
        else:
            self.ui.show_warning(u'错误', u'资产路径不存在:\n{}'.format(_u(path)))

    def open_subtype_path(self, subtype_name):
        if not self.validate_subtype():
            self.ui.show_warning(u'错误', u'请先选择资产和任务')
            return

        path = os.path.join(self.asset_dir(), 'components', subtype_name)

        if os.path.exists(path):
            open_folder_in_explorer(_u(path).replace("/", "\\"))
        else:
            self.ui.show_warning(u'错误', u'任务路径不存在:\n{}'.format(_u(path)))

    def open_version_path(self, version_name):
        if not self.validate_subtype():
            self.ui.show_warning(u'错误', u'请先选择资产和任务')
            return

        path = self.version_path(version_name)

        if os.path.exists(path):
            open_file_in_explorer(_u(path).replace("/", "\\"))
        else:
            self.ui.show_warning(u'错误', u'版本文件不存在:\n{}'.format(_u(path)))

    def get_file_info(self, version_filename):
        file_path = self.version_path(version_filename)

        if not os.path.exists(file_path):
            return u""

        try:
            size_bytes = os.path.getsize(file_path)
            mod_time = os.path.getmtime(file_path)

            return u"\n\n文件大小: {:.1f} KB\n最后修改: {}".format(
                size_bytes / 1024.0,
                _u(datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M'))
            )
        except Exception:
            return u"\n\n(无法获取文件信息)"


class VersionService(PathService):

    def refresh_version_list(self):
        if not self.validate_subtype():
            return

        versions = self.pm.get_workshop_versions(
            self.asset_type,
            self.asset,
            self.subtype
        ) or []

        version_list = self.ui.version_list
        version_list.clear()

        for version in versions:
            version_list.addItem(_u(version))

    def backup_to_deleted_folder(self, file_path):
        if not os.path.exists(file_path):
            return False

        deleted_dir = os.path.join(self.subtype_dir(), "deleted")

        if not os.path.exists(deleted_dir):
            os.makedirs(deleted_dir)

        filename = os.path.basename(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_name = u"{}_{}".format(_u(timestamp), _u(filename))
        backup_path = os.path.join(deleted_dir, backup_name)

        shutil.copy2(file_path, backup_path)
        return True

    def is_master_version(self, version_filename):
        try:
            master_path = self.pm.get_master_file(
                self.asset_type,
                self.asset,
                self.subtype
            )

            if not master_path:
                return False

            master_name = os.path.basename(master_path)
            return master_name == version_filename
        except Exception:
            return False

    def delete_selected_version(self, version_filename):
        if not self.validate_subtype():
            self.ui.show_warning(u'错误', u'请先选择资产和任务')
            return False

        file_path = self.version_path(version_filename)

        if not os.path.exists(file_path):
            self.ui.show_warning(u'错误', u'文件不存在:\n{}'.format(_u(file_path)))
            return False

        if self.is_master_version(version_filename):
            reply = QtWidgets.QMessageBox.question(
                self.ui,
                u'警告',
                u'该版本是 Master，删除后 Master 将失效。\n确定继续？',
                QtWidgets.QMessageBox.Yes |
                QtWidgets.QMessageBox.No
            )

            if reply != QtWidgets.QMessageBox.Yes:
                return False
        else:
            reply = QtWidgets.QMessageBox.question(
                self.ui,
                u'确认删除',
                u'确定删除版本？\n{}'.format(_u(version_filename)),
                QtWidgets.QMessageBox.Yes |
                QtWidgets.QMessageBox.No
            )

            if reply != QtWidgets.QMessageBox.Yes:
                return False

        try:
            self.backup_to_deleted_folder(file_path)
        except Exception as e:
            print(u"备份删除文件失败: {}".format(_u(e)))

        try:
            os.remove(file_path)
        except Exception as e:
            self.ui.show_critical(u'删除失败', _u(e))
            return False

        note_path = file_path + ".note"
        if os.path.exists(note_path):
            try:
                os.remove(note_path)
            except Exception:
                pass

        self.refresh_version_list()

        _show_info_inview(u'版本文件已删除', 'green')

        return True


class FileOperationService(PathService):

    def open_version(self, version_name):
        path = self.version_path(version_name)
        return file_ops.open_file(path)

    def import_version(self, version_name, namespace=None):
        path = self.version_path(version_name)
        return file_ops.import_file(path, namespace=namespace)

    def reference_version(self, version_name, namespace=None):
        path = self.version_path(version_name)
        if namespace is None:
            namespace = _u(version_name).split('.')[0]
        return file_ops.reference_file(path, namespace=namespace, group_locator=True)

    def open_master(self):
        return file_ops.open_master_file(
            self.pm, self.asset_type, self.asset, self.subtype
        )

    def import_master(self, namespace=None):
        return file_ops.import_master_file(
            self.pm, self.asset_type, self.asset, self.subtype, namespace=namespace
        )

    def reference_master(self, namespace=None):
        mf = self.pm.get_master_file(self.asset_type, self.asset, self.subtype)

        if not mf or not os.path.exists(mf):
            raise RuntimeError(u"Master file not found")

        if namespace is None:
            return file_ops.reference_file(mf, namespace=":", group_locator=True)
        else:
            return file_ops.reference_file(mf, namespace=namespace, group_locator=True)

    def set_master(self, version_name):
        return file_ops.set_master_from_version(
            self.pm, self.asset_type, self.asset, self.subtype, version_name
        )

    def write_note_info(self, subtype_name, version_filename, info="", workshop=True):
        task_dir = os.path.join(self.asset_dir(), 'components', subtype_name)
        self.pm.write_note_info(task_dir, version_filename, info, workshop)


class OpSkinWeight(PathService):

    def export_ng(self, *args):
        selected = cmds.ls(sl=1) or []
        _path = self.skin_dir()
        if not os.path.exists(_path):
            os.makedirs(_path)
        file_path = os.path.join(_path, '{}_ng.json'.format(selected[0]))
        export_to(file_path)

    # @undo
    def import_ng(self, mode=1, *ages):
        selected = cmds.ls(sl=1)
        if selected:
            _path = os.path.join(self.skin_dir(), '{}_ng.json'.format(selected[0]))
            import_from(file_path=_path, mode=mode)

    def open_sk_path(self):
        if os.path.exists(self.skin_dir()):
            open_folder_in_explorer(self.skin_dir().replace("/", "\\"))
        else:
            self.ui.show_warning(u'错误', u'任务路径不存在:\n{}'.format(self.skin_dir()))

class VersionContextMenu(PipelineContext):

    def __init__(self, main_window):
        super(VersionContextMenu, self).__init__(main_window)

        self.path_service = PathService(main_window)
        self.version_service = VersionService(main_window)
        self.exporter = FBXExporter(main_window)
        self.file_ops = FileOperationService(main_window)
        self.ng_ops = OpSkinWeight(main_window)

    def show_asset_menu(self, position):
        list_widget = self.ui.asset_list
        item = list_widget.itemAt(position)
        if not item:
            return
        asset_name = _u(item.text())
        menu = QtWidgets.QMenu(list_widget)

        open_path_action = menu.addAction(u"📂 打开资产目录")
        menu.addSeparator()
        add_menu_label(menu, u"color:")
        color_menu = menu.addMenu(u"🎨 设置标记")
        for label, color in _color_options:
            action = color_menu.addAction(label)
            action.triggered.connect(partial(self.ui._set_color, asset_name, color))

        def _open():
            self.path_service.open_asset_path(asset_name)

        open_path_action.triggered.connect(_open)
        menu.exec_(list_widget.mapToGlobal(position))

    def show_subtype_menu(self, position):
        list_widget = self.ui.subtype_list
        item = list_widget.itemAt(position)

        if not item:
            return

        subtype_name = _u(item.text())
        menu = QtWidgets.QMenu(list_widget)
        open_path_action = menu.addAction(u"📂 打开任务目录")
        add_menu_label(menu, u"color:")
        color_menu = menu.addMenu(u"🎨 设置标记")
        for label, color in _color_options:
            action = color_menu.addAction(label)
            action.triggered.connect(partial(self.ui._set_color, self.asset, color,
                                             subtype_name=subtype_name))

        menu.addSeparator()
        open_master_action = menu.addAction(u"打开 Master")
        import_master_action = menu.addAction(u"导入 Master")
        reference_master_action = menu.addAction(u"引用 Master")

        def safe_run(func):
            try:
                func()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self.ui, u"错误", _u(e))

        def _open():
            self.path_service.open_subtype_path(subtype_name)

        def _open_master():
            safe_run(lambda: self.file_ops.open_master())
            _show_info_inview(u'Master opened', 'yellow')

        def _import_master():
            safe_run(lambda: self.file_ops.import_master())
            _show_info_inview(u'Master imported', 'yellow')

        def _reference_master():
            safe_run(lambda: self.file_ops.reference_master())
            _show_info_inview(u'Master referenced', 'yellow')

        open_path_action.triggered.connect(_open)
        open_master_action.triggered.connect(_open_master)
        import_master_action.triggered.connect(_import_master)
        reference_master_action.triggered.connect(_reference_master)
        menu.exec_(list_widget.mapToGlobal(position))

    def show_version_menu(self, position):

        def safe_run(func):
            try:
                func()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self.ui, u"错误", _u(e))

        def _open():
            safe_run(lambda: self.file_ops.open_version(version_name))
            _show_info_inview(u'The selected version has been opened', 'yellow')

        def _import():
            safe_run(lambda: self.file_ops.import_version(version_name))
            _show_info_inview(u'The selected version has been imported', 'yellow')

        def _reference():
            ns = version_name.split('.')[0]
            safe_run(lambda: self.file_ops.reference_version(version_name, namespace=ns))
            _show_info_inview(u'The selected version has been reference', 'yellow')

        def _locate():
            safe_run(lambda: self.path_service.open_version_path(version_name))

        def _set_master():
            safe_run(lambda: self.file_ops.set_master(version_name))
            _show_info_inview(u'Master 设置成功', 'green')

        def _delete():
            ok = self.version_service.delete_selected_version(version_name)
            if ok:
                safe_run(lambda: self.file_ops.write_note_info(self.subtype, version_name, u"Delete", True))
            if ok and hasattr(self.ui, "refresh_all"):
                self.ui.refresh_all()

        def _export_ng():
            safe_run(lambda: self.ng_ops.export_ng())

        def _import_ng(mode=1):
            safe_run(lambda: self.ng_ops.import_ng(mode))

        list_widget = self.ui.version_list
        item = list_widget.itemAt(position)

        if item:
            version_name = _u(item.text())
            menu = QtWidgets.QMenu(list_widget)
            add_menu_label(menu, u'📋 版本信息: {}'.format(version_name))
            locate_action = menu.addAction(u"📂 打开版本路径")
            menu.addSeparator()
            open_action = menu.addAction(u" 打开")
            import_action = menu.addAction(u" 导入")
            reference_action = menu.addAction(u" 引用")
            menu.addSeparator()
            set_master_action = menu.addAction(u"⚙ Set Master ")
            menu.addSeparator()
            add_fbx_menu(menu, version_name, self.exporter, add_menu_label, safe_run)
            menu.addSeparator()
            add_menu_label(menu, u"  删除:")
            delete_action = menu.addAction(u"🗑️ 删除当前选择")
            open_action.triggered.connect(_open)
            import_action.triggered.connect(_import)
            reference_action.triggered.connect(_reference)
            locate_action.triggered.connect(_locate)
            set_master_action.triggered.connect(_set_master)
            delete_action.triggered.connect(_delete)
        else:
            menu = QtWidgets.QMenu()
            add_menu_label(menu, u'📋 功能区:', "red")
            set_fbx_action = menu.addAction(u'⚙ 设置FBX导出对象')
            menu.addSeparator()
            add_menu_label(menu, u'📤 导入导出对象: {} > ng'.format(self.subtype), "red")
            ng_exp_action = menu.addAction(u" 导出 ng")
            ng_imp_action1 = menu.addAction(u" closestPoint导入")
            ng_imp_action2 = menu.addAction(u" uvSpace导入")
            ng_imp_action3 = menu.addAction(u" vertexId导入")
            menu.addSeparator()
            ng_clean_action = menu.addAction(u" 清除场景ng节点")
            menu.addSeparator()
            sk_action = menu.addAction(u"📂 打开skin路径")
            if not self.subtype:
                [_i.setEnabled(False) for _i in [ng_exp_action, ng_imp_action1, ng_imp_action2, ng_imp_action3, sk_action]]
            set_fbx_action.triggered.connect(self.ui.set_fbx_export_objects)
            ng_exp_action.triggered.connect(_export_ng)
            ng_imp_action1.triggered.connect(lambda: _import_ng(1))
            ng_imp_action2.triggered.connect(lambda: _import_ng(2))
            ng_imp_action3.triggered.connect(lambda: _import_ng(3))
            ng_clean_action.triggered.connect(cleanup_scene_ng)
            sk_action.triggered.connect(self.ng_ops.open_sk_path)

        menu.exec_(list_widget.mapToGlobal(position))


def show_asset_context_menu(main_window, position):
    ctx = VersionContextMenu(main_window)
    ctx.show_asset_menu(position)


def show_subtype_context_menu(main_window, position):
    ctx = VersionContextMenu(main_window)
    ctx.show_subtype_menu(position)


def show_version_context_menu(main_window, position):
    ctx = VersionContextMenu(main_window)
    ctx.show_version_menu(position)


__all__ = [
    'show_asset_context_menu',
    'show_subtype_context_menu',
    'show_version_context_menu'
]
