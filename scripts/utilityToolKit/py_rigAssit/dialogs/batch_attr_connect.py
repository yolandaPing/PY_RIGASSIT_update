# -*- coding: utf-8 -*-
# .FileName:batch_attr_connect.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2024/11/14 23:52
# .Finish time:
from functools import partial

import maya.cmds as cmds

from ui_framework.core.qtCompat import *
from ui_framework.widgets.widgets import Widgets, PyouPersistentWindow
from py_rigAssit.dialogs import Help, mayaPrint, undo

_widgets = Widgets()


class AttrConnectUI(PyouPersistentWindow):
    def __init__(self, parent=_widgets.maya_main_window()):
        super(AttrConnectUI, self).__init__("AttrConnectUI", "AttrConnectUI", parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Batch Attr Connect")
        self.setMinimumWidth(320)
        self.create_ui()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFocus()


    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(_widgets.create_text(u"输入对象，属性后，批量选择输入对象"))
        layout1, self.ot_node, self.ot_node_btn = _widgets.create_QLineEdit_row(u"输出对象:")
        layout2, self.ot_node_attr, self.ot_node_attr_btn = _widgets.create_QLineEdit_row(u"输出属性:")
        layout3, self.im_attr, self.im_attr_btn = _widgets.create_QLineEdit_row(u"输入属性:")
        btn_layout, bt_apply_btn, help_btn = _widgets.create_Qbuttons(" Apply ")
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        layout.addLayout(btn_layout)
        layout.addStretch()
        _widgets.create_copyrightText(layout, "2024")

        self.ot_node_btn.clicked.connect(partial(self.get_selection, self.ot_node))
        self.ot_node_attr_btn.clicked.connect(partial(self.get_selection_attr, self.ot_node_attr))
        self.im_attr_btn.clicked.connect(partial(self.get_selection_attr, self.im_attr))
        bt_apply_btn.clicked.connect(self.connect_to_all)

    def get_selection(self, fld):
        selection = cmds.ls(selection=True)
        if selection:
            fld.setText(selection[0])
        else:
            mayaPrint.warning("请选择一个输出对象")

    def get_selection_attr(self, fld):
        sel_attr = cmds.channelBox('mainChannelBox', q=1, sma=1)
        if sel_attr:
            fld.setText(sel_attr[0])

    @undo
    def connect_to_all(self):
        ot_node = self.ot_node.text().strip()
        ot_node_attr = self.ot_node_attr.text().strip()
        im_attr = self.im_attr.text().strip()

        selection = cmds.ls(selection=True)
        if selection:
            for i in selection:
                cmds.connectAttr("{}.{}".format(ot_node, ot_node_attr), "{}.{}".format(i, im_attr), f=1)
            mayaPrint.log("succeeded")
        else:
            mayaPrint.error("请选择输入对象")


def show():
    global attr_con_ins
    try:
        attr_con_ins.close()
        attr_con_ins.deleteLater()
    except:
        pass
    attr_con_ins = AttrConnectUI()
    attr_con_ins.show()
    return attr_con_ins

if __name__ == "__main__":
    show()