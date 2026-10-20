# -*- coding: utf-8 -*-

# .FileName:convert_drivenkeys_ui.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/6/3 20:04
# .Finish time:
from functools import partial

from py_rigAssit import QtWidgets, QtCore, QtGui, Widgets, PyouPersistentWindow
from py_rigAssit.dialogs import base_dir, Help, undo, mayaPrint
from Utils.sdk_info import SDKINFO_SET
import HelpImageUI as Help

import maya.cmds as cmds

_widgets = Widgets()
sdk_info = SDKINFO_SET()


class PYConvertQtWidgets(QtWidgets.QWidget):
    def __init__(self, parent=_widgets.maya_main_window()):
        super(PYConvertQtWidgets, self).__init__(parent)

    def init_ui(self):
        container = QtWidgets.QWidget()
        container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        main_layout = QtWidgets.QVBoxLayout(container)
        main_layout.setContentsMargins(8, 0, 8, 8)
        main_layout.setSpacing(0)
        group_node = QtWidgets.QGroupBox("")
        main_layout.addWidget(group_node)
        layout = QtWidgets.QVBoxLayout(group_node)

        layout1, self.dirve_attr, self.dirve_attr_btn = _widgets.create_QLineEdit_row(u"驱动属性:")

        self.parent_his = QtWidgets.QSpinBox()
        self.parent_his.setValue(1)
        self.parent_his.setFixedWidth(30)

        parent_his_form = QtWidgets.QFormLayout()
        parent_his_form.addRow(_widgets.create_bold_label(u'               父级: '), self.parent_his)
        self.dirve_value_block = _widgets.create_radiogroup(
            "Convert Type:",
            [("跟随关键帧值", 1, "follow key frame"), ("自定义范围值", 2, "user range")],
            default_id=1
        )
        value_layout = QtWidgets.QHBoxLayout()

        self.label = _widgets.create_bold_label(u'设置驱动属性值:')
        self.label.setStyleSheet("color: gray;")
        self.dirve_minmax_fld = QtWidgets.QLineEdit()
        self.dirve_minmax_fld.setText("0;10")
        self.dirve_minmax_fld.setEnabled(False)
        self.dirve_minmax_fld.setFixedWidth(160)
        value_layout.addWidget(self.label)
        value_layout.addWidget(self.dirve_minmax_fld)
        self.create_block = _widgets.create_radiogroup(
            "Create Type:",
            [("新建", 1, "当前父级新建"), ("添加", 2, "在当前父级已有的驱动上叠加")],
            default_id=1
        )
        btn_layout, bt_apply_btn, help_btn = _widgets.create_Qbuttons(" Apply ")

        layout.addLayout(layout1)
        layout.addWidget(_widgets.create_text(u"设置驱动转到当前控制器对象的父层级层数"))
        layout.addLayout(parent_his_form)
        layout.addWidget(self.dirve_value_block)
        layout.addWidget(_widgets.create_text(u"* 驱动属性值数量和关键帧一致，使用英文;分开"))
        layout.addLayout(value_layout)
        layout.addWidget(self.create_block)
        layout.addWidget(_widgets.create_text(u"* mainChannelBox选择需要的属性"))
        layout.addLayout(btn_layout)
        layout.addStretch()

        self.dirve_value_block.idClicked.connect(self._on_type_Toggled)
        self.dirve_attr_btn.clicked.connect(partial(self.get_selection_attr, self.dirve_attr))
        bt_apply_btn.clicked.connect(self.animCurve_convert)
        help_btn.clicked.connect(partial(Help.HelpImage,"", "animCurve_convert_tool"))

        return container

    def _on_type_Toggled(self, btn_id):

        if btn_id == 1:
            self.dirve_minmax_fld.setEnabled(False)
            self.label.setStyleSheet("color: gray;")
        else:
            self.dirve_minmax_fld.setEnabled(True)
            self.label.setStyleSheet("color: white;")

    def get_selection(self):
        selection = cmds.ls(selection=True)
        if selection:
            return selection
        else:
            mayaPrint.error("请选择一个输出对象")

    def get_selection_attr(self, fld):
        selection = self.get_selection()
        sel_attr = cmds.channelBox('mainChannelBox', q=1, sma=1)
        if selection and sel_attr:
            fld.setText("{}.{}".format(selection[0], sel_attr[0]))

    def create_animCurve(self, name, node_type, infos, dirver_attr, dirven_attr, create_type):
        new_node = cmds.createNode(node_type, name=name)
        sdk_info.set_AnimCurve_ValuePair(new_node, infos)
        cmds.connectAttr(dirver_attr, "{}.input".format(new_node), f=1)
        if create_type == 2:
            imp_drv_node = cmds.listConnections(dirven_attr, scn=False, p=True, s=True, d=False)
            if imp_drv_node:
                imp_drv_node = imp_drv_node[0]
                if cmds.objectType(imp_drv_node.split(".")[0]) == "blendWeighted":
                    indices = cmds.getAttr('{}.input'.format(imp_drv_node.split(".")[0]), multiIndices=True)
                    cmds.connectAttr('{}.output'.format(new_node), '{}.input[{}]'.format(imp_drv_node.split(".")[0], (indices[-1])+1), f=1)
                else:
                    blendWtd = cmds.createNode('blendWeighted', name='{}_Wtd'.format(name))
                    cmds.connectAttr(imp_drv_node, '{}.input[0]'.format(blendWtd), f=1)
                    cmds.connectAttr('{}.output'.format(new_node), '{}.input[1]'.format(blendWtd), f=1)
                    cmds.connectAttr("{}.output".format(blendWtd), dirven_attr, f=1)
        else:
            cmds.connectAttr("{}.output".format(new_node), dirven_attr, f=1)

    @undo
    def animCurve_convert(self):
        animCurve_map = {'animCurveTL': 'animCurveUL',
                         'animCurveTA': 'animCurveUA',
                         'animCurveTU': 'animCurveUU',
                         'animCurveTT': 'animCurveUT'}
        dirve_attr = self.dirve_attr.text()
        pa_his = self.parent_his.value()
        dirve_type = self.dirve_value_block.checkedId()
        create_type = self.create_block.checkedId()
        if dirve_type != 1:
            minmax_text = self.dirve_minmax_fld.text()
            minmax_value = [int(s) for s in minmax_text.split(";")]

        sels = self.get_selection()
        selAttr = cmds.channelBox("mainChannelBox", q=True, sma=True)

        for node in sels:
            full_path = cmds.listRelatives(sels[0], p=True, fullPath=True)[0]
            parent_list = full_path.split("|")[1:][::-1]

            if pa_his > len(parent_list):
                mayaPrint.warning(u'{}的父级没有第{}层'.format(node, pa_his))
                continue

            if pa_his == 0:
                parent_name = node
            else:
                parent_name = parent_list[pa_his-1]

            for attr in selAttr:
                imp_source_node = cmds.listConnections("{}.{}".format(node, attr), scn=False, p=True, s=True, d=False)
                if imp_source_node:
                    imp_source_node = imp_source_node[0]
                infos = sdk_info.get_AnimCurv_ValuePair(imp_source_node.split(".")[0])
                if dirve_type == 2 and minmax_value:
                    for idx, v in enumerate(minmax_value):
                        infos[idx+1][0] = v
                name = imp_source_node.split(".")[0].replace(node, parent_name)
                node_type = cmds.objectType(imp_source_node)
                self.create_animCurve(name, animCurve_map[node_type], infos, dirve_attr, "{}.{}".format(parent_name, attr), create_type)

        mayaPrint.log("animCurve convert succeeded.")


class PYConvertDrivenkeysUI(PyouPersistentWindow):
    def __init__(self, parent=_widgets.maya_main_window()):
        super(PYConvertDrivenkeysUI, self).__init__("PYConvertDrivenkeysUI", "PYConvertDrivenkeysUI", parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Animkeys Convert Drivenkeys")
        self.setMinimumWidth(320)
        self._build_ui()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFocus()

    def _build_ui(self):
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(8, 0, 8, 8)
        main.setSpacing(4)

        main.addWidget(_widgets.create_title("Animkeys Convert Drivenkeys", 15, None))
        self.widget = PYConvertQtWidgets(parent=self)
        main.addWidget(self.widget.init_ui())
        _widgets.create_copyrightText(main, "2026")


def main():
    global convert_keys_ui
    try:
        convert_keys_ui.close()
        convert_keys_ui.deleteLater()
    except:
        pass
    convert_keys_ui = PYConvertDrivenkeysUI()
    convert_keys_ui.show()
    return convert_keys_ui

if __name__ == "__main__":
    main()
