# -*- coding: utf-8 -*-

# .FileName:fbx_dialog.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2025/12/18 21:08
# .Finish time:

"""
FBX导出设置对话框模块
独立的非模态对话框，解决界面阻塞问题。
"""

from ui_framework.core.qtCompat import *
from ui_framework.widgets.widgets import Widgets, PyouPersistentWindow

try:
    import maya.cmds as cmds
    IN_MAYA = True
except Exception:
    IN_MAYA = False

_widgets = Widgets()

DEFAULT_UE_CONFIG = {
    'UnrealEditor': 'D:/UEProjects/MyProject/UnrealEngine/Engine/Binaries/Win64/UnrealEditor-Cmd.exe',
    'UE_PROJECT': 'D:/UEProjects/MyProject/MyProject.uproject',
    'CONTENT': 'test/Assets'
}


class FBXExportDialog(QtWidgets.QDialog):
    """FBX导出设置对话框（非模态）"""

    def __init__(self, parent=None, fbx_config=None, ue_config=None):
        super(FBXExportDialog, self).__init__(parent)
        self.fbx_config = fbx_config or ['Geo_grp', 'root_jnt']
        self.ue_config = dict(DEFAULT_UE_CONFIG)
        if isinstance(ue_config, dict):
            self.ue_config.update(ue_config)
        self.setWindowTitle(u'设置 FBX / UE 导出配置')
        self.setFixedSize(620, 310)
        self.init_ui()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFocus()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        geo_layout, self.geo_name_edit, get_geo_btn = _widgets.create_QLineEdit_row(u"几何体组名称:")
        joint_layout, self.joint_name_edit, get_joint_btn = _widgets.create_QLineEdit_row(u"根关节名称:")
        self.geo_name_edit.setText(self.fbx_config[0] if len(self.fbx_config) > 0 else '')
        self.joint_name_edit.setText(self.fbx_config[1] if len(self.fbx_config) > 1 else '')

        ue_form_layout = QtWidgets.QFormLayout()
        self.unreal_editor_edit = QtWidgets.QLineEdit(self.ue_config.get('UnrealEditor', ''))
        self.ue_project_edit = QtWidgets.QLineEdit(self.ue_config.get('UE_PROJECT', ''))
        self.content_edit = QtWidgets.QLineEdit(self.ue_config.get('CONTENT', ''))
        ue_form_layout.addRow(u'UnrealEditor:', self.unreal_editor_edit)
        ue_form_layout.addRow(u'UE_PROJECT:', self.ue_project_edit)
        ue_form_layout.addRow(u'CONTENT:', self.content_edit)

        info_label = _widgets.create_text(
            u'提示：FBX 名称会在导出时自动查找；UE 配置用于将 FBX 导入 Unreal。'
        )
        info_label.setWordWrap(True)
        layout.addLayout(geo_layout)
        layout.addLayout(joint_layout)
        layout.addLayout(ue_form_layout)
        layout.addWidget(info_label)
        get_geo_btn.clicked.connect(lambda: self.get_object_from_scene(self.geo_name_edit))
        get_joint_btn.clicked.connect(lambda: self.get_object_from_scene(self.joint_name_edit, 'joint'))
        
        button_layout = QtWidgets.QHBoxLayout()
        test_btn = QtWidgets.QPushButton(u'测试对象')
        test_btn.clicked.connect(self.test_fbx_objects)
        button_layout.addWidget(test_btn)
        button_layout.addStretch()
        self.ok_btn = QtWidgets.QPushButton(u'  确定  ')
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QtWidgets.QPushButton(u'  取消  ')
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def get_object_from_scene(self, target_edit, obj_type='transform'):
        """从Maya场景中获取对象名称并填入文本框"""
        if not IN_MAYA:
            QtWidgets.QMessageBox.warning(self, u'错误', u'此功能只能在Maya中运行')
            return
        try:
            selected = cmds.ls(selection=True, type=obj_type)
            if selected:
                target_edit.setText(selected[0])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, u'错误', u'获取场景对象失败:\n{}'.format(str(e)))

    def test_fbx_objects(self):
        """测试FBX导出对象是否存在于当前场景"""
        if not IN_MAYA:
            QtWidgets.QMessageBox.warning(self, u'错误', u'此功能只能在Maya中运行')
            return

        geo_name = self.geo_name_edit.text().strip()
        joint_name = self.joint_name_edit.text().strip()
        if not geo_name and not joint_name:
            QtWidgets.QMessageBox.warning(self, u'提示', u'请先设置要导出的对象名称')
            return

        try:
            missing_objects = []
            if geo_name:
                if not cmds.objExists(geo_name):
                    missing_objects.append(geo_name)
                elif cmds.objectType(geo_name) != 'transform':
                    missing_objects.append(u'{} (类型错误，期望transform)'.format(geo_name))
            # 测试根关节
            if joint_name:
                if not cmds.objExists(joint_name):
                    missing_objects.append(joint_name)
                elif cmds.objectType(joint_name) not in ['joint', 'transform']:
                    missing_objects.append(u'{} (类型错误，期望joint)'.format(joint_name))

            if not missing_objects:
                QtWidgets.QMessageBox.information(self, u'测试通过', u'所有设置的对象都存在于当前场景中')
            else:
                QtWidgets.QMessageBox.warning(self, u'测试失败', u'以下对象不存在或类型错误:\n\n' + '\n'.join(missing_objects))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, u'错误', u'测试过程中发生错误:\n{}'.format(str(e)))

    def get_settings(self):
        """获取对话框中设置的FBX对象名称"""
        return [
            self.geo_name_edit.text().strip(),
            self.joint_name_edit.text().strip()
        ]

    def get_ue_settings(self):
        """获取对话框中设置的 Unreal Engine 导出配置。"""
        return {
            'UnrealEditor': self.unreal_editor_edit.text().strip(),
            'UE_PROJECT': self.ue_project_edit.text().strip(),
            'CONTENT': self.content_edit.text().strip()
        }
