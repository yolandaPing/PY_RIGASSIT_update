# -*- coding: utf-8 -*-

# .FileName:snapshot_manager.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/10/24
# .Finish time:

"""
截图相关功能 Mixin（直接截图 / 框选截图）。

两个对外方法：
  - take_snapshot_direct: Maya playblast 截当前场景视图，直接覆盖 preview.png
  - take_snapshot:        隐藏窗口 → 抓 Maya 主窗口所在屏幕 → 拖拽选区 → 裁切保存 preview.png

依赖宿主类提供：
  - self.pm
  - self.current_asset_type
  - self.selected_asset
  - self.selected_subtype
  - self.preview_label
  - self.show_warning(title, message)
"""

import os
import sys

try:
    from ui_framework.core.qtCompat import *
    from ui_framework.widgets.widgets import Widgets
except:
    from CommonUse.qtCompat import *
    from CommonUse.widgetsUse import Widgets

try:
    from py_rigAssit.openpipeline import ui_openpipeline
except ImportError:
    from . import ui_openpipeline

_widgets = Widgets()

PY2 = (sys.version_info[0] == 2)


def _normalize_screen_pixmap(pix, screen):
    """确保 grabWindow 返回的 pixmap 只覆盖目标屏幕本身。

    兼容场景：
      - pixmap 携带 devicePixelRatio（高 DPI）；
      - 某些平台下 grabWindow(0) 返回的是整个虚拟桌面（需要裁出目标屏）。
    尺寸对不上时回退原 pixmap，由 crop_region_from_screenshot 的 ratio 逻辑兜底。
    """
    if pix is None or pix.isNull():
        return pix
    try:
        geo = screen.geometry()
    except Exception:
        return pix
    if geo.width() <= 0 or geo.height() <= 0:
        return pix

    # devicePixelRatio 在老版本 PySide2 可能不存在
    try:
        dpr = float(pix.devicePixelRatio() or 1.0)
    except Exception:
        dpr = 1.0
    if dpr <= 0:
        dpr = 1.0

    expected_w = geo.width() * dpr
    expected_h = geo.height() * dpr
    if abs(pix.width() - expected_w) <= 2 and abs(pix.height() - expected_h) <= 2:
        return pix

    # 若 pixmap 覆盖整个虚拟桌面，则裁出目标屏幕区域
    screens = []
    try:
        screens = QtGui.QGuiApplication.screens()
    except Exception:
        try:
            screens = QtWidgets.QApplication.screens()
        except Exception:
            pass
    if screens:
        try:
            v_geo = screens[0].geometry()
            for s in screens[1:]:
                v_geo = v_geo.united(s.geometry())
            v_w = v_geo.width() * dpr
            v_h = v_geo.height() * dpr
            if abs(pix.width() - v_w) <= 2 and abs(pix.height() - v_h) <= 2:
                ox = int(round((geo.x() - v_geo.x()) * dpr))
                oy = int(round((geo.y() - v_geo.y()) * dpr))
                rect = QtCore.QRect(
                    ox, oy,
                    int(round(geo.width() * dpr)),
                    int(round(geo.height() * dpr)),
                )
                rect = rect.intersected(pix.rect())
                if rect.width() > 0 and rect.height() > 0:
                    return pix.copy(rect)
        except Exception:
            pass

    return pix

def _grab_screen_pixmap(screen):
    """兼容各版本 PySide2 的屏幕抓取。

    Maya 2019（Py2.7 + PySide2 5.6）的坑：
        QScreen.grabWindow(qintptr, ...) 要求第一个参数是 long 类型，
        传入 int 的 0 会报 "called with wrong argument types"。
        解决：Py2 下用 long(0)。

    回退路径：
      1) QScreen.grabWindow(long(0))          ← Py2 首选
      2) QScreen.grabWindow(0)                 ← Py3 首选
      3) QScreen.grabWindow(0, 0, 0, -1, -1)   ← 完整签名
      4) QPixmap.grabWindow(0)                 ← Qt4 遗留 API
      5) shiboken2.VoidPtr(0) 显式转 qintptr
    """
    last_error = None
    grab_func = getattr(screen, "grabWindow", None)

    # 候选 zero 值：Py2 先试 long(0)，再试 0；Py3 直接 0
    zero_candidates = []
    if PY2:
        try:
            zero_candidates.append(long(0))  # noqa: F821
        except Exception:
            pass
    zero_candidates.append(0)

    if callable(grab_func):
        for zero in zero_candidates:
            # 单参数
            try:
                pix = grab_func(zero)
                if pix is not None and not pix.isNull():
                    return _normalize_screen_pixmap(pix, screen)
            except Exception as e:
                last_error = e

            # 完整参数
            try:
                pix = grab_func(zero, 0, 0, -1, -1)
                if pix is not None and not pix.isNull():
                    return _normalize_screen_pixmap(pix, screen)
            except Exception as e:
                last_error = e

    # QPixmap.grabWindow（Qt4 遗留 API，PySide2 部分版本仍保留）
    try:
        legacy = getattr(QtGui.QPixmap, "grabWindow", None)
        if callable(legacy):
            pix = legacy(0)
            if pix is not None and not pix.isNull():
                return _normalize_screen_pixmap(pix, screen)
    except Exception as e:
        last_error = e

    # shiboken2 显式转 VoidPtr(qintptr)
    try:
        import shiboken2
        ptr = shiboken2.VoidPtr(0, False)
        pix = grab_func(ptr)
        if pix is not None and not pix.isNull():
            return _normalize_screen_pixmap(pix, screen)
    except Exception as e:
        last_error = e

    raise RuntimeError(
        u'当前 Maya/Qt 环境不提供可用的屏幕抓取接口: {}'.format(repr(last_error))
    )


class SnapshotMixin(object):
    """截图功能 Mixin，需与宿主对话框组合使用。"""

    def _resolve_target_screen(self):
        """返回当前 Maya 主窗口（场景）所在的屏幕。

        策略：
          1. 只有一块屏幕时直接返回主屏；
          2. 依次用 Maya 主窗口中心、当前对话框中心，通过 screenAt 或屏幕几何判定；
          3. 都失败时回退主屏。
        """
        screens = []
        try:
            screens = QtGui.QGuiApplication.screens()
        except Exception:
            try:
                screens = QtWidgets.QApplication.screens()
            except Exception:
                pass

        try:
            primary = QtWidgets.QApplication.primaryScreen()
        except Exception:
            primary = None

        if not screens or len(screens) <= 1:
            return primary or (screens[0] if screens else None)

        # 收集候选中心点
        points = []
        try:
            mw = _widgets.maya_main_window()
            if mw is not None:
                points.append(mw.frameGeometry().center())
        except Exception:
            pass
        try:
            points.append(self.frameGeometry().center())
        except Exception:
            pass

        # 优先使用 Qt5.10+ 的 screenAt；老版本 Qt 5.6 没有此方法
        screen_at = getattr(QtGui.QGuiApplication, 'screenAt', None)
        if screen_at is None:
            screen_at = getattr(QtWidgets.QApplication, 'screenAt', None)

        for p in points:
            if screen_at is not None:
                try:
                    s = screen_at(p)
                    if s is not None:
                        return s
                except Exception:
                    pass
            # 回退：遍历屏幕几何
            for s in screens:
                try:
                    if s.geometry().contains(p):
                        return s
                except Exception:
                    pass

        return primary or screens[0]

    def take_snapshot_direct(self):
        """直接调用 ProjectManager 截图；当前选中子类型时保存到子类型，否则保存到资产。"""
        if not (self.pm and self.current_asset_type and self.selected_asset):
            self.show_warning(u'提示', u'请先选择项目和资产')
            return

        try:
            if self.selected_subtype:
                path = self.pm.take_snapshot(
                    self.current_asset_type, self.selected_asset, self.selected_subtype
                )
            else:
                path = self.pm.take_snapshot(self.current_asset_type, self.selected_asset)

            if not path or not os.path.isfile(path):
                self.show_warning(u'失败', u'预览保存失败：未生成截图文件')
                return

            pix = QtGui.QPixmap(path)
            if pix.isNull():
                self.show_warning(u'失败', u'生成的预览图无效：{}'.format(path))
                return

            self.preview_label.setText('')
            self.preview_label.setPixmap(pix)
        except Exception as e:
            self.show_warning(u'失败', u'直接截图失败: {}'.format(str(e)))

    def take_snapshot(self):
        """框选截图：隐藏窗口 → 抓目标屏幕 → 拖拽选区 → 裁切保存 preview.png"""
        if not (self.pm and self.selected_asset):
            self.show_warning(u'提示', u'请先选择资产与子类型')
            return

        # 先确定目标屏幕（Maya 主窗口所在屏幕），再隐藏窗口
        target_screen = self._resolve_target_screen()

        was_visible = self.isVisible()
        if was_visible:
            self.hide()

        def _restore_window():
            if was_visible:
                self.show()
                self.raise_()
                self.activateWindow()

        def _start():
            try:
                screen = target_screen or QtWidgets.QApplication.primaryScreen()
                if not screen:
                    self.show_warning(u'失败', u'无法获取屏幕')
                    _restore_window()
                    return
                QtCore.QTimer.singleShot(80, lambda: _grab(screen))
            except Exception as e:
                self.show_warning(u'失败', u'启动截图失败: {}'.format(str(e)))
                _restore_window()

        def _grab(screen):
            try:
                # 抓屏
                try:
                    full_pix = _grab_screen_pixmap(screen)
                except Exception as e:
                    self.show_warning(u'失败', u'抓屏失败: {}'.format(str(e)))
                    _restore_window()
                    return

                screen_geo = screen.geometry()
                if full_pix is None or full_pix.isNull() or full_pix.width() == 0:
                    self.show_warning(u'失败', u'抓屏失败（可能是硬件加速视图导致）')
                    _restore_window()
                    return

                selector = ui_openpipeline.ScreenRegionSelector(full_pix, screen_geo)
                self._snapshot_selector = selector

                def on_region(global_rect):
                    try:
                        pix = ui_openpipeline.crop_region_from_screenshot(
                            full_pix, screen_geo, global_rect
                        )
                        if pix.isNull() or pix.width() < 2 or pix.height() < 2:
                            self.show_warning(u'失败', u'截取区域无效')
                            return
                        if self.selected_subtype:
                            target_dir = os.path.join(
                                self.pm.get_asset_dir(
                                    self.current_asset_type, self.selected_asset
                                ),
                                'components', self.selected_subtype
                            )
                        else:
                            target_dir = self.pm.get_asset_dir(self.current_asset_type, self.selected_asset)
                        if not os.path.exists(target_dir):
                            os.makedirs(target_dir)
                        target_path = os.path.join(target_dir, 'preview.png')
                        if pix.save(target_path, 'PNG'):
                            self.preview_label.setPixmap(pix)
                        else:
                            self.show_warning(u'失败', u'保存预览图失败')
                    except Exception as e:
                        self.show_warning(u'失败', u'截图保存出错: {}'.format(str(e)))
                    finally:
                        self._snapshot_selector = None
                        _restore_window()

                def on_cancel():
                    self._snapshot_selector = None
                    _restore_window()

                selector.region_selected.connect(on_region)
                selector.cancelled.connect(on_cancel)
                selector.show()
                selector.raise_()
                selector.activateWindow()
                selector.setFocus()
            except Exception as e:
                self.show_warning(u'失败', u'截图出错: {}'.format(str(e)))
                _restore_window()

        QtCore.QTimer.singleShot(200, _start)