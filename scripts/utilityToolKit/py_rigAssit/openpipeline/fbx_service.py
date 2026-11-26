# -*- coding: utf-8 -*-
# .FileName:fbx_service.py
"""
OpenPipeline 的 FBX 导出集中模块：同步导出 / 后台导出 / UE 后续步骤 / 右键菜单。

由 py_rigAssit.openpipeline.version_context 调用。
本模块自带 PathService 所需的路径属性，不从 version_context 导入任何东西，
避免 version_context <-> fbx_service 循环导入。
"""
try:
    from importlib import reload
except ImportError:
    pass

import os
import sys
import io
import json
import logging
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

from ui_framework.core.qtCompat import *
from Pipeline import file_operations as file_ops
from .text_utils import _u
from .asset_info import ENABLE_MAYABATCH


try:
    import maya.cmds as cmds
    import maya.mel as mel
    IN_MAYA = True
except Exception:
    IN_MAYA = False


# ---------------------------------------------------------------------------
# 后台 Maya 工具（内联，避免依赖 work_patch / 其它工具包的路径映射）
# ---------------------------------------------------------------------------
def get_maya_batch_executable():
    """定位 mayabatch.exe，找不到时退回 maya.exe（调用方加 -batch）。
    返回 (路径, 已尝试的路径列表)。
    """
    tried = []

    def _check(path):
        if not path:
            return None
        tried.append(path)
        return path if os.path.isfile(path) else None

    def _from_dir(directory):
        if not directory:
            return None
        for name in ("mayabatch.exe", "mayabatch", "maya.exe", "maya"):
            found = _check(os.path.join(directory, name))
            if found:
                return found
        return None

    for env_name in ("PY_RIGASSIT_MAYA_BATCH", "MAYA_BATCH_EXECUTABLE"):
        override = os.environ.get(env_name)
        if override:
            found = _check(override)
            if found:
                return found, tried

    found = _from_dir(os.path.dirname(sys.executable or "") if IN_MAYA else "")
    if found:
        return found, tried

    maya_location = os.environ.get("MAYA_LOCATION", "")
    if maya_location:
        found = _from_dir(os.path.join(maya_location, "bin"))
        if found:
            return found, tried

    if not IN_MAYA:
        return None, tried

    for flag in ("installPath", "executablePath"):
        try:
            value = cmds.about(**{flag: True})
        except Exception:
            value = ""
        if not value:
            continue
        directories = [value, os.path.join(value, "bin")]
        if flag == "executablePath":
            directories.insert(0, os.path.dirname(value))
        for directory in directories:
            found = _from_dir(directory)
            if found:
                return found, tried

    try:
        version = cmds.about(version=True)
    except Exception:
        version = ""

    try:
        import _winreg as winreg
    except ImportError:
        try:
            import winreg
        except ImportError:
            winreg = None
    if winreg and version:
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub_key in (r"SOFTWARE\Autodesk\Maya\{}\SetupInstallPath".format(version),
                            r"SOFTWARE\Autodesk\Maya\{}".format(version)):
                install = ""
                try:
                    key = winreg.OpenKey(hive, sub_key)
                    try:
                        for value_name in ("InstallPath", "SetupInstallPath", ""):
                            try:
                                install = winreg.QueryValueEx(key, value_name)[0]
                                break
                            except OSError:
                                continue
                    finally:
                        winreg.CloseKey(key)
                except Exception:
                    continue
                found = _from_dir(os.path.join(install, "bin"))
                if found:
                    return found, tried

    roots = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        r"C:\Program Files\Autodesk",
        r"D:\Program Files\Autodesk",
    ]
    for root in roots:
        autodesk = root if root.lower().endswith("autodesk") else os.path.join(root, "Autodesk")
        if not os.path.isdir(autodesk):
            continue
        directories = []
        if version:
            directories.append(os.path.join(autodesk, "Maya{}".format(version), "bin"))
        try:
            for name in sorted(os.listdir(autodesk), reverse=True):
                if name.lower().startswith("maya") and os.path.isdir(os.path.join(autodesk, name, "bin")):
                    directories.append(os.path.join(autodesk, name, "bin"))
        except Exception:
            pass
        for directory in directories:
            found = _from_dir(directory)
            if found:
                return found, tried

    return None, tried


def _py_literal(value):
    """转成可安全嵌入 Python 源码的 ASCII 字面量。"""
    return json.dumps(value, ensure_ascii=True)


def build_python_mel(worker_path):
    """生成 MEL 启动脚本（Maya 的 -script 只保证加载 MEL）。"""
    path = worker_path.replace("\\", "/").replace("'", "\\'")
    python_code = "import runpy; runpy.run_path('{}')".format(path)
    mel_code = python_code.replace("\\", "\\\\").replace('"', '\\"')
    return 'python("{}");\n'.format(mel_code)


def build_worker_script(status_path, payload, body):
    """生成后台 Maya worker 脚本；body 为已缩进 4 空格的代码。"""
    existing_paths = [p for p in sys.path if p and os.path.exists(p)]
    paths_json = _py_literal(json.dumps(existing_paths, ensure_ascii=True))
    status_json = _py_literal(json.dumps(status_path, ensure_ascii=True))
    payload_json = _py_literal(json.dumps(payload, ensure_ascii=True))
    return """# -*- coding: utf-8 -*-
# Auto-generated by py_rigAssit.openpipeline - do not edit.
import os
import sys
import json
import traceback

sys.path[:0] = json.loads({paths})

STATUS = json.loads({status})
PAYLOAD = json.loads({payload})

result = {{"ok": False, "error": ""}}
try:
{body}
    result["ok"] = True
except Exception:
    result["error"] = traceback.format_exc()
finally:
    try:
        with open(STATUS, "w") as _fh:
            json.dump(result, _fh, ensure_ascii=True)
    except Exception:
        pass
""".format(paths=paths_json, status=status_json, payload=payload_json, body=body)


def _show_info_inview(title=u"Finished", color='yellow'):
    try:
        import HelpImageUI as help
        help.inView_Message(color, u"{}".format(_u(title)))
    except Exception:
        pass


# 后台 worker 的实际工作部分（4 空格缩进，嵌入 build_worker_script 的 try 块）。
_FBX_EXPORT_BODY = '''    import os
    import maya.cmds as cmds
    import maya.mel as mel
    from Pipeline import file_operations as file_ops

    cmds.file(new=True, force=True)
    file_ops.import_file(PAYLOAD["source_file"])

    skins = cmds.ls(type='skinCluster') or []
    for skin in skins:
        if not cmds.objExists(skin):
            continue
        input_nodes = cmds.listConnections(skin + '.matrix') or []
        for node in input_nodes:
            if cmds.nodeType(node) == 'multMatrix':
                jnt = cmds.connectionInfo(node + '.matrixIn[0]', sourceFromDestination=1)
                ot_nodes = cmds.connectionInfo(node + '.matrixSum', destinationFromSource=1) or []
                for ot in ot_nodes:
                    if skin == ot.split('.')[0]:
                        cmds.connectAttr(jnt, ot, f=1)

    export_objects = []
    for obj in (PAYLOAD["geo_group"], PAYLOAD["root_joint"]):
        if obj and cmds.objExists(obj):
            export_objects.append(obj)
    if not export_objects:
        raise RuntimeError("Export objects missing in batch Maya")

    cmds.select(clear=True)
    cmds.select(export_objects, r=True)
    mel.eval(u'file -force -options "v=0;" -typ "FBX export" -pr -es "{}";'.format(PAYLOAD["fbx_path"]))
    if not os.path.isfile(PAYLOAD["fbx_path"]):
        raise RuntimeError("FBX was not written: {}".format(PAYLOAD["fbx_path"]))
'''


class FBXExporter(object):
    """FBX 导出服务，由 version_context.VersionContextMenu 调用。"""

    def __init__(self, main_window):
        self.ui = main_window

    # ------------------------------------------------------------------
    # 路径属性：与 version_context.PathService 保持一致
    # ------------------------------------------------------------------
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

    def asset_dir(self, asset_name=None):
        asset_name = asset_name or self.asset
        return self.pm.get_asset_dir(self.asset_type, asset_name)

    def subtype_dir(self):
        return os.path.join(self.asset_dir(), 'components', self.subtype)

    def version_path(self, version_filename):
        return os.path.join(self.subtype_dir(), 'workshop', version_filename)

    # ------------------------------------------------------------------
    # 原有同步导出（行为保持不变）
    # ------------------------------------------------------------------
    def ensure_scene_safe(self):
        if not IN_MAYA:
            return False

        modified = cmds.file(q=True, modified=True)

        if not modified:
            return True

        reply = QtWidgets.QMessageBox.question(
            self.ui,
            u"警告",
            u"当前场景有未保存内容。\n继续导出会清空当前场景，是否继续？",
            QtWidgets.QMessageBox.Yes |
            QtWidgets.QMessageBox.No
        )

        return reply == QtWidgets.QMessageBox.Yes

    def get_export_objects(self):
        if not hasattr(self.ui, "fbx_config"):
            raise RuntimeError("fbx_config missing")

        config = self.ui.fbx_config

        if len(config) < 2:
            raise RuntimeError("FBX config invalid")

        geo_grp = config[0]
        root_joint = config[1]

        export_objects = []

        if geo_grp and cmds.objExists(geo_grp):
            export_objects.append(geo_grp)

        if root_joint and cmds.objExists(root_joint):
            export_objects.append(root_joint)

        if not export_objects:
            raise RuntimeError("Export objects missing")
        self.geo_grp = geo_grp
        self.root_joint = root_joint
        return export_objects

    def delete_matrix_nodes(self):
        skins = cmds.ls(type='skinCluster') or []
        for skin in skins:
            if not cmds.objExists(skin):
                continue
            input_nodes = cmds.listConnections(skin + '.matrix') or []
            for node in input_nodes:
                if cmds.nodeType(node) == 'multMatrix':
                    jnt = cmds.connectionInfo(node + '.matrixIn[0]', sourceFromDestination=1)
                    ot_nodes = cmds.connectionInfo(node + '.matrixSum', destinationFromSource=1) or []
                    for ot in ot_nodes:
                        if skin == ot.split('.')[0]:
                            cmds.connectAttr(jnt, ot, f=1)

    def delete_blendshape_nodes(self):
        meshes = cmds.ls(type="mesh", long=True) or []
        transforms = []

        for mesh in meshes:
            parent = cmds.listRelatives(mesh, parent=True, fullPath=True) or []
            if parent:
                transforms.extend(parent)

        transforms = list(set(transforms))
        for obj in transforms:
            history = cmds.listHistory(obj) or []
            blend_nodes = cmds.ls(history, type='blendShape') or []

            for bs in blend_nodes:
                if cmds.objExists(bs):
                    try:
                        cmds.delete(bs)
                    except Exception:
                        pass

    def cleanup_scene(self):
        self.delete_matrix_nodes()
        # self.delete_blendshape_nodes()

    def build_fbx_path(self, version_filename):
        fbx_dir = os.path.join(self.subtype_dir(), "fbx")
        if not os.path.exists(fbx_dir):
            os.makedirs(fbx_dir)
        base_name = os.path.splitext(_u(version_filename))[0]
        fbx_path = os.path.join(fbx_dir, base_name + u".fbx")
        return fbx_path.replace("\\", "/")

    def export_selected_to_fbx(self, fbx_path):
        export_objects = self.get_export_objects()
        cmds.select(clear=True)
        cmds.select(export_objects, r=True)
        mel.eval(u'file -force -options "v=0;" -typ "FBX export" -pr -es "{}";'.format(_u(fbx_path)))
        return os.path.exists(fbx_path)

    def _export_to_unreal(self, fbx_path, asset_type=None, asset=None, ue_config=None):
        try:
            from py_rigAssit.common.to_ue.fbx_to_unreal import export_to_unreal, save_json

            ue_config = ue_config if isinstance(ue_config, dict) else getattr(self.ui, 'UE_CONFIG', {})
            unreal_editor = ue_config.get('UnrealEditor', '')
            ue_project = ue_config.get('UE_PROJECT', '')
            content = ue_config.get('CONTENT', '')
            if not unreal_editor or not ue_project or not content:
                raise RuntimeError(u'请先在 FBX 导出设置中填写完整的 UE 配置')

            obj_fold = {"chr": "Chr",
                        "Chr": "Chr",
                        "char": "Chr",
                        "prp": "Prp",
                        "Prp": "Prp"}
            asset_type = asset_type or self.asset_type
            asset = asset or self.asset
            if content and content != "None" and content != "none":
                ue_content_path = u"/Game/{}/{}".format(_u(content), _u(obj_fold.get(asset_type, "Chr")))
            else:
                ue_content_path = u"/Game/{}".format(_u(obj_fold.get(asset_type, "Chr")))
            export_to_unreal(fbx_path, unreal_editor, ue_project, ue_content_path, asset)
        except Exception as e:
            self.ui.show_warning_delayed(
                u'UE 导出警告',
                u'{}\n前往ue手动运行ue_importer.py移动材质贴图即可'.format(_u(e)))

    def _save_json_for_ue(self, fbx_path, asset_type=None, asset=None, ue_config=None):
        try:
            if not isinstance(ue_config, dict):
                ue_config = getattr(self.ui, 'UE_CONFIG', None)
            if not isinstance(ue_config, dict):
                ue_config = {}
            content = ue_config.get('CONTENT', '') or ''
            obj_fold = {"chr": "Chr",
                        "Chr": "Chr",
                        "char": "Chr",
                        "prp": "Prp",
                        "Prp": "Prp"}
            asset_type = asset_type or self.asset_type
            asset = asset or self.asset
            if content and content != "None" and content != "none":
                ue_content_path = u"/Game/{}/{}".format(_u(content), _u(obj_fold.get(asset_type, "Chr")))
            else:
                ue_content_path = u"/Game/{}".format( _u(obj_fold.get(asset_type, "Chr")))
            config = {
                "fbx": _u(fbx_path),
                "base_path": ue_content_path,
                "name": _u(asset)
            }
            config_path = os.path.join(os.path.expanduser("~"), "Unreal Projects", "ue_import.json")
            config_dir = os.path.dirname(config_path)
            if not os.path.isdir(config_dir):
                os.makedirs(config_dir)
            with open(config_path, "w") as f:
                json.dump(config, f)
            print(config_dir, u"[OpenPipeline] ue_import.json 已写入: %s", _u(config_path))
            logger.debug(u"[OpenPipeline] ue_import.json 已写入: %s", _u(config_path))
            return True
        except Exception as e:
            logger.warning(u"[OpenPipeline] 写 ue_import.json 失败: %s", e)
            return False

    def export_fbx_for_version(self, version_filename, to_ue=False):
        if not IN_MAYA:
            self.ui.show_critical(u"错误", u"只能在 Maya 中运行")
            return False

        if not self.ensure_scene_safe():
            return False

        version_path = self.version_path(version_filename)

        if not os.path.exists(version_path):
            raise RuntimeError(u"Version file missing:\n{}".format(_u(version_path)))

        fbx_path = self.build_fbx_path(version_filename)

        try:
            cmds.file(new=True, force=True)
            file_ops.import_file(version_path)
            self.cleanup_scene()
            ok = self.export_selected_to_fbx(fbx_path)
            if ok:
                cmds.file(new=True, force=True)
                if to_ue:
                    self._export_to_unreal(fbx_path)
                else:
                    self._save_json_for_ue(fbx_path)
                    _show_info_inview(u'FBX 导出完成', 'green')
            if not ok:
                raise RuntimeError("FBX export failed")

            return fbx_path

        except Exception as e:
            self.ui.show_warning_delayed(u'导出失败', _u(e))
            return False

    # ------------------------------------------------------------------
    # 后台批量导出（不触碰当前 Maya 场景，也不需要确认保存）
    # ------------------------------------------------------------------
    def export_fbx_for_version_batch(self, version_filename, to_ue=False):
        """启动独立的后台Maya导出该版本的 FBX。"""
        if not IN_MAYA:
            self.ui.show_critical(u"错误", u"只能在 Maya 中运行")
            return False

        version_file = self.version_path(version_filename)
        if not os.path.exists(version_file):
            raise RuntimeError(u"Version file missing:\n{}".format(_u(version_file)))

        config = getattr(self.ui, 'fbx_config', None) or []
        if len(config) < 2 or not config[0] or not config[1]:
            self.ui.show_warning(u'错误', u'请先在「⚙ 设置FBX导出对象」中配置导出对象')
            return False
        geo_grp = _u(config[0])
        root_joint = _u(config[1])

        fbx_path = self.build_fbx_path(version_filename)

        exe, searched = get_maya_batch_executable()
        if not exe:
            tried = "\n".join(searched[-10:]) if searched else u"（未找到可检查的目录）"
            self.ui.show_critical(
                u"错误",
                u"找不到 mayabatch.exe / maya.exe。已尝试:\n{}\n\n"
                u"可在 Maya Script Editor 执行 "
                u"\"import sys, os; print(os.path.dirname(sys.executable))\" 查看安装目录。".format(tried)
            )
            return False

        # 启动时捕获界面状态，避免异步期间用户切换资产导致 UE 路径错误。
        asset_type = self.asset_type
        asset = self.asset
        ue_config = dict(getattr(self.ui, 'UE_CONFIG', {}) or {})

        job_dir = tempfile.mkdtemp(prefix="py_openpipeline_fbx_")
        worker_path = os.path.join(job_dir, "export_fbx_batch.py")
        mel_path = os.path.join(job_dir, "run_export.mel")
        status_path = os.path.join(job_dir, "status.json")
        log_path = os.path.join(job_dir, "maya_batch.log")

        payload = {
            "source_file": _u(version_file).replace("\\", "/"),
            "fbx_path": _u(fbx_path),
            "geo_group": geo_grp,
            "root_joint": root_joint,
        }
        try:
            with open(worker_path, "w") as fh:
                fh.write(build_worker_script(status_path, payload, _FBX_EXPORT_BODY))
            with open(mel_path, "w") as fh:
                fh.write(build_python_mel(worker_path))
        except Exception as e:
            shutil.rmtree(job_dir, ignore_errors=True)
            self.ui.show_critical(u'错误', u'生成后台导出脚本失败: {}'.format(_u(e)))
            return False

        log_fh = open(log_path, "w")
        args = [exe]
        if not os.path.basename(exe).lower().startswith("mayabatch"):
            args.append("-batch")
        args.extend(["-script", mel_path])
        try:
            proc = subprocess.Popen(
                args,
                cwd=os.path.dirname(version_file),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            log_fh.close()
            shutil.rmtree(job_dir, ignore_errors=True)
            self.ui.show_critical(u'错误', u'启动后台 Maya 失败: {}'.format(_u(e)))
            return False

        _show_info_inview(u'FBX 后台导出已启动', 'yellow')

        _jobs = getattr(self.ui, '_op_fbx_batch_jobs', None)
        if _jobs is None:
            _jobs = []
            self.ui._op_fbx_batch_jobs = _jobs
        job = {"proc": proc, "dir": job_dir, "elapsed": 0}
        _jobs.append(job)

        timer = QtCore.QTimer(self.ui)
        timer.setInterval(1000)
        job["timer"] = timer

        def _on_timeout():
            job["elapsed"] += 1
            if proc.poll() is None:
                if job["elapsed"] >= 1800:  # 30 分钟超时保护
                    timer.stop()
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        log_fh.close()
                    except Exception:
                        pass
                    if job in _jobs:
                        _jobs.remove(job)
                    timer.deleteLater()
                    self.ui.show_warning_delayed(
                        u'导出失败',
                        u'后台 Maya 导出 FBX 超时（30分钟），已终止。\n日志: {}'.format(log_path))
                return

            timer.stop()
            try:
                timer.timeout.disconnect(_on_timeout)
            except Exception:
                pass
            timer.deleteLater()
            if job in _jobs:
                _jobs.remove(job)
            try:
                log_fh.close()
            except Exception:
                pass

            result = {}
            if os.path.isfile(status_path):
                try:
                    with open(status_path, "r") as fh:
                        result = json.load(fh)
                except Exception:
                    result = {}

            if result.get("ok"):
                shutil.rmtree(job_dir, ignore_errors=True)
                _show_info_inview(u'FBX 后台导出完成', 'green')

                def _finish():
                    if to_ue:
                        self._export_to_unreal(fbx_path, asset_type, asset, ue_config)
                    else:
                        self._save_json_for_ue(fbx_path, asset_type, asset, ue_config)

                QtCore.QTimer.singleShot(500, _finish)

            else:
                error = result.get("error") or u"未知错误（退出码: {}）".format(proc.returncode)
                self.ui.show_warning_delayed(
                    u'导出失败',
                    u'后台 Maya 导出 FBX 失败:\n{}\n\n日志: {}'.format(
                        _u(error)[-1500:], log_path))

        timer.timeout.connect(_on_timeout)
        timer.start()
        return True


def add_fbx_menu(menu, version_name, service, add_menu_label, safe_run):
    """构建 Export FBX 子菜单，由 version_context.show_version_menu 调用。"""
    add_menu_label(menu, u"⭐ fbx:")
    fbx_menu = menu.addMenu(u"Export FBX")
    export_fbx_action = fbx_menu.addAction(u"📤 导出 FBX")
    export_fbx_ue_action = fbx_menu.addAction(u'📤 导出FBX to UE')
    export_batch_action = fbx_menu.addAction(u'🚀 后台 Maya 导出 FBX')
    export_batch_ue_action = fbx_menu.addAction(u'🚀 后台 Maya 导出 FBX to UE')
    export_batch_action.setEnabled(ENABLE_MAYABATCH)
    export_batch_ue_action.setEnabled(ENABLE_MAYABATCH)
    export_fbx_action.triggered.connect(
        lambda: safe_run(lambda: service.export_fbx_for_version(version_name, to_ue=False)))
    export_fbx_ue_action.triggered.connect(
        lambda: safe_run(lambda: service.export_fbx_for_version(version_name, to_ue=True)))
    export_batch_action.triggered.connect(
        lambda: safe_run(lambda: service.export_fbx_for_version_batch(version_name, to_ue=False)))
    export_batch_ue_action.triggered.connect(
        lambda: safe_run(lambda: service.export_fbx_for_version_batch(version_name, to_ue=True)))
