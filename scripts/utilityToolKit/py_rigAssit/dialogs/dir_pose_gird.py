# -*- coding: utf-8 -*-

# .FileName:dir_pose_gird.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/7/14 23:57
# .Finish time:
"""
DIR Pose Grid / Direction / Angle Pose Editor
规则: direction: 0,90,180,270; radius: 0-180°; 每圈15°; 总共12圈
"""
from functools import partial

import math

from py_rigAssit import QtWidgets, QtCore, QtGui, Qt, Widgets, PyouPersistentWindow
from py_rigAssit.dialogs import Help
import maya.cmds as cmds
import pymel.core as pm


class PoseData(object):
    def __init__(self, angle, direction, node=None):
        self.angle = float(angle)
        self.direction = float(direction)
        self.node = node
        radius = self.angle / 180.0
        rad = math.radians(self.direction)
        self.x = math.sin(rad) * radius
        self.y = -math.cos(rad) * radius
    def data(self):
        return {"angle": self.angle, "direction": self.direction, "x": self.x, "y": self.y}
    def get_node(self):
        return self.node


class DIRPoseTempSolver(object):
    def __init__(self):
        self.info_node = None
        self.input_pose = None
        self.drive_joint = None
        self.drive_ctrl = None
        self.temp_joint = None
        self.temp_info = None
        self.system = None

    def load_driver(self, info_node, input_pose):
        self.clear()
        self.info_node = info_node
        self.input_pose = input_pose
        if not cmds.objExists(input_pose):
            return False
        if cmds.objExists(input_pose + ".drive_joint"):
            self.drive_joint = cmds.getAttr(input_pose + ".drive_joint")
        self.drive_ctrl = cmds.getAttr(input_pose + ".drive_ctrl")
        if isinstance(self.drive_ctrl, list):
            self.drive_ctrl = self.drive_ctrl[0]
        if not self.drive_joint:
            cmds.warning("No drive_joint")
            return False
        return True

    def create_temp_joint(self):
        self.clear_temp()
        self.temp_joint = cmds.createNode("joint", n="DIRPose_temp_joint")
        pat = cmds.listRelatives(self.info_node, parent=True)[0]
        self.temp_info = cmds.createNode("joint", n="DIRPose_temp_PoseInfo", parent=pat)
        cmds.matchTransform(self.temp_info, self.info_node)
        cmds.parent(self.temp_joint, self.temp_info)
        matrix = cmds.xform(self.input_pose, q=True, ws=True, matrix=True)
        cmds.xform(self.temp_joint, ws=True, matrix=matrix)
        cmds.setAttr(self.temp_joint + ".rotate", 0,0,0, type="double3")
        cmds.setAttr(self.temp_joint + ".jointOrient", 0,0,0, type="double3")
        cmds.setAttr(self.temp_info + ".visibility", 0)
        return self.temp_joint

    def build_driver_network(self):
        if not self.temp_joint:
            return False
        try:
            from DrivePose.direction_dirve_pose import driver_core
            self.system = driver_core.DIRDrivePoseSystem()
            self.system.aixs = cmds.getAttr(self.info_node + ".init_axis")
            if isinstance(self.system.aixs, tuple):
                self.system.aixs = self.system.aixs[0]
            self.system.update_angle_direction(self.temp_joint)
            cmds.select(cl=1)
            return True
        except Exception as e:
            print("Temp DIR network error:", e)
            return False

    def set_pose(self, angle, direction):
        if not self.temp_joint:
            return
        d = math.radians(direction)
        a = math.radians(angle)
        direction_matrix = pm.datatypes.Matrix([
            [1,0,0,0],
            [0,math.cos(d),math.sin(d),0],
            [0,-math.sin(d),math.cos(d),0],
            [0,0,0,1]
        ])
        angle_matrix = pm.datatypes.Matrix([
            [math.cos(a),math.sin(a),0,0],
            [-math.sin(a),math.cos(a),0,0],
            [0,0,1,0],
            [0,0,0,1]
        ])
        result = direction_matrix.inverse() * angle_matrix * direction_matrix
        euler = pm.datatypes.EulerRotation(result)
        cmds.setAttr(self.temp_joint + ".rotate",
                     math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z), type="double3")
        cmds.dgdirty(self.temp_joint)

    def get_rotate(self):
        if not self.temp_joint or not cmds.objExists(self.temp_joint):
            return None
        cmds.matchTransform(self.drive_ctrl, self.temp_joint, pos=False, rot=True)
        return cmds.getAttr(self.drive_ctrl+".rotate")[0]

    def clear_temp(self):
        for node in [self.temp_joint, self.temp_info]:
            if node and cmds.objExists(node):
                cmds.delete(node)
        self.temp_joint = None
        self.temp_info = None
        self.system = None

    def clear(self):
        self.clear_temp()
        self.info_node = None
        self.input_pose = None
        self.drive_joint = None
        self.drive_ctrl = None


class GridWidget(QtWidgets.QWidget):

    positionChanged = QtCore.Signal(float, float)
    controlChanged = QtCore.Signal(float, float)
    poseSelected = QtCore.Signal(float, float, str)
    poseDoubleClicked = QtCore.Signal(float, float, str)
    poseAdded = QtCore.Signal(float, float)
    calculatePressed = QtCore.Signal()
    resetPressed = QtCore.Signal()  # 新增重置信号，用于通知主窗口

    def __init__(self, parent=None):
        super(GridWidget, self).__init__(parent)
        self.setMinimumSize(480, 480)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.current_angle = 0
        self.current_direction = 0
        self.current_x = 0
        self.current_y = 0
        self.rotate_mode = None
        self.temp_solver = None
        self.temp_poses = {}
        self.poses = []
        self.selected_pose = None
        self.dragging = False
        self.margin = 20
        self.bg_color = QtGui.QColor(30, 30, 35)
        self.grid_color = QtGui.QColor(90, 100, 120, 100)
        self.direction_color = QtGui.QColor(160, 180, 220, 150)
        self.pose_color = QtGui.QColor(0, 180, 255)
        self.select_color = QtGui.QColor(255, 180, 50)
        self.origin_color = QtGui.QColor(255, 50, 50)
        self.text_color = QtGui.QColor(180, 190, 200)
        self.font = QtGui.QFont("Arial", 9)
        self.drag_line_color = QtGui.QColor(0, 255, 200, 180)
        self.last_mouse_pos = None

    def set_driver_pose(self, poses):
        self.poses = []
        for item in poses:
            if len(item) == 3:
                angle, direction, node = item
            else:
                angle, direction = item
                node = None
            self.poses.append(PoseData(angle, direction, node))
        self.update()

    def clear_pose(self):
        self.poses = []
        self.selected_pose = None
        self.update()

    def get_current_pose(self):
        return {"angle": self.current_angle, "direction": self.current_direction}

    def select_pose(self, angle, direction):
        for pose in self.poses:
            if abs(pose.angle - angle) < 0.01 and abs(pose.direction - direction) < 0.01:
                self.selected_pose = pose
                self.current_angle = pose.angle
                self.current_direction = pose.direction
                self.current_x = pose.x
                self.current_y = pose.y
                self.update()
                return True
        return False

    def calculate_temp_rotate(self):
        if not self.rotate_mode:
            return
        angle = self.current_angle
        direction = self.current_direction
        if angle <= 0:
            return
        self.temp_solver.set_pose(angle, direction)
        rotate = self.temp_solver.get_rotate()
        if not rotate:
            return
        ctrl = self.temp_solver.drive_ctrl
        cmds.setAttr(self.temp_solver.temp_joint + ".rotate", rotate[0], rotate[1], rotate[2], type="double3")
        self.temp_poses[(angle, direction)] = rotate
        self.update()
        print("DIR Temp Rotate:", angle, direction, rotate)
        return ctrl

    def reset_to_origin(self):
        """重置网格控制点到原点（角度0，方向0），并清除临时标记"""
        self.current_angle = 0.0
        self.current_direction = 0.0
        self.current_x, self.current_y = 0.0, 0.0
        self.temp_poses.clear()
        self.selected_pose = None
        self.positionChanged.emit(0.0, 0.0)
        self.controlChanged.emit(0.0, 0.0)

        self.update()

    def position_to_pose(self, x, y):
        radius = math.sqrt(x * x + y * y)
        if radius > 1:
            radius = 1
        angle = radius * 180.0
        direction = math.degrees(math.atan2(x, -y))
        if direction < 0:
            direction += 360
        return angle, direction

    def pose_to_position(self, angle, direction):
        radius = angle / 180.0
        rad = math.radians(direction)
        x = math.sin(rad) * radius
        y = -math.cos(rad) * radius
        return x, y

    def hit_test_pose(self, pos):
        rect = self.rect()
        size = min(rect.width(), rect.height())
        radius = size / 2 - self.margin
        cx = rect.width() / 2
        cy = rect.height() / 2
        x = (pos.x() - cx) / radius
        y = (pos.y() - cy) / radius
        for pose in self.poses:
            d = math.sqrt((pose.x - x) ** 2 + (pose.y - y) ** 2)
            if d < 0.04:
                return pose
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pose = self.hit_test_pose(event.pos())
            if pose:
                self.selected_pose = pose
                self.current_angle = pose.angle
                self.current_direction = pose.direction
                self.current_x = pose.x
                self.current_y = pose.y
                self.poseSelected.emit(pose.angle, pose.direction, pose.node)
                self.update()
                return
            self.dragging = True
            self.update_position(event.pos())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.update_position(event.pos())

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def mouseDoubleClickEvent(self, event):
        pose = self.hit_test_pose(event.pos())
        if pose:
            self.selected_pose = pose
            self.poseDoubleClicked.emit(pose.angle, pose.direction, pose.node)
            self.update()
        else:
            # 双击空白区域 → 重置原点，并发射信号通知主窗口
            self.reset_to_origin()
            self.resetPressed.emit()

    def update_position(self, pos):
        rect = self.rect()
        size = min(rect.width(), rect.height())
        radius = size / 2 - self.margin
        cx = rect.width() / 2
        cy = rect.height() / 2
        x = (pos.x() - cx) / radius
        y = (pos.y() - cy) / radius
        angle, direction = self.position_to_pose(x, y)
        self.current_x, self.current_y = self.pose_to_position(angle, direction)
        self.current_angle = angle
        self.current_direction = direction
        self.positionChanged.emit(angle, direction)
        self.controlChanged.emit(angle, direction)
        self.update()

    def snap_to_grid(self):
        if self.current_angle <= 0:
            angle = 0
        else:
            angle = round(self.current_angle / 15.0) * 15
            if angle > 180:
                angle = 180
        direction = round(self.current_direction / 15.0) * 15
        if direction >= 360:
            direction = 0
        self.current_angle = angle
        self.current_direction = direction
        self.current_x, self.current_y = self.pose_to_position(angle, direction)
        self.positionChanged.emit(angle, direction)
        self.controlChanged.emit(angle, direction)
        self.update()

    def snap_nearest_pose(self):
        if not self.poses:
            return
        best = None
        min_dist = float('inf')
        for pose in self.poses:
            d = math.sqrt((pose.x - self.current_x) ** 2 + (pose.y - self.current_y) ** 2)
            if d < min_dist:
                min_dist = d
                best = pose
        if best:
            self.selected_pose = best
            self.current_angle = best.angle
            self.current_direction = best.direction
            self.current_x = best.x
            self.current_y = best.y
            self.positionChanged.emit(best.angle, best.direction)
            self.controlChanged.emit(best.angle, best.direction)
            self.poseSelected.emit(best.angle, best.direction, best.node)
            self.update()

    def add_pose_at_cursor(self):
        if self.last_mouse_pos is None:
            return
        rect = self.rect()
        size = min(rect.width(), rect.height())
        radius = size / 2 - self.margin
        cx = rect.width() / 2
        cy = rect.height() / 2
        x = (self.last_mouse_pos.x() - cx) / radius
        y = (self.last_mouse_pos.y() - cy) / radius
        if math.sqrt(x * x + y * y) > 1:
            return
        angle, direction = self.position_to_pose(x, y)
        for pose in self.poses:
            if abs(pose.angle - angle) < 0.01 and abs(pose.direction - direction) < 0.01:
                self.select_pose(angle, direction)
                return
        new_pose = PoseData(angle, direction, node=None)
        self.poses.append(new_pose)
        self.selected_pose = new_pose
        self.current_angle = angle
        self.current_direction = direction
        self.current_x = new_pose.x
        self.current_y = new_pose.y
        self.positionChanged.emit(angle, direction)
        self.controlChanged.emit(angle, direction)
        self.poseAdded.emit(angle, direction)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_X:
            self.snap_to_grid()
        elif event.key() == Qt.Key_V:
            self.snap_nearest_pose()
        elif event.key() == Qt.Key_S:
            self.calculatePressed.emit()
        # 移除了 R 键处理，符合要求
        else:
            super(GridWidget, self).keyPressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        w, h = rect.width(), rect.height()
        size = min(w, h)
        radius = size / 2 - self.margin
        cx, cy = w / 2, h / 2
        painter.fillRect(rect, self.bg_color)
        painter.setFont(self.font)

        # 虚线圆环
        pen = QtGui.QPen(self.grid_color, 1, Qt.DashLine)
        painter.setPen(pen)
        for i in range(1, 13):
            angle_value = i * 15
            r = radius * (angle_value / 180.0)
            painter.drawEllipse(QtCore.QPointF(cx, cy), r, r)
            painter.setPen(self.text_color)
            painter.drawText(QtCore.QPointF(cx + 5, cy - r), "{}°".format(angle_value))
            painter.setPen(pen)

        # 方向线（实线）
        pen = QtGui.QPen(self.grid_color, 1, Qt.SolidLine)
        painter.setPen(pen)
        for direction in range(0, 360, 15):
            rad = math.radians(direction)
            x = cx + radius * math.sin(rad)
            y = cy - radius * math.cos(rad)
            painter.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(x, y))

        # 中心十字（实线）
        cross_pen = QtGui.QPen(QtGui.QColor(180, 255, 255), 1, Qt.SolidLine)
        painter.setPen(cross_pen)
        painter.drawLine(QtCore.QPointF(cx - radius, cy), QtCore.QPointF(cx + radius, cy))
        painter.drawLine(QtCore.QPointF(cx, cy - radius), QtCore.QPointF(cx, cy + radius))

        # 方向标签
        painter.setPen(self.text_color)
        labels = [(0, "0"), (45, "45"), (90, "90"), (135, "135"), (180, "180"), (225, "225"), (270, "270"),
                  (315, "315")]
        for deg, text in labels:
            rad = math.radians(deg)
            x = cx + (radius + 15) * math.sin(rad)
            y = cy - (radius + 15) * math.cos(rad)
            painter.drawText(QtCore.QPointF(x, y), text)

        # 原点
        painter.setBrush(self.origin_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QtCore.QPointF(cx, cy), 5, 5)

        # 已存姿态点
        for pose in self.poses:
            px = cx + pose.x * radius
            py = cy + pose.y * radius
            painter.setBrush(self.select_color if pose == self.selected_pose else self.pose_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QtCore.QPointF(px, py), 6, 6)

        # 临时姿态点
        for angle, direction in self.temp_poses.keys():
            x, y = self.pose_to_position(angle, direction)
            px = cx + x * radius
            py = cy + y * radius
            painter.setBrush(QtGui.QColor(255, 220, 0))
            painter.drawEllipse(QtCore.QPointF(px, py), 6, 6)

        # 拖动指示线
        px = cx + self.current_x * radius
        py = cy + self.current_y * radius
        if self.dragging and (abs(self.current_x) > 0.001 or abs(self.current_y) > 0.001):
            painter.setPen(QtGui.QPen(self.drag_line_color, 2.0, Qt.DotLine))
            painter.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(px, py))

        # 当前点
        painter.setBrush(QtGui.QColor(255, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QtCore.QPointF(px, py), 8, 8)

        # 信息文字
        painter.setPen(self.text_color)
        painter.drawText(QtCore.QPointF(10, 20),
                         "Angle: {:.1f}  Direction: {:.1f}".format(self.current_angle, self.current_direction))


class DIRPoseGridWindow(PyouPersistentWindow):
    def __init__(self, parent=None):
        super(DIRPoseGridWindow, self).__init__("PYDIRPoseGridDlg", "PYDIRPoseGridWindow", parent)
        self.setWindowTitle("DIR Pose Grid")
        self.resize(500, 650)
        self.driver_node = None
        self.realtime = False
        self.driver_info = None
        self.input_pose = None
        self.ad_pose = None
        self.grid = GridWidget(self)
        self.temp_solver = DIRPoseTempSolver()
        self.rotate_mode = False
        self.current_info = None
        self.current_input_pose = None

        self.header = "pyDIRPoseGridHeader"
        self.setup_ui()

    def setup_ui(self):
        container = QtWidgets.QWidget()
        main = QtWidgets.QVBoxLayout(container)
        main.setContentsMargins(2, 2, 2, 2)
        main.setSpacing(2)
        PY_WIDGEAT = Widgets()

        self.driver_label = QtWidgets.QLabel(" None")
        self.input_label = QtWidgets.QLabel(" None")
        self.rotate_btn = QtWidgets.QPushButton("Entered rotate mode")
        self.direction_label = QtWidgets.QLabel("Direction: 0")
        self.angle_label = QtWidgets.QLabel("Angle: 0")
        self.rotate_label = QtWidgets.QLabel("Rotate: ")
        self.load_btn = QtWidgets.QPushButton("Load Driver System")
        self.clear_btn = QtWidgets.QPushButton(" [Clear temp] ")
        self.reset_btn = QtWidgets.QPushButton(" [Reset] ")  # 新增 Reset 按钮
        gird_key = QtWidgets.QLabel(u"x:吸附栅格, v:吸附pose, s:计算角度, 双击空白处重置原点")
        gird_key.setStyleSheet("color: #888;")
        self.load_btn.setProperty("green", True)
        self.clear_btn.setProperty("danger", True)
        self.rotate_btn.setProperty("cld", True)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(PY_WIDGEAT.create_text("Driver: "))
        top.addWidget(self.driver_label)
        top.addWidget(PY_WIDGEAT.create_text("Input_pose: "))
        top.addWidget(self.input_label)
        top.addStretch()
        info = QtWidgets.QHBoxLayout()
        info.addWidget(self.direction_label, 1)
        info.addWidget(self.angle_label, 1)
        info.addWidget(self.rotate_label)
        info.addWidget(self.rotate_btn, 2)
        btn = QtWidgets.QHBoxLayout()
        btn.addWidget(self.load_btn, 1)
        btn.addWidget(self.clear_btn)
        btn.addWidget(self.reset_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(PY_WIDGEAT.create_title("DIR Pose Grid", 15, None))
        layout.addLayout(top)
        layout.addWidget(self.grid, 1)
        layout.addWidget(gird_key)
        layout.addLayout(info)
        layout.addLayout(btn)
        PY_WIDGEAT.create_copyrightText(layout, "2026")
        main.addLayout(layout)

        # Signals
        self.load_btn.clicked.connect(self.load_selected_driver)
        self.clear_btn.clicked.connect(self.clear_temp_pose)
        self.reset_btn.clicked.connect(self.reset_to_origin)
        self.grid.positionChanged.connect(self.update_info)
        self.grid.poseDoubleClicked.connect(self.return_pose_position)
        self.grid.poseAdded.connect(self.on_pose_added)
        self.rotate_btn.clicked.connect(self.rotate_mode_state)
        self.grid.calculatePressed.connect(self.calculate_temp_rotate)
        self.grid.resetPressed.connect(self.reset_to_origin)          # 双击空白触发重置

    def rotate_mode_state(self, *args):
        try:
            if not self.info_node:
                cmds.warning("Please load driver first")
                return
        except:
            cmds.warning("Please load driver first")
            return
        if self.rotate_mode:
            self.disable_rotate_mode()
            self.show_heads(False)
            self.rotate_btn.setText("Entered rotate mode")
        else:
            self.enable_rotate_mode()
            self.show_heads(True)
            self.rotate_btn.setText("Exited rotate mode")

    def show_heads(self, enable):
        if cmds.headsUpDisplay(self.header, ex=1):
            cmds.headsUpDisplay(self.header, rem=1)

        if enable:
            cmds.headsUpDisplay(
                self.header,
                s=2,
                b=0,
                bs="medium",
                l="Soft Weight Real-time",
                lfs="large"
            )
            Help.inView_Message("red", "Entered calculate rotate mode")
        else:
            Help.inView_Message("yellow", "Exited calculate rotate mode")

    def load_existing_pose(self):
        from DrivePose.direction_dirve_pose import driver_core
        system = driver_core.DIRDrivePoseSystem()
        poses = system.get_poses(self.driver_node)
        self.pose_map = {}
        grid_poses = []
        base = self.driver_node.replace("_Info", "")
        for angle, direction in poses:
            pose_name = "{}PST__pose_dir{}_ang{}".format(base, int(direction), int(angle))
            key = (float(angle), float(direction))
            self.pose_map[key] = pose_name if cmds.objExists(pose_name) else None
            grid_poses.append((angle, direction, None))
        self.grid.set_driver_pose(grid_poses)
        # print("DIR Pose Map:", self.pose_map)

    def load_selected_driver(self):
        if self.temp_solver:
            self.temp_solver.clear()
        sel = cmds.ls(sl=True)
        if not sel:
            cmds.warning("Select DIRpose Info")
            return
        info = sel[0]
        if not cmds.objExists(info + ".input_pose"):
            cmds.warning("No input pose")
            return
        input_pose = cmds.getAttr(info + ".input_pose")
        if not input_pose:
            cmds.warning("Invalid input pose")
            return
        self.info_node = info
        self.input_pose = input_pose
        self.temp_solver.load_driver(self.info_node, self.input_pose)
        self.driver_node = self.info_node
        self.load_existing_pose()
        self.driver_label.setText(self.info_node)
        self.input_label.setText(self.input_pose)
        print("DIR Driver Loaded:", info)

    def update_realtime_pose(self, angle, direction):
        try:
            self.preview.update(angle, direction)
            rot = self.preview.get_rotate()
            if rot:
                self.rotate_label.setText("RX {:.2f}  RY {:.2f}  RZ {:.2f}".format(rot[0], rot[1], rot[2]))
        except Exception as e:
            print("DIR Preview Error:", e)

    def update_info(self, angle, direction):
        self.angle_label.setText("Angle: {:.1f}".format(angle))
        self.direction_label.setText("Direction: {:.1f}".format(direction))

    def return_pose_position(self, angle, direction, node):
        pose = self.pose_map.get((float(angle), float(direction)))
        if not pose:
            cmds.warning("Pose not found: {} {}".format(angle, direction))
            return
        cmds.select(pose, r=True)
        from DrivePose.direction_dirve_pose import driver_core
        system = driver_core.DIRDrivePoseSystem()
        system.return_pose_position()

    def convert_grid_direction(self, direction):
        direction = 90 - direction
        if direction < 0:
            direction += 360
        return direction

    def calculate_temp_rotate(self):
        if not self.rotate_mode:
            return
        angle = self.grid.current_angle
        direction = self.grid.current_direction
        if angle <= 0:
            return
        self.temp_solver.set_pose(angle, direction)
        rotate = self.temp_solver.get_rotate()
        if not rotate:
            return
        ctrl = self.temp_solver.drive_ctrl
        cmds.setAttr(ctrl + ".rotate", rotate[0], rotate[1], rotate[2], type="double3")
        self.grid.temp_poses[(angle, direction)] = rotate
        self.grid.update()
        print("DIR Temp Rotate:", angle, direction, rotate)

    def reset_to_origin(self):
        """重置网格点并归零控制器旋转"""
        self.grid.reset_to_origin()  # 更新界面状态
        if self.temp_solver.drive_ctrl:
            # 直接设置控制器旋转为0
            cmds.setAttr(self.temp_solver.drive_ctrl + ".rotate", 0, 0, 0, type="double3")


    def on_pose_added(self, angle, direction):
        print("New pose added: angle={}, direction={}".format(angle, direction))

    def enable_rotate_mode(self):
        try:
            if not self.info_node:
                cmds.warning("Please load driver first")
                return
        except:
            cmds.warning("Please load driver first")
            return
        self.rotate_mode = True
        self.temp_solver.create_temp_joint()
        self.temp_solver.build_driver_network()
        print("DIR Rotate Calculate Mode")

    def disable_rotate_mode(self):
        self.rotate_mode = False
        self.temp_solver.clear_temp()
        print("DIR Rotate Mode Off")

    def clear(self):
        self.driver_node = None
        self.ad_pose = None
        self.driver_label.setText("Driver: None")
        self.grid.clear_pose()

    def closeEvent(self, event):
        try:
            if hasattr(self, "temp_solver"):
                self.temp_solver.clear()
        except Exception as e:
            print("DIR temp clear:", e)
        event.accept()

    def clear_temp_pose(self):
        self.grid.temp_poses.clear()
        self.grid.update()


def show():
    global _window
    try:
        if _window:
            _window.close()
            _window.deleteLater()
    except:
        pass
    _window = DIRPoseGridWindow()
    _window.show()
    return _window

if __name__ == "__main__":
    show()