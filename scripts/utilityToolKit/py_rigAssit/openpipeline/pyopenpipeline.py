# -*- coding: utf-8 -*-

# .FileName:pyopenpipeline.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2025/6/30 20:23
# .Finish time:

import os
import io
import json
import logging
import shutil
import errno
import xml.etree.ElementTree as ET
import xml.sax.saxutils
from datetime import datetime

try:
    import maya.cmds as cmds
    import maya.mel as mel
    IN_MAYA = True
except ImportError:
    cmds = None
    mel = None
    IN_MAYA = False

try:
    from importlib import reload
except ImportError:
    pass

from py_rigAssit.openpipeline import ui_openpipeline
reload(ui_openpipeline)

from .version_context import (show_asset_context_menu, show_subtype_context_menu, show_version_context_menu)
from .version import VERSION, TIMESTAMP
from .asset_info import PROJECTS_XML, ENABLE_DESC_TIP
from .ui_openpipeline import build_openpipeline_ui
from .description_manager import DescriptionMixin
from .snapshot_manager import SnapshotMixin
from Pipeline import file_operations as fops
from Pipeline.pipelineConfig import OpenPipelineConfig, DEFAULT_UE_CONFIG
from Pipeline.projectManager import ProjectManager
from Pipeline.pipelineUtils import (
    load_projects_from_xml, get_projects_xml_path, ensure_projects_xml,
    add_project_to_xml, open_folder_in_explorer, open_file_in_explorer
)
from .text_utils import _u
from ui_framework.core.qtCompat import *
from ui_framework.widgets.widgets import Widgets, PyouPersistentWindow

_widgets = Widgets()
logger = logging.getLogger(__name__)
UE_CONFIG = dict(DEFAULT_UE_CONFIG)
_USER_DEFINED_CANDIDATES = (
    "user_defined",
    "Pipeline.user_defined",
    "py_rigAssit.openpipeline.user_defined",
)


def _safe_makedirs(path):
    if not path:
        return
    try:
        os.makedirs(path)
    except OSError as e:
        if getattr(e, 'errno', None) == getattr(errno, 'EEXIST', 17):
            return
        if os.path.isdir(path):
            return
        raise


def _load_user_defined_module():
    import importlib
    for mod_path in _USER_DEFINED_CANDIDATES:
        try:
            mod = importlib.import_module(mod_path)
            if hasattr(mod, "set_value"):
                return mod
        except Exception:
            continue
    return None


def _load_version_format_from_user_defined():
    mod = _load_user_defined_module()
    if mod is not None and hasattr(mod, "get_version_format"):
        try:
            return mod.get_version_format()
        except Exception:
            pass
    return "new"


def _save_version_format_to_user_defined(fmt):
    mod = _load_user_defined_module()
    if mod is None or not hasattr(mod, "set_value"):
        return False
    try:
        mod.set_value("version_format", fmt)
        return True
    except Exception:
        return False




class FbxConfigMixin(object):
    """职责 mixin：FbxConfigMixin。所有状态经 self 共享。"""

    # ---------------- FBX 配置 ----------------
    def load_fbx_config(self):
        try:
            self.fbx_config = self.cfg.get_fbx_export_info()
            if not self.fbx_config:
                self.fbx_config = ['Geo_grp', 'root_jnt']
                self.save_fbx_config(self.fbx_config)
            self.UE_CONFIG = self.cfg.get_ue_config()
            UE_CONFIG.clear()
            UE_CONFIG.update(self.UE_CONFIG)
        except Exception as e:
            logger.warning(u"加载FBX配置失败: %s", _u(e))

    def save_fbx_config(self, fbx_export):
        try:
            self.cfg.set_fbx_export_info(fbx_export)
        except Exception as e:
            logger.warning(u"保存FBX配置失败: %s", _u(e))

    def save_ue_config(self, ue_config):
        """保存 Unreal Engine 导出配置，并同步运行时 UE_CONFIG。"""
        try:
            self.UE_CONFIG = self.cfg.get_ue_config()
            self.UE_CONFIG.update(ue_config)
            UE_CONFIG.clear()
            UE_CONFIG.update(self.UE_CONFIG)
            self.cfg.set_ue_config(self.UE_CONFIG)
        except Exception as e:
            logger.warning(u"保存UE配置失败: %s", _u(e))

    def set_fbx_export_objects(self):
        from py_rigAssit.openpipeline.fbx_dialog import FBXExportDialog

        if hasattr(self, '_fbx_dialog') and self._fbx_dialog:
            self._fbx_dialog.raise_()
            self._fbx_dialog.activateWindow()
            return

        dialog = FBXExportDialog(
            parent=self,
            fbx_config=self.fbx_config,
            ue_config=self.UE_CONFIG
        )
        dialog.setWindowFlags(QtCore.Qt.Window)
        self._fbx_dialog = dialog

        dialog.accepted.connect(lambda: self._on_fbx_dialog_accepted(dialog))
        dialog.rejected.connect(lambda: setattr(self, '_fbx_dialog', None))
        dialog.finished.connect(lambda: setattr(self, '_fbx_dialog', None))

        dialog.show()

    def _on_fbx_dialog_accepted(self, dialog):
        new_settings = dialog.get_settings()
        new_ue_settings = dialog.get_ue_settings()
        if new_settings[0] and new_settings[1]:
            self.fbx_config = new_settings
            self.save_fbx_config(self.fbx_config)
        self.save_ue_config(new_ue_settings)
        self.show_info_inview(u'FBX/UE 导出设置已保存', 'green')
        self._fbx_dialog = None



class ProjectMixin(object):
    """职责 mixin：ProjectMixin。所有状态经 self 共享。"""

    def update_root_path_label(self):
        root_path = self.cfg.get_project_root_path()
        if root_path:
            normalized_path = _u(root_path).replace('\\', '/')
            self.root_path_label.setText(normalized_path)
            self.root_path_label.setToolTip(normalized_path)
        else:
            self.root_path_label.setText(u'未设置')
            self.root_path_label.setToolTip('')

    def check_config(self):
        try:
            config_file = self.cfg.get_config_file_path()
            config_exists = os.path.exists(config_file)
            config_content = u"配置文件不存在"
            if config_exists:
                try:
                    with io.open(config_file, 'r', encoding='utf-8') as f:
                        config_content = json.load(f)
                except Exception:
                    try:
                        with io.open(config_file, 'r', encoding='utf-8', errors='replace') as f:
                            config_content = json.load(f)
                    except Exception as e:
                        config_content = u"读取配置文件失败: {}".format(_u(e))

            if isinstance(config_content, dict):
                content_str = _u(json.dumps(config_content, indent=4, ensure_ascii=False))
            else:
                content_str = _u(config_content)

            message = u"配置文件路径: {}\n".format(_u(config_file))
            message += u"配置文件存在: {}\n".format(config_exists)
            message += u"项目根路径: {}\n".format(_u(self.cfg.get_project_root_path()))
            message += u"上次选择的项目: {}\n".format(_u(self.cfg.get_last_project()))
            message += u"配置文件内容:\n{}\n".format(content_str)
            self.show_info(u'配置检查', message)
        except Exception as e:
            self.show_warning(u'错误', u"检查配置时出错: {}".format(_u(e)))

    def set_project_root_path(self):
        current_root = self.cfg.get_project_root_path()
        start_dir = current_root if current_root else ''
        root_path = QtWidgets.QFileDialog.getExistingDirectory(self, u'选择项目根路径', start_dir)
        if root_path:
            normalized_path = _u(root_path).replace('\\', '/')
            success = self.cfg.set_project_root_path(normalized_path)
            if success:
                self.cfg = OpenPipelineConfig()
            else:
                self.show_warning(u'错误', u'保存配置失败，请检查文件权限')
                return

            self.update_root_path_label()
            xml_path = os.path.join(normalized_path, PROJECTS_XML)
            if os.path.exists(xml_path):
                try:
                    self.load_projects()
                except Exception as e:
                    self.show_warning(u'错误', u'加载项目配置文件失败:\n{}'.format(_u(e)))
            else:
                reply = QtWidgets.QMessageBox.question(self, u'未找到项目配置文件',
                                                       u'在{path}中未找到{PROJECTS_XML}文件，是否创建新的项目配置文件？'.format(
                                                           path=_u(normalized_path), PROJECTS_XML=PROJECTS_XML),
                                                       QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.Yes:
                    ensure_projects_xml(self.cfg)
                    self.load_projects()

    def check_projects_in_root(self):
        root_path = self.cfg.get_project_root_path()
        if not root_path:
            self.show_warning(u'提示', u'请先设置项目根路径')
            return

        xml_path = os.path.join(root_path, PROJECTS_XML)
        if not os.path.exists(xml_path):
            self.show_info(u'检查结果',
                           u'在{path}中未找到{PROJECTS_XML}文件'.format(
                               path=_u(root_path), PROJECTS_XML=PROJECTS_XML))
            return

        projects = load_projects_from_xml(self.cfg)
        missing_projects = []
        valid_projects = []

        for name, path in projects.items():
            if os.path.exists(path):
                valid_projects.append(u'✓ {name}: {path}'.format(name=_u(name), path=_u(path)))
            else:
                missing_projects.append(u'✗ {name}: {path} (路径不存在)'.format(name=_u(name), path=_u(path)))

        message = u'项目根路径: {root_path}\n'.format(root_path=_u(root_path))
        message += u'XML文件: {xml_path}\n'.format(xml_path=_u(xml_path))
        message += u'找到 {count} 个项目定义\n\n'.format(count=len(projects))

        if valid_projects:
            message += u'有效项目 ({count}个):\n'.format(count=len(valid_projects))
            message += '\n'.join(valid_projects) + u'\n\n'
        else:
            message += u'无有效项目\n\n'

        if missing_projects:
            message += u'无效项目 ({count}个):\n'.format(count=len(missing_projects))
            message += '\n'.join(missing_projects)

        self.show_info(u'项目检查结果', message)

    def load_projects(self):
        self.project_combo.clear()
        self.project_combo.addItem('', '')

        root_path = self.cfg.get_project_root_path()
        if not root_path:
            self.project_combo.addItem(u'请先设置项目根路径', '')
            return

        xml_projects = load_projects_from_xml(self.cfg)
        if not xml_projects:
            self.project_combo.addItem(u'没有找到项目', '')
            return

        for name, path in xml_projects.items():
            self.project_combo.addItem(_u(name), _u(path))

    def select_last_project(self):
        last_project_path, last_assetType, last_asset = self.cfg.get_last_info(self.maya_version)

        if last_project_path:
            normalized_last_path = _u(last_project_path).replace('\\', '/').rstrip('/')

            for i in range(self.project_combo.count()):
                item_data = self.project_combo.itemData(i)
                if item_data:
                    normalized_item_data = _u(item_data).replace('\\', '/').rstrip('/')
                    if normalized_item_data == normalized_last_path:
                        self.project_combo.blockSignals(True)
                        try:
                            self.project_combo.setCurrentIndex(i)
                        finally:
                            self.project_combo.blockSignals(False)
                        self.on_project_changed(_u(self.project_combo.itemText(i)))
                        self._select_last_type_and_asset(last_assetType, last_asset)
                        break

    def _select_last_type_and_asset(self, last_assetType, last_asset):
        if last_assetType:
            for t in range(self.type_combo.count()):
                type_text = self.type_combo.itemText(t)
                if type_text == _u(last_assetType):
                    self.type_combo.blockSignals(True)
                    try:
                        self.type_combo.setCurrentIndex(t)
                    finally:
                        self.type_combo.blockSignals(False)
                    self.on_asset_type_changed(_u(self.type_combo.itemText(t)))
                    self._select_last_asset(last_asset)
                    break

    def _select_last_asset(self, last_asset):
        if last_asset:
            for a in range(self.asset_list.count()):
                item = self.asset_list.item(a)
                if item and item.text() == _u(last_asset):
                    self.asset_list.blockSignals(True)
                    try:
                        self.asset_list.setCurrentRow(a)
                    finally:
                        self.asset_list.blockSignals(False)
                    self.on_asset_clicked(item)
                    break

    def on_project_changed(self, text):
        if not text or text == u'-- 选择项目 --' or text == u'请先设置项目根路径' or text == u'没有找到项目':
            self.pm = None
            self.current_project_path = u''
            self.current_project_name = u''
            self.btn_create_asset.setEnabled(False)
            self.btn_delete_asset.setEnabled(False)
            self.btn_delete_asset.setVisible(False)
            self.btn_add_sub.setEnabled(False)
            self.btn_del_sub.setEnabled(False)
            self.btn_rename_sub.setEnabled(False)
            self.btn_snapshot.setEnabled(False)
            self.btn_snapshot_direct.setEnabled(False)
            self._reset_selection()
            self.type_combo.clear()
            return

        path = self.project_combo.currentData()
        if path:
            normalized_path = _u(path).replace('\\', '/')
            if os.path.exists(normalized_path):
                self._reset_selection()
                self.current_project_path = normalized_path
                self.current_project_name = _u(text)
                self.cfg.update_last_info(self.maya_version, project=normalized_path)
                lib = self.get_library_folder_from_xml(text)
                self.pm = ProjectManager(normalized_path, _u(text), lib)
                self.update_asset_type_combo()
                self.btn_create_asset.setEnabled(True)
                self.btn_add_sub.setEnabled(False)
                self.btn_del_sub.setEnabled(False)
                self.btn_rename_sub.setEnabled(False)
                self.btn_snapshot.setEnabled(False)
                self.btn_snapshot_direct.setEnabled(False)
                self.cfg.add_project_path(normalized_path)
                self.load_assets()
            else:
                self.show_warning(u'错误',
                                  u'项目路径不存在:\n{path}\n\n请检查项目是否被移动或删除。'.format(
                                      path=_u(normalized_path)))

    def get_library_folder_from_xml(self, project_name):
        xml_path = get_projects_xml_path(self.cfg)
        if not xml_path or not os.path.exists(xml_path):
            return self.cfg.config.get('library_folder', 'lib')

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for proj in root.findall('project'):
                name_elem = proj.find('name')
                if name_elem is not None and name_elem.text == _u(project_name):
                    lf_elem = proj.find('libraryfolder')
                    if lf_elem is not None and lf_elem.text:
                        return _u(lf_elem.text)
        except Exception as e:
            logger.warning(u"从XML读取library_folder失败: %s", _u(e))

        return self.cfg.config.get('library_folder', 'lib')

    def open_existing_project(self):
        root_path = self.cfg.get_project_root_path()
        if not root_path:
            self.show_warning(u'提示', u'请先设置项目根路径')
            return

        project_dir = QtWidgets.QFileDialog.getExistingDirectory(self, u'选择项目文件夹', root_path)
        if project_dir:
            normalized_dir = _u(project_dir).replace('\\', '/')
            if not normalized_dir.startswith(_u(root_path).replace('\\', '/')):
                self.show_warning(u'错误',
                                  u'选择的项目不在项目根路径下:\n\n项目根路径: {root}\n项目路径: {project}'.format(
                                      root=_u(root_path), project=_u(normalized_dir)))
                return

            project_name = os.path.basename(normalized_dir.rstrip('/'))
            xml_projects = load_projects_from_xml(self.cfg)

            if project_name in xml_projects:
                idx = self.project_combo.findText(_u(project_name))
                if idx >= 0:
                    self.project_combo.setCurrentIndex(idx)
            else:
                reply = QtWidgets.QMessageBox.question(self, u'项目未注册',
                                                       u'项目"{name}"未在系统中注册，是否现在注册？'.format(
                                                           name=_u(project_name)),
                                                       QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.Yes:
                    if not normalized_dir.endswith('/'):
                        normalized_dir = normalized_dir + '/'

                    add_project_to_xml(self.cfg, _u(project_name), _u(normalized_dir))
                    self.load_projects()
                    idx = self.project_combo.findText(_u(project_name))
                    if idx >= 0:
                        self.project_combo.setCurrentIndex(idx)

    def create_project_dialog(self):
        root_path = self.cfg.get_project_root_path()
        if not root_path:
            self.show_warning(u'提示', u'请先设置项目根路径')
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(u'创建项目')
        dlg.setFixedSize(420, 180)
        lay = QtWidgets.QVBoxLayout()
        lay.addWidget(_widgets.create_text(u'输入项目名称'))
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel(u'项目名称:'))
        self.new_proj_name = QtWidgets.QLineEdit()
        row1.addWidget(self.new_proj_name)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel(u'项目根路径:'))
        self.new_proj_path = QtWidgets.QLabel(_u(root_path))
        self.new_proj_path.setStyleSheet('background: gray; padding:4px; color: black; border:1px solid #ccc;')
        row2.addWidget(self.new_proj_path, 1)

        row3 = QtWidgets.QHBoxLayout()
        row3.addWidget(QtWidgets.QLabel(u'库文件夹:'))
        self.new_proj_lib = QtWidgets.QLineEdit()
        self.new_proj_lib.setText(self.cfg.config.get('library_folder', 'lib'))
        self.new_proj_lib.setEnabled(False)
        row3.addWidget(self.new_proj_lib)

        btn_row = QtWidgets.QHBoxLayout()
        ok = QtWidgets.QPushButton(u'创建')
        ok.clicked.connect(lambda: self._create_project(dlg))
        cancel = QtWidgets.QPushButton(u'取消')
        cancel.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)

        lay.addLayout(row1)
        lay.addLayout(row2)
        lay.addLayout(row3)
        lay.addLayout(btn_row)
        dlg.setLayout(lay)
        dlg.exec_()

    def _create_project(self, dlg):
        name = _u(self.new_proj_name.text().strip())
        root_path = self.cfg.get_project_root_path()
        lib = _u(self.new_proj_lib.text().strip())
        if not name:
            self.show_warning(u'错误', u'请填写项目名称')
            return

        if not lib:
            lib = 'lib'
        project_root = os.path.join(root_path, name)
        project_root = project_root.replace('\\', '/')
        if not project_root.endswith('/'):
            project_root = project_root + '/'
        xml_projects = load_projects_from_xml(self.cfg)
        if name in xml_projects:
            self.show_warning(u'错误', u'项目"{name}"已存在'.format(name=name))
            return
        project_dir = project_root.rstrip('/')
        if os.path.exists(project_dir):
            reply = QtWidgets.QMessageBox.question(
                self, u'文件夹已存在',
                u'文件夹"{name}"已存在于项目根路径下，是否继续？'.format(name=name),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return
        _safe_makedirs(project_dir)
        _safe_makedirs(os.path.join(project_dir, lib))
        ensure_projects_xml(self.cfg)
        add_project_to_xml(self.cfg, name, project_root, libraryfolder=lib)
        self.cfg.add_project_path(project_root)
        self.load_projects()
        idx = self.project_combo.findText(name)
        if idx >= 0:
            self.project_combo.setCurrentIndex(idx)
        dlg.accept()
        self.show_info_inview(u'项目已创建', 'green')

    def get_current_asset_types(self):
        asset_types = []
        if not self.pm:
            return asset_types

        try:
            lib_path = os.path.join(self.pm.project_root, self.pm.library_folder)
            if os.path.exists(lib_path):
                for item in os.listdir(lib_path):
                    item_path = os.path.join(lib_path, item)
                    if os.path.isdir(item_path):
                        asset_types.append(_u(item))
                asset_types.sort()
        except Exception as e:
            logger.warning(u"获取资产类型失败: %s", _u(e))

        return asset_types

    def update_asset_type_combo(self):
        self.type_combo.clear()
        if not self.pm:
            return

        asset_types = self.get_current_asset_types()
        if asset_types:
            for asset_type in asset_types:
                self.type_combo.addItem(asset_type, asset_type)
            if asset_types:
                self.current_asset_type = asset_types[0]
        else:
            self.type_combo.addItem(u'暂无资产类型')
            self.current_asset_type = ''

    def add_asset_type(self):
        if not self.pm:
            self.show_warning(u'错误', u'请先选择项目')
            return

        text, ok = QtWidgets.QInputDialog.getText(self, u'添加资产类型', u'输入资产类型名称:')
        if ok and text.strip():
            t = _u(text.strip())
            existing_types = self.get_current_asset_types()
            if t in existing_types:
                self.show_warning(u'提示', u'资产类型 {t} 已存在'.format(t=t))
                return

            try:
                lib_path = os.path.join(self.pm.project_root, self.pm.library_folder)
                new_type_path = os.path.join(lib_path, t)
                if not os.path.exists(lib_path):
                    os.makedirs(lib_path)
                os.makedirs(new_type_path)
                self.update_asset_type_combo()
                index = self.type_combo.findText(t)
                if index >= 0:
                    self.type_combo.setCurrentIndex(index)
                self.show_info_inview(u'资产类型已添加', 'green')
            except Exception as e:
                self.show_warning(u'错误', u'创建资产类型失败: {error}'.format(error=_u(e)))

    def delete_asset_type(self):
        if not self.pm:
            self.show_warning(u'错误', u'请先选择项目')
            return

        current_type = self.type_combo.currentText()
        if not current_type or current_type == u'暂无资产类型':
            self.show_warning(u'提示', u'请先选择一个资产类型')
            return

        lib_path = os.path.join(self.pm.project_root, self.pm.library_folder)
        type_path = os.path.join(lib_path, current_type)

        if not os.path.exists(type_path):
            self.show_warning(u'错误', u'资产类型文件夹不存在')
            return

        try:
            items = os.listdir(type_path)
            if items:
                reply = QtWidgets.QMessageBox.question(
                    self, u'确认删除',
                    u'资产类型 "{current_type}" 文件夹不为空，包含 {count} 个文件/文件夹。确定要删除吗？'.format(
                        current_type=_u(current_type), count=len(items)),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if reply != QtWidgets.QMessageBox.Yes:
                    return
        except Exception:
            pass

        reply = QtWidgets.QMessageBox.question(
            self, u'确认删除',
            u'确定要删除资产类型 "{current_type}" 吗？此操作不可撤销。'.format(
                current_type=_u(current_type)),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                shutil.rmtree(type_path)
                self.update_asset_type_combo()
                self.asset_list.clear()
                self.subtype_list.clear()
                self.clear_right()
                self.show_info_inview(u'资产类型已删除', 'green')
            except Exception as e:
                self.show_warning(u'错误', u'删除失败: {error}'.format(error=_u(e)))



class AssetMixin(object):
    """职责 mixin：AssetMixin。所有状态经 self 共享。"""

    def on_asset_sort_changed(self, index):
        self.load_assets(index)

    def _get_color_file_path(self, asset_name, subtype_name=None):
        if not self.pm or not self.current_asset_type or not asset_name:
            return None
        asset_dir = self.pm.get_asset_dir(self.current_asset_type, asset_name)
        if subtype_name:
            color_file = os.path.join(asset_dir, 'components', subtype_name, '.color')
        else:
            color_file = os.path.join(asset_dir, '.color')
        return color_file

    def _get_color(self, asset_name, subtype_name=None):
        color_file = self._get_color_file_path(asset_name, subtype_name)
        exists, content = self._read_asset_text(color_file)
        if exists:
            color = _u(content).strip().lower()
            if color in ('red', 'yellow', 'blue', 'green'):
                return color
        return None

    def _set_color(self, asset_name, color, subtype_name=None):
        if not self.pm or not self.current_asset_type or not asset_name:
            return
        color_file = self._get_color_file_path(asset_name, subtype_name)
        if not color_file:
            return
        dir_path = os.path.dirname(color_file)
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except Exception:
                return
        if color and color in ('red', 'yellow', 'blue', 'green'):
            try:
                with io.open(color_file, 'w', encoding='utf-8') as f:
                    f.write(_u(color))
                self._set_asset_text_cache(color_file, True, _u(color))
            except Exception:
                self._invalidate_asset_text(color_file)
        else:
            if os.path.exists(color_file):
                try:
                    os.remove(color_file)
                except Exception:
                    pass
            self._invalidate_asset_text(color_file)
        self._update_item_color(asset_name, subtype_name)

    def _update_item_color(self, asset_name, subtype_name=None):
        if subtype_name:
            for i in range(self.subtype_list.count()):
                item = self.subtype_list.item(i)
                if item.text() == subtype_name:
                    color = self._get_color(asset_name, subtype_name)
                    if color and color in self.COLOR_MAP:
                        item.setForeground(self.COLOR_MAP[color])
                    else:
                        item.setForeground(QtGui.QColor("#e0e0e0"))
                    break
        else:
            for i in range(self.asset_list.count()):
                item = self.asset_list.item(i)
                if item.text() == asset_name:
                    color = self._get_color(asset_name)
                    if color and color in self.COLOR_MAP:
                        item.setForeground(self.COLOR_MAP[color])
                    else:
                        item.setForeground(QtGui.QColor("#e0e0e0"))
                    break

    def load_assets(self, sort_mode=1, *args):
        self.asset_list.clear()
        self.subtype_list.clear()
        self.clear_right()
        if not self.pm or not self.current_asset_type:
            return

        assets = self.pm.list_assets(self.current_asset_type)
        if not assets:
            return

        if sort_mode == 2:
            asset_with_time = []
            for asset in assets:
                asset_path = self.pm.get_asset_dir(self.current_asset_type, asset)
                mtime = os.path.getmtime(asset_path) if os.path.exists(asset_path) else 0
                asset_with_time.append((asset, mtime))
            asset_with_time.sort(key=lambda x: x[1], reverse=True)
            sorted_assets = [item[0] for item in asset_with_time]
        else:
            sorted_assets = sorted(assets)

        for asset in sorted_assets:
            item = QtWidgets.QListWidgetItem(_u(asset))
            color = self._get_color(asset)
            if color and color in self.COLOR_MAP:
                item.setForeground(self.COLOR_MAP[color])
            self.asset_list.addItem(item)
        self.asset_count.setText(u"{}".format(len(sorted_assets)))
        if ENABLE_DESC_TIP:
            self.update_asset_tooltips()

    def on_asset_type_changed(self, text):
        if not text or text == u'暂无资产类型':
            self.current_asset_type = ''
            self._reset_selection()
            self.btn_delete_asset.setEnabled(False)
            self.btn_delete_asset.setVisible(False)
            return

        self._reset_selection()
        self.current_asset_type = _u(text)
        self.load_assets()
        self.btn_delete_asset.setEnabled(False)
        self.btn_delete_asset.setVisible(False)
        self.cfg.update_last_info(self.maya_version, asset_type=self.current_asset_type)

    def filter_assets(self, text):
        text = _u(text).lower()
        for i in range(self.asset_list.count()):
            it = self.asset_list.item(i)
            it.setHidden(text not in _u(it.text()).lower())

    def create_asset_dialog(self):
        if not self.pm or not self.current_asset_type:
            self.show_warning(u'提示', u'请先选择有效的资产类型')
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(u'创建资产')
        dlg.setFixedSize(320, 150)
        lay = QtWidgets.QVBoxLayout()

        r_name = QtWidgets.QHBoxLayout()
        r_name.addWidget(_widgets.create_text(u'名称:'))
        self.new_asset_name = QtWidgets.QLineEdit()
        r_name.addWidget(self.new_asset_name)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(_widgets.create_text(u'级别:'))
        self.new_asset_level = QtWidgets.QComboBox()
        self.new_asset_level.setEditable(True)
        self.new_asset_level.addItems(['No', 'S', 'A', 'B', 'C', 'D'])
        self.new_asset_level.setFixedWidth(60)
        self.new_asset_level.setCurrentText('No')
        btn_row.addWidget(self.new_asset_level)

        ok = QtWidgets.QPushButton(u' 创建 ')
        ok.clicked.connect(lambda: self._create_asset(dlg))
        cancel = QtWidgets.QPushButton(u' 取消 ')
        cancel.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)

        lay.addLayout(r_name)
        lay.addLayout(btn_row)
        dlg.setLayout(lay)
        dlg.exec_()

    def _get_asset_level(self, asset_type, asset_name):
        return self.pm.get_asset_level(asset_type, asset_name)

    def _create_asset(self, dlg):
        name = _u(self.new_asset_name.text().strip())
        level = _u(self.new_asset_level.currentText().strip())
        self.btn_delete_asset.setEnabled(False)
        self.btn_delete_asset.setVisible(False)
        if not name:
            self.show_warning(u'错误', u'请输入资产名称')
            return
        if self.pm.create_asset(self.current_asset_type, name, level):
            dlg.accept()
            self.load_assets()
            self.show_info_inview(u'资产已创建', 'green')
        else:
            self.show_warning(u'失败', u'资产已存在或创建失败')

    def delete_asset_dialog(self):
        if not self.pm or not self.current_asset_type:
            self.show_warning(u'错误', u'请先选择项目及资产类型')
            return

        if not self.selected_asset:
            self.show_warning(u'错误', u'请先选择要删除的资产')
            return

        asset_dir = self.pm.get_asset_dir(self.current_asset_type, self.selected_asset)
        if not os.path.exists(asset_dir):
            self.show_warning(u'错误', u'资产路径不存在:\n{}'.format(_u(asset_dir)))
            return

        try:
            item_count = 0
            asset_size = 0
            for root, dirs, files in os.walk(asset_dir):
                item_count += len(dirs) + len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        asset_size += os.path.getsize(file_path)
                    except Exception:
                        pass

            asset_size_mb = asset_size / (1024.0 * 1024.0)
            confirm_msg = u'确定要删除资产 "{asset_name}" 吗？\n\n'.format(asset_name=_u(self.selected_asset))
            confirm_msg += u'资产类型: {asset_type}\n'.format(asset_type=_u(self.current_asset_type))
            confirm_msg += u'资产路径: {asset_path}\n'.format(asset_path=_u(asset_dir))
            confirm_msg += u'包含内容: {count} 个文件/文件夹\n'.format(count=item_count)
            confirm_msg += u'总大小: {size:.2f} MB\n\n'.format(size=asset_size_mb)
            confirm_msg += u'警告: 此操作不可逆！所有相关的子类型、版本、预览图等都会被永久删除。'

            reply = QtWidgets.QMessageBox.question(
                self,
                u'确认删除资产',
                confirm_msg,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                success, message = self._delete_asset(asset_dir)
                if success:
                    self.show_info_inview(u'资产已删除', 'green')
                    self.load_assets()
                    self.clear_right()
                    self.selected_asset = None
                    self.selected_subtype = None
                    self.info_label.setText(u'未选择资产')
                else:
                    self.show_warning(u'删除失败', message)
        except Exception as e:
            self.show_warning(u'错误', u'检查资产信息时出错:\n{}'.format(_u(e)))

    def _delete_asset(self, asset_dir):
        try:
            if not os.path.exists(asset_dir):
                return False, u'资产文件夹不存在'
            shutil.rmtree(asset_dir)
            if os.path.exists(asset_dir):
                return False, u'资产删除失败，文件夹仍然存在'
            return True, u'资产已成功删除'
        except OSError as e:
            return False, u'操作系统错误: {}'.format(_u(e))
        except Exception as e:
            return False, u'删除过程中发生错误: {}'.format(_u(e))

    def show_asset_preview(self, asset_type, asset):
        """兼容旧调用，统一走 _load_preview。"""
        self._load_preview(asset_type=asset_type, asset=asset, subtype=None)

    def on_asset_clicked(self, item):
        self.selected_asset = _u(item.text())
        self.selected_subtype = None
        level = self._get_asset_level(self.current_asset_type, self.selected_asset)
        level_display = level if level else 'No'
        display_text = u'资产: {level} > {asset}'.format(level=_u(level_display), asset=_u(self.selected_asset))
        self.info_label.setText(display_text)
        self.load_subtypes()
        self.btn_delete_asset.setEnabled(True)
        self.btn_delete_asset.setVisible(True)
        self.btn_add_sub.setEnabled(True)
        self.btn_del_sub.setEnabled(False)
        self.btn_rename_sub.setEnabled(False)
        self.btn_snapshot.setEnabled(True)
        self.btn_snapshot_direct.setEnabled(True)
        self.show_asset_preview(self.current_asset_type, self.selected_asset)
        self.clear_right()
        self.show_version_count(0)
        self.cfg.update_last_info(self.maya_version, asset=self.selected_asset)
        self.load_description()

    def load_subtypes(self):
        self.subtype_list.clear()
        if not (self.pm and self.selected_asset):
            return
        subs = self.pm.list_subtypes(self.current_asset_type, self.selected_asset)
        if subs:
            for sub in subs:
                item = QtWidgets.QListWidgetItem(_u(sub))
                color = self._get_color(self.selected_asset, subtype_name=sub)
                if color and color in self.COLOR_MAP:
                    item.setForeground(self.COLOR_MAP[color])
                self.subtype_list.addItem(item)

    def add_subtype_dialog(self):
        if not (self.pm and self.selected_asset):
            self.show_warning(u'提示', u'请先选择资产')
            return
        text, ok = QtWidgets.QInputDialog.getText(self, u'添加子类型', u'输入子类型名称:')
        if ok and text.strip():
            if self.pm.create_subtype(self.current_asset_type, self.selected_asset, _u(text.strip())):
                self.show_info_inview(u'子类型创建成功', 'green')
                self.load_subtypes()
            else:
                self.show_warning(u'失败', u'创建失败或已存在')

    def delete_subtype(self):
        if not (self.pm and self.selected_asset):
            self.show_warning(u'提示', u'请先选择资产')
            return

        sub = self.selected_subtype
        if not sub:
            self.show_warning(u'提示', u'请先选择一个任务/子类型')
            return

        p = os.path.join(self.pm.get_asset_dir(self.current_asset_type, self.selected_asset),
                         'components', sub)
        if not os.path.isdir(p):
            self.show_warning(u'失败', u'找不到该子类型: {}'.format(_u(p)))
            return

        confirm_msg = (u'将删除任务 "{sub}" 及其全部内容:\n{path}\n\n'
                       u'此操作不可撤销，版本、备注和预览图都会被删除。是否继续？').format(
            sub=_u(sub), path=_u(p))
        reply = QtWidgets.QMessageBox.question(
            self, u'确认删除任务', confirm_msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            shutil.rmtree(p)
        except Exception as e:
            self.show_warning(u'删除失败', u'删除失败: {error}'.format(error=_u(e)))
            return

        self.selected_subtype = None
        self.info_label.setText(u'选中: {asset}'.format(asset=_u(self.selected_asset)))
        self.load_subtypes()
        self._refresh_versions()
        self.show_info_inview(u'子类型已删除', 'green')

    def rename_subtype(self):
        if not (self.pm and self.selected_asset and self.selected_subtype):
            self.show_warning(u'提示', u'请先选择资产和子类型')
            return

        new_name, ok = QtWidgets.QInputDialog.getText(
            self, u'重命名子类型',
            u'重命名 "{old}" 为:'.format(old=_u(self.selected_subtype)),
            text=self.selected_subtype)

        if ok and new_name.strip():
            new_name = _u(new_name.strip())
            if new_name == self.selected_subtype:
                self.show_warning(u'提示', u'新名称与当前名称相同')
                return

            existing_subs = self.pm.list_subtypes(self.current_asset_type, self.selected_asset)
            if new_name in existing_subs:
                self.show_warning(u'失败', u'子类型 "{new_name}" 已存在'.format(new_name=new_name))
                return

            success, message = self.pm.rename_subtype(
                self.current_asset_type,
                self.selected_asset,
                self.selected_subtype,
                new_name
            )

            if success:
                self.show_info_inview(u'子类型已重命名', 'green')
                self.load_subtypes()
                self.selected_subtype = new_name
            else:
                self.show_warning(u'失败', message)



class VersionMixin(object):
    """职责 mixin：VersionMixin。所有状态经 self 共享。"""

    def _refresh_versions(self):
        """按当前资产/任务刷新版本列表、备注、计数、按钮状态和预览图。"""
        if not (getattr(self, 'pm', None) and self.selected_asset and self.selected_subtype):
            self.version_list.clear()
            self.show_version_count(0)
            self.notes_text.clear()
            for btn in (self.btn_save_new_version, self.btn_set_master,
                        self.btn_snapshot, self.btn_snapshot_direct,
                        self.btn_del_sub, self.btn_rename_sub):
                btn.setEnabled(False)
            self.btn_save_new_version.setStyleSheet("color: gray;")
            self.btn_set_master.setStyleSheet("color: gray;")
            self._load_preview(subtype=None)
            return

        versions = self.pm.get_workshop_versions(
            self.current_asset_type, self.selected_asset, self.selected_subtype)
        self.version_list.clear()
        for v in versions:
            self.version_list.addItem(_u(v))

        self.show_version_count(len(versions))
        notes = self.pm.get_notes(
            self.current_asset_type, self.selected_asset, self.selected_subtype)
        self.notes_text.setHtml(self.format_notes_text(notes))

        self.btn_save_new_version.setEnabled(True)
        self.btn_save_new_version.setStyleSheet("color: green;")
        self.btn_set_master.setEnabled(bool(versions))
        self.btn_set_master.setStyleSheet("color: red;")
        self.btn_snapshot.setEnabled(True)
        self.btn_snapshot_direct.setEnabled(True)
        self.btn_del_sub.setEnabled(True)
        self.btn_rename_sub.setEnabled(True)

        self._load_preview(subtype=self.selected_subtype)

    def format_notes_text(self, text):
        if not text:
            return u""
        text = _u(text)

        lines = text.splitlines()
        html_parts = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(u"[MASTER SET]"):
                color = u"yellow"
            elif stripped.startswith(u"Note: Delete"):
                color = u"#e68b86"
            elif stripped.startswith(u"Note:"):
                color = u"#80fcca"
            else:
                color = u"#abc4d2"
            escaped = _u(xml.sax.saxutils.escape(_u(line)))
            html_parts.append(u'<span style="color:{};">{}</span>'.format(color, escaped))
        return u"<br>".join(html_parts)

    def _load_preview(self, asset_type=None, asset=None, subtype=None):
        """加载预览图：优先任务目录，其次资产目录；按显示尺寸解码，避免全尺寸大图占双份内存。"""
        label = getattr(self, 'preview_label', None)
        if label is None:
            return

        asset_type = asset_type or self.current_asset_type
        asset = asset or self.selected_asset
        if not (getattr(self, 'pm', None) and asset_type and asset):
            label.clear()
            label.setText(u'No Preview')
            return

        base_dir = self.pm.get_asset_dir(asset_type, asset)
        search_dirs = []
        if subtype:
            search_dirs.append(os.path.join(base_dir, 'components', subtype))
        search_dirs.append(base_dir)

        for search_dir in search_dirs:
            for name in ('preview.png', 'preview.jpg'):
                path = os.path.join(search_dir, name)
                if not os.path.isfile(path):
                    continue

                pix = None
                try:
                    try:
                        target = label.contentsRect().size()
                    except Exception:
                        target = label.size()
                    reader = QtGui.QImageReader(path)
                    src_size = reader.size()
                    if (src_size.isValid() and src_size.width() > 0 and src_size.height() > 0
                            and target.width() > 0 and target.height() > 0):
                        factor = min(1.0,
                                     float(target.width()) / src_size.width(),
                                     float(target.height()) / src_size.height())
                        scaled = QtCore.QSize(max(1, int(src_size.width() * factor)),
                                              max(1, int(src_size.height() * factor)))
                        reader.setScaledSize(scaled)
                    image = reader.read()
                    if not image.isNull():
                        pix = QtGui.QPixmap.fromImage(image)
                except Exception:
                    pix = None

                if pix is None or (hasattr(pix, 'isNull') and pix.isNull()):
                    pix = QtGui.QPixmap(path)

                label.clear()
                label.setPixmap(pix)
                return

        label.clear()
        label.setText(u'No Preview')

    def on_subtype_clicked(self, item):
        st = _u(item.text())
        self.selected_subtype = st
        self.info_label.setText(u'选中: {asset}.{subtype}'.format(
            asset=_u(self.selected_asset), subtype=st))
        self._refresh_versions()

    def on_subtype_double_clicked(self, item):
        st = _u(item.text())
        self.selected_subtype = st
        latest = self.pm.get_latest_workshop(self.current_asset_type, self.selected_asset, st)
        if latest:
            if IN_MAYA:
                try:
                    fops.open_file(latest)
                    self.show_info_inview(u'The latest version has been opened', 'yellow')
                except Exception as e:
                    self.show_warning(u'错误', _u(e))
            else:
                self.show_info(u'打开', u'最新版本路径:\n' + _u(latest))
        else:
            self.show_warning(u'提示', u'未找到任何版本')

    def show_version_count(self, counts):
        if counts:
            self.version_count_text.setText(u"总数量: {}".format(counts))
        else:
            self.version_count_text.setText(u"")

    def open_selected_version(self):
        item = self.version_list.currentItem()
        if not item:
            latest = self.pm.get_latest_workshop(self.current_asset_type, self.selected_asset, self.selected_subtype)
            if latest:
                try:
                    fops.open_file(latest)
                    self.show_info_inview(u'The latest version has been opened', 'yellow')
                except Exception as e:
                    self.show_warning(u'失败', _u(e))
            else:
                self.show_warning(u'提示', u'没有可用的版本')
            return

        fname = _u(item.text())
        try:
            fops.open_latest_or_selected_version(
                self.pm, self.current_asset_type, self.selected_asset, self.selected_subtype, fname
            )
            self.show_info_inview(u'The version has been opened', 'yellow')
        except Exception as e:
            self.show_warning(u'失败', _u(e))

    def open_master(self):
        try:
            fops.open_master_file(self.pm, self.current_asset_type, self.selected_asset, self.selected_subtype)
            self.show_info_inview(u'Master has been opened', 'yellow')
        except Exception as e:
            self.show_warning(u'错误', _u(e))

    def reference_master(self, namespace=True):
        try:
            mf = self.pm.get_master_file(
                self.current_asset_type,
                self.selected_asset,
                self.selected_subtype
            )
            if not mf or not os.path.exists(mf):
                self.show_warning(u'错误', u'Master 文件不存在')
                return

            if namespace:
                ns = os.path.basename(mf).split(".")[0]
                fops.reference_file(mf, namespace=ns, group_locator=True)
            else:
                fops.reference_file(mf, namespace=":", group_locator=True)

            self.show_info_inview(u'Reference Master Finished')
        except Exception as e:
            self.show_warning(u'失败', _u(e))

    def save_new_version(self):
        if not (self.pm and self.selected_asset and self.selected_subtype):
            self.show_warning(u'提示', u'请先选择资产与子类型')
            return
        notes, ok = QtWidgets.QInputDialog.getText(self, u'保存新版本', u'输入版本备注:')
        if not ok:
            return
        try:
            if fops.save_workshop(None, _u(notes), self.pm, self.current_asset_type,
                                  self.selected_asset, self.selected_subtype):
                self.show_info_inview(u'The new version has been saved', 'green')
                self._refresh_versions()
            else:
                self.show_warning(u'失败', u'保存新版本失败')
        except Exception as e:
            self.show_warning(u'失败', _u(e))

    def save_new_master(self):
        if not (self.pm and self.selected_asset and self.selected_subtype):
            self.show_warning(u'提示', u'请先选择资产与子类型')
            return
        confirm_msg = u"确认保存当前场景为Master？？？\n\n建议: 如有旧的master请去往{}下的master备份\n".format(
            _u(self.selected_subtype))
        reply = QtWidgets.QMessageBox.question(
            self, u'确认保存Master', confirm_msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.No:
            return
        try:
            if fops.save_master(None, self.pm, self.current_asset_type, self.selected_asset, self.selected_subtype):
                notes = self.pm.get_notes(self.current_asset_type, self.selected_asset, self.selected_subtype)
                self.notes_text.setHtml(self.format_notes_text(notes))
                self.show_info_inview(u'Master has been saved', 'green')
            else:
                self.show_warning(u'失败', u'Master保存失败')
        except Exception as e:
            self.show_warning(u'失败', _u(e))



class PYPenpipelineDialog(ProjectMixin, AssetMixin, VersionMixin, FbxConfigMixin, DescriptionMixin, SnapshotMixin, PyouPersistentWindow):
    COLOR_MAP = {
        'red': QtGui.QColor(255, 120, 120),
        'yellow': QtGui.QColor(255, 230, 80),
        'blue': QtGui.QColor(100, 170, 255),
        'green': QtGui.QColor(100, 220, 120),
    }

    def __init__(self, parent=_widgets.maya_main_window()):
        super(PYPenpipelineDialog, self).__init__("PYPenpipelineDlgApp", "PYPenpipelineDialog", parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self.setWindowFlags(QtCore.Qt.Window |
                            QtCore.Qt.WindowMinimizeButtonHint |
                            QtCore.Qt.WindowMaximizeButtonHint |
                            QtCore.Qt.WindowCloseButtonHint)

        self.cfg = OpenPipelineConfig()
        self.maya_version = cmds.about(version=True) if IN_MAYA and cmds else 'Unknown'

        self.timeStamp = TIMESTAMP
        self.WINDOW_NAME = u'OpenPipeline v{} (Maya{})'.format(_u(VERSION), _u(self.maya_version))

        self.pm = None
        self.current_project_path = u''
        self.current_project_name = u''
        self.current_asset_type = u''
        self.selected_asset = None
        self.selected_subtype = None
        self.new_proj_name = None
        self.new_proj_path = None
        self.new_asset_name = None
        self.fbx_config = None
        self.UE_CONFIG = dict(DEFAULT_UE_CONFIG)
        self._fbx_dialog = None
        self._snapshot_selector = None

        self.setWindowTitle(self.WINDOW_NAME)
        self.loadWindowSettings()

        build_openpipeline_ui(self)
        self.update_root_path_label()
        self.load_projects()
        self.select_last_project()
        self.load_fbx_config()
        self._restore_version_format_combo()

    def show_info(self, title, message):
        QtWidgets.QMessageBox.information(self, _u(title), _u(message))

    def show_warning(self, title, message):
        QtWidgets.QMessageBox.warning(self, _u(title), _u(message))

    def show_critical(self, title, message):
        QtWidgets.QMessageBox.critical(self, _u(title), _u(message))

    def closeEvent(self, event):
        # 防抖期间关闭窗口时，把最后编辑的 description 落盘
        desc_flush = getattr(self, '_flush_description_save', None)
        if desc_flush is not None:
            desc_flush()
        try:
            super(PYPenpipelineDialog, self).closeEvent(event)
        except AttributeError:
            event.accept()

    def _is_dialog_alive(self):
        """窗口的 C++ 对象是否仍然存活，避免延迟回调打到已销毁的窗口。"""
        try:
            for module_name in ('shiboken6', 'shiboken2'):
                try:
                    shiboken = __import__(module_name)
                except ImportError:
                    continue
                validator = getattr(shiboken, 'isValid', None)
                if validator is not None and not validator(self):
                    return False
                break
            # 触碰一次 Qt 对象；已销毁时会抛 RuntimeError
            self.windowTitle()
            return True
        except RuntimeError:
            return False
        except Exception:
            return False

    def _show_message_delayed(self, level, title, message, delay):
        title = _u(title)
        message = _u(message)

        def _show():
            if not self._is_dialog_alive():
                return
            try:
                boxes = {
                    'info': QtWidgets.QMessageBox.information,
                    'warning': QtWidgets.QMessageBox.warning,
                    'critical': QtWidgets.QMessageBox.critical,
                }
                boxes[level](self, title, message)
            except RuntimeError:
                # 回调排队期间窗口被销毁
                pass

        QtCore.QTimer.singleShot(delay, _show)

    def show_info_delayed(self, title, message, delay=500):
        self._show_message_delayed('info', title, message, delay)

    def show_warning_delayed(self, title, message, delay=500):
        self._show_message_delayed('warning', title, message, delay)

    def show_critical_delayed(self, title, message, delay=500):
        self._show_message_delayed('critical', title, message, delay)

    def show_info_inview(self, title=u"Finished", color='yellow'):
        from HelpImageUI import inView_Message
        inView_Message(color, u"{}".format(_u(title)))

    def show_help(self, text="", *args):
        QtWidgets.QMessageBox.information(self, u"帮助", _u(text))

    def safe_run(self, func):
        try:
            func()
        except Exception as e:
            self.show_critical(u'错误', _u(e))

    def _reset_selection(self):
        """清空当前选择及其关联 UI，避免切换项目/资产类型后右键仍指向旧资产。"""
        desc_flush = getattr(self, '_flush_description_save', None)
        if desc_flush is not None:
            desc_flush()
        self.selected_asset = None
        self.selected_subtype = None
        if hasattr(self, 'asset_list'):
            self.asset_list.clear()
        if hasattr(self, 'subtype_list'):
            self.subtype_list.clear()
        if hasattr(self, 'asset_count'):
            self.asset_count.setText(u'0')
        if hasattr(self, 'info_label'):
            self.info_label.setText(u'未选择资产')
        if hasattr(self, 'preview_label'):
            self.preview_label.clear()
            self.preview_label.setText(u'No Preview')
        if hasattr(self, 'show_version_count'):
            self.show_version_count(0)
        self.clear_right()

    def clear_right(self):
        self.version_list.clear()
        self.notes_text.clear()
        self.clear_description_ui()
        self.btn_save_new_version.setEnabled(False)
        self.btn_save_new_version.setStyleSheet("color: gray;")
        self.btn_set_master.setEnabled(False)
        self.btn_set_master.setStyleSheet("color: gray;")
        self.btn_del_sub.setEnabled(False)
        self.btn_rename_sub.setEnabled(False)
        if not self.selected_asset:
            self.btn_delete_asset.setEnabled(False)
            self.btn_delete_asset.setVisible(False)
            self.btn_snapshot.setEnabled(False)
            self.btn_snapshot_direct.setEnabled(False)
            self.preview_label.clear()
            self.preview_label.setText(u'No Preview')

    def show_asset_context_menu(self, position):
        show_asset_context_menu(self, position)

    def show_subtype_context_menu(self, position):
        show_subtype_context_menu(self, position)

    def show_version_context_menu(self, position):
        show_version_context_menu(self, position)

    def _restore_version_format_combo(self):
        if not hasattr(self, "version_format_combo"):
            return
        fmt = _load_version_format_from_user_defined()
        idx = self.version_format_combo.findData(fmt)
        if idx >= 0:
            self.version_format_combo.blockSignals(True)
            self.version_format_combo.setCurrentIndex(idx)
            self.version_format_combo.blockSignals(False)

    def on_version_format_changed(self, index):
        fmt = self.version_format_combo.itemData(index)
        if not fmt:
            return
        if not _save_version_format_to_user_defined(fmt):
            logger.warning(
                u"[OpenPipeline] 无法保存版本格式 '%s' 到 user_defined.json"
                u"（user_defined 模块不可导入）", _u(fmt))



def main():
    global py_Penpipeline
    try:
        py_Penpipeline.close()
        py_Penpipeline.deleteLater()
    except Exception:
        pass

    py_Penpipeline = PYPenpipelineDialog()
    py_Penpipeline.show()
    return py_Penpipeline


if __name__ == '__main__':
    main()
