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

多屏 / Maya 2019 (Qt 5.6) 兼容说明：
  - Qt 5.6 上 `QScreen.grabWindow(0)` 在多屏环境里可能返回「主屏截图」
    或「整个虚拟桌面」，不一定返回调用它的那块屏，导致框选截图时背景
    显示的是另一块屏上的 Maya。
  - 修复策略：优先用 `grabWindow(0, x, y, w, h)` 让 Qt 直接裁剪出目标屏；
    失败时才回退到 `grabWindow(0)` + 手动 crop；最后再做一次尺寸校验。
  - 需要看诊断日志时设置环境变量 OPENPIPELINE_DEBUG=1 再启动 Maya。
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


def _debug(msg):
    """诊断输出，环境变量 OPENPIPELINE_DEBUG=1 时打印。"""
    try:
        if os.environ.get('OPENPIPELINE_DEBUG', '0') == '1':
            print(u"[Snapshot] {}".format(msg))
    except Exception:
        pass


def _screen_info(screen):
    """返回屏幕的简短描述，用于诊断。"""
    if screen is None:
        return u"<None>"
    try:
        geo = screen.geometry()
        try:
            name = screen.name()
        except Exception:
            name = u"?"
        return u"{}(x={},y={},w={},h={})".format(
            name, geo.x(), geo.y(), geo.width(), geo.height())
    except Exception as e:
        return u"<err:{}>".format(repr(e))


def _get_screens():
    screens = []
    try:
        screens = QtGui.QGuiApplication.screens()
    except Exception:
        try:
            screens = QtWidgets.QApplication.screens()
        except Exception:
            pass
    return screens


def _get_primary_screen():
    try:
        return QtWidgets.QApplication.primaryScreen()
    except Exception:
        return None


def _normalize_screen_pixmap(pix, screen):
    """确保 pixmap 是目标屏幕（target screen）的完整截图。

    分三种情况：
      1. 尺寸直接匹配目标屏 → 原样返回；
      2. 尺寸匹配虚拟桌面 union → 按目标屏相对虚拟桌面的偏移 crop；
      3. 尺寸既不匹配目标屏也不匹配虚拟桌面（说明 grabWindow 抓错屏了）
         → 打印警告并返回原 pix，让上层提示用户。
    """
    if pix is None or pix.isNull():
        return pix
    try:
        geo = screen.geometry()
    except Exception:
        return pix
    if geo.width() <= 0 or geo.height() <= 0:
        return pix

    try:
        dpr = float(pix.devicePixelRatio() or 1.0)
    except Exception:
        dpr = 1.0
    if dpr <= 0:
        dpr = 1.0

    expected_w = geo.width() * dpr
    expected_h = geo.height() * dpr

    # 1. 精确匹配目标屏
    if abs(pix.width() - expected_w) <= 2 and abs(pix.height() - expected_h) <= 2:
        _debug(u"normalize: 尺寸匹配目标屏 {}x{}".format(pix.width(), pix.height()))
        return pix

    screens = _get_screens()

    # 2. 匹配虚拟桌面 union
    if screens:
        v_geo = None
        try:
            v_geo = screens[0].geometry()
            for s in screens[1:]:
                v_geo = v_geo.united(s.geometry())
        except Exception:
            v_geo = None

        if v_geo is not None:
            for try_dpr in (dpr, 1.0):
                v_w = v_geo.width() * try_dpr
                v_h = v_geo.height() * try_dpr
                if abs(pix.width() - v_w) <= 4 and abs(pix.height() - v_h) <= 4:
                    ox = int(round((geo.x() - v_geo.x()) * try_dpr))
                    oy = int(round((geo.y() - v_geo.y()) * try_dpr))
                    cw = int(round(geo.width() * try_dpr))
                    ch = int(round(geo.height() * try_dpr))
                    rect = QtCore.QRect(ox, oy, cw, ch).intersected(pix.rect())
                    if rect.width() > 0 and rect.height() > 0:
                        _debug(u"normalize: 从虚拟桌面 {}x{} 裁出目标屏 {}x{}".format(
                            pix.width(), pix.height(), cw, ch))
                        return pix.copy(rect)

    # 3. 检查 pixmap 是否匹配其它屏（说明 grabWindow 抓到了错误的屏）
    if screens:
        for s in screens:
            try:
                s_geo = s.geometry()
            except Exception:
                continue
            for try_dpr in (dpr, 1.0):
                s_w = s_geo.width() * try_dpr
                s_h = s_geo.height() * try_dpr
                if abs(pix.width() - s_w) <= 2 and abs(pix.height() - s_h) <= 2:
                    _debug(
                        u"normalize: grabWindow 抓错了屏"
                        u"（返回 {}x{}，匹配 {}，目标期望 {}x{}）".format(
                            pix.width(), pix.height(),
                            _screen_info(s),
                            int(expected_w), int(expected_h)))
                    return pix

    _debug(u"normalize: 无法识别 pixmap 尺寸 {}x{}（目标屏期望 {}x{}）".format(
        pix.width(), pix.height(), int(expected_w), int(expected_h)))
    return pix


def _zero_candidates():
    """grabWindow 需要的 0 参数候选（Py2 优先 long(0)）。"""
    out = []
    if PY2:
        try:
            out.append(long(0))  # noqa: F821
        except Exception:
            pass
    out.append(0)
    return out


def _grab_screen_pixmap(screen):
    """抓取目标屏幕的完整截图。

    修复要点（Maya 2019 / Qt 5.6 多屏问题）：
      1) 优先 `grabWindow(0, x, y, w, h)` 让 Qt 直接裁剪出目标屏区域，
         避免 grabWindow(0) 返回主屏或虚拟桌面导致背景错误；
      2) 若方式 1 失败，回退到 `grabWindow(0)` + `_normalize_screen_pixmap`；
      3) 再不行再尝试 QPixmap.grabWindow / shiboken2.VoidPtr。

    所有分支都会经过 `_normalize_screen_pixmap` 做最终校验。
    """
    last_error = None

    try:
        geo = screen.geometry()
    except Exception:
        geo = None

    grab_func = getattr(screen, "grabWindow", None)

    # ---- 策略 1：带 x/y/w/h 参数抓目标屏区域 ----
    if callable(grab_func) and geo is not None and geo.width() > 0 and geo.height() > 0:
        for zero in _zero_candidates():
            try:
                pix = grab_func(zero, geo.x(), geo.y(), geo.width(), geo.height())
                if pix is not None and not pix.isNull() and pix.width() > 0:
                    try:
                        dpr = float(pix.devicePixelRatio() or 1.0)
                    except Exception:
                        dpr = 1.0
                    exp_w = geo.width() * dpr
                    exp_h = geo.height() * dpr
                    if (abs(pix.width() - exp_w) <= max(4, exp_w * 0.02)
                            and abs(pix.height() - exp_h) <= max(4, exp_h * 0.02)):
                        _debug(u"grab: 方式1成功 (x,y,w,h) -> {}x{}".format(
                            pix.width(), pix.height()))
                        return pix
                    # 尺寸对不上，交给 normalize 处理
                    normalized = _normalize_screen_pixmap(pix, screen)
                    if normalized is not None and not normalized.isNull():
                        return normalized
            except Exception as e:
                last_error = e

    # ---- 策略 2：primary screen grabWindow(0) 抓整个桌面 + normalize ----
    primary = _get_primary_screen()
    grab_screens = []
    if primary is not None:
        grab_screens.append(primary)
    if screen is not None and screen is not primary:
        grab_screens.append(screen)

    for gs in grab_screens:
        gf = getattr(gs, "grabWindow", None)
        if not callable(gf):
            continue
        for zero in _zero_candidates():
            try:
                pix = gf(zero)
                if pix is not None and not pix.isNull() and pix.width() > 0:
                    _debug(u"grab: 方式2 grabWindow(0) on {} -> {}x{}".format(
                        _screen_info(gs), pix.width(), pix.height()))
                    return _normalize_screen_pixmap(pix, screen)
            except Exception as e:
                last_error = e
            try:
                pix = gf(zero, 0, 0, -1, -1)
                if pix is not None and not pix.isNull() and pix.width() > 0:
                    _debug(u"grab: 方式2b grabWindow(0,0,0,-1,-1) -> {}x{}".format(
                        pix.width(), pix.height()))
                    return _normalize_screen_pixmap(pix, screen)
            except Exception as e:
                last_error = e

    # ---- 策略 3：Qt4 遗留 API ----
    try:
        legacy = getattr(QtGui.QPixmap, "grabWindow", None)
        if callable(legacy):
            pix = legacy(0)
            if pix is not None and not pix.isNull() and pix.width() > 0:
                _debug(u"grab: 方式3 QPixmap.grabWindow(0) -> {}x{}".format(
                    pix.width(), pix.height()))
                return _normalize_screen_pixmap(pix, screen)
    except Exception as e:
        last_error = e

    # ---- 策略 4：shiboken2 VoidPtr(0) ----
    try:
        import shiboken2
        ptr = shiboken2.VoidPtr(0, False)
        if callable(grab_func):
            pix = grab_func(ptr)
            if pix is not None and not pix.isNull() and pix.width() > 0:
                _debug(u"grab: 方式4 VoidPtr(0) -> {}x{}".format(pix.width(), pix.height()))
                return _normalize_screen_pixmap(pix, screen)
    except Exception as e:
        last_error = e

    raise RuntimeError(
        u'当前 Maya/Qt 环境不提供可用的屏幕抓取接口: {}'.format(repr(last_error))
    )


class SnapshotMixin(object):
    """截图功能 Mixin，需与宿主对话框组合使用。"""

    def _resolve_target_screen(self):
        """返回 Maya 主窗口（场景）所在的屏幕。"""
        screens = _get_screens()
        primary = _get_primary_screen()

        _debug(u"resolve: screens={}, primary={}".format(
            [_screen_info(s) for s in screens], _screen_info(primary)))

        if not screens or len(screens) <= 1:
            return primary or (screens[0] if screens else None)

        points = []
        try:
            mw = _widgets.maya_main_window()
            if mw is not None:
                c = mw.frameGeometry().center()
                points.append((u"maya_window", c))
        except Exception:
            pass
        try:
            c = self.frameGeometry().center()
            points.append((u"dialog", c))
        except Exception:
            pass

        for tag, p in points:
            _debug(u"resolve: 候选 {} center=({},{})".format(tag, p.x(), p.y()))

        screen_at = getattr(QtGui.QGuiApplication, 'screenAt', None)
        if screen_at is None:
            screen_at = getattr(QtWidgets.QApplication, 'screenAt', None)

        for tag, p in points:
            if screen_at is not None:
                try:
                    s = screen_at(p)
                    if s is not None:
                        _debug(u"resolve: screenAt({}) -> {}".format(tag, _screen_info(s)))
                        return s
                except Exception:
                    pass
            for s in screens:
                try:
                    if s.geometry().contains(p):
                        _debug(u"resolve: geometry.contains({}) -> {}".format(
                            tag, _screen_info(s)))
                        return s
                except Exception:
                    pass

        _debug(u"resolve: 全部失败，回退 primary={}".format(_screen_info(primary)))
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
        _debug(u"take_snapshot: target_screen = {}".format(_screen_info(target_screen)))

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
                screen = target_screen or _get_primary_screen()
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

                # ---- 抓屏后校验：pixmap 尺寸是否匹配目标屏 ----
                try:
                    dpr_check = float(full_pix.devicePixelRatio() or 1.0)
                except Exception:
                    dpr_check = 1.0
                exp_w = screen_geo.width() * dpr_check
                exp_h = screen_geo.height() * dpr_check
                mismatch_w = abs(full_pix.width() - exp_w) > max(4, exp_w * 0.02)
                mismatch_h = abs(full_pix.height() - exp_h) > max(4, exp_h * 0.02)
                if mismatch_w or mismatch_h:
                    _debug(
                        u"take_snapshot: 抓屏尺寸 {}x{} 与目标屏 {}x{} 不符，"
                        u"将按比例强制裁剪".format(
                            full_pix.width(), full_pix.height(),
                            int(exp_w), int(exp_h)))
                    # 尝试按比例强制裁出一块 —— 至少避免背景明显错位
                    try:
                        sx = 0
                        sy = 0
                        sw = min(full_pix.width(), int(round(exp_w)))
                        sh = min(full_pix.height(), int(round(exp_h)))
                        if sw > 0 and sh > 0:
                            full_pix = full_pix.copy(
                                QtCore.QRect(sx, sy, sw, sh))
                    except Exception:
                        pass

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
                            target_dir = self.pm.get_asset_dir(
                                self.current_asset_type, self.selected_asset)
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