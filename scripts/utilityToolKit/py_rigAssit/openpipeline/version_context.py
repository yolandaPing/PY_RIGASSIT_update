# -*- coding: utf-8 -*-
# .FileName:version_context.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2025/12/13 13:02
"""
版本右键菜单功能模块
处理资产、任务、版本列表的右键菜单及相关操作。
"""
import os
import shutil
from datetime import datetime
try:
    from importlib import reload
except ImportError:
    pass

try:
    from ui_framework.core.qtCompat import *
except:
    from CommonUse.qtCompat import *

from Pipeline.pipelineConfig import OpenPipelineConfig
from Pipeline.projectManager import ProjectManager

try:
    from Pipeline.pipelineUtils import *
    from Pipeline.pipelineUtils import load_projects_from_xml, get_projects_xml_path, ensure_projects_xml, \
        add_project_to_xml, open_folder_in_explorer, open_file_in_explorer

except ImportError as e:
    try:
        from .pipelineUtils import *
    except ImportError:
        print(u"version_context导入工具pipeline_utils模块失败")

try:
    import maya.cmds as cmds
    import maya.mel as mel
    import maya.OpenMaya as om
    IN_MAYA = True
except Exception:
    IN_MAYA = False

_cfg = OpenPipelineConfig()

import maya.cmds as cmds


def is_scene_strictly_empty():
    all_nodes = cmds.ls(long=True) or []

    default_nodes = [
        'persp', 'top', 'front', 'side',
        'defaultLightSet', 'defaultObjectSet',
        'defaultRenderUtilityList', 'defaultShaderList',
        'defaultTextureList', 'lightLinker1',
        'postProcessList1', 'renderGlobalsList1',
        'defaultRenderGlobals', 'defaultResolution',
        'lambert1', 'particleCloud1', 'standardSurface1',
        'time1', 'sequenceManager1', 'hardwareRenderingGlobals',
        'renderPartition', 'defaultLightList1', 'defaultShaderList1',
        'defaultRenderUtilityList1', 'defaultRenderingList1', 'lightList1',
        'defaultTextureList1', 'initialShadingGroup', 'initialParticleSE',
        'initialMaterialInfo', 'shaderGlow1', 'dof1', 'defaultRenderQuality',
        'defaultViewColorManager', 'defaultColorMgtGlobals', 'hardwareRenderGlobals',
        'characterPartition', 'defaultHardwareRenderGlobals', 'ikSystem', 'hyperGraphInfo',
        'hyperGraphLayout', 'globalCacheControl', 'strokeGlobals', 'dynController1', '|persp|perspShape',
        '|top|topShape', '|front|frontShape', '|side|sideShape', 'shapeEditorManager', 'poseInterpolatorManager',
        'layerManager', 'defaultLayer', 'renderLayerManager', 'defaultRenderLayer'
    ]

    # 将默认节点转换为长名称格式以便比较
    default_long_names = []
    for node in default_nodes:
        try:
            long_name = cmds.ls(node, long=True)
            if long_name:
                default_long_names.extend(long_name)
        except:
            pass

    for node in all_nodes:
        if node not in default_long_names:
            return False

    return True

def add_menu_label(menu, text):
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(widget)
    label = QtWidgets.QLabel(text)
    label.setStyleSheet("color: yellow;")
    layout.addWidget(label)
    layout.setContentsMargins(20, 2, 5, 2)
    widget.setLayout(layout)

    label_fbx_action = QtWidgets.QWidgetAction(menu)
    label_fbx_action.setDefaultWidget(widget)
    menu.addAction(label_fbx_action)


def show_asset_context_menu(main_window, position):
    """显示资产列表的右键菜单"""
    if not main_window.pm or not main_window.current_asset_type:
        return
    item = main_window.asset_list.itemAt(position)
    if not item:
        return
    menu = QtWidgets.QMenu()
    open_action = menu.addAction(u'📂 打开资产路径')
    open_action.triggered.connect(lambda: open_asset_path(main_window, item.text()))
    menu.exec_(main_window.asset_list.mapToGlobal(position))


def show_subtype_context_menu(main_window, position):
    """显示任务列表的右键菜单"""
    if not main_window.pm or not main_window.current_asset_type or not main_window.selected_asset:
        return
    item = main_window.subtype_list.itemAt(position)
    if not item:
        return
    menu = QtWidgets.QMenu()
    open_action = menu.addAction(u'📂 打开任务路径')
    Import_action = menu.addAction('import Master')
    Reference_action = menu.addAction('reference Master')
    open_action.triggered.connect(lambda: open_subtype_path(main_window, item.text()))
    Import_action.triggered.connect(lambda: import_master(main_window, False))
    Reference_action.triggered.connect(lambda: reference_master(main_window, False))
    menu.exec_(main_window.subtype_list.mapToGlobal(position))


def show_version_context_menu(main_window, position):
    """显示版本列表的右键菜单（包含FBX导出选项）"""
    if not main_window.pm or not main_window.current_asset_type or not main_window.selected_asset or not main_window.selected_subtype:
        return
    item = main_window.version_list.itemAt(position)
    if not item:
        return

    version_filename = item.text()
    menu = QtWidgets.QMenu()
    open_action = menu.addAction(u'📂 打开版本路径')
    open_action.triggered.connect(lambda: open_version_path(main_window, version_filename))
    menu.addSeparator()
    set_master_action = menu.addAction(u'⚙ Set Master 📋 ')
    set_master_action.triggered.connect(main_window.set_master)
    menu.addSeparator()
    add_menu_label(menu, "⭐ fbx:")
    set_fbx_action = menu.addAction(u'⚙ 设置FBX导出对象')
    set_fbx_action.triggered.connect(main_window.set_fbx_export_objects)

    export_fbx_action = menu.addAction(u'📤 导出FBX ({} + {})'.format(
        main_window.fbx_config[0], main_window.fbx_config[1]
    ))
    export_fbx_UE_action = menu.addAction(u'📤 导出FBX to UE')
    export_fbx_action.setProperty('yellow', True)
    export_fbx_action.triggered.connect(lambda: export_fbx_for_version(main_window, version_filename, False))
    menu.addSeparator()
    export_fbx_UE_action.setProperty('yellow', True)
    export_fbx_UE_action.triggered.connect(lambda: export_fbx_for_version(main_window, version_filename, True))
    menu.addSeparator()

    file_info = get_file_info(main_window, version_filename)
    info_action = menu.addAction(u'📋 版本信息: {}'.format(version_filename))
    info_action.setEnabled(False)
    if file_info:
        info_action.setToolTip(version_filename + file_info)

    menu.addSeparator()

    # 菜单项：删除
    delete_action = menu.addAction(u'🗑️ 删除当前选择')
    delete_action.triggered.connect(lambda: delete_selected_version(main_window, version_filename))

    menu.exec_(main_window.version_list.mapToGlobal(position))


def open_asset_path(main_window, asset_name):
    """打开资产文件夹路径"""
    # from utils import open_folder_in_explorer
    if not main_window.pm or not main_window.current_asset_type:
        QtWidgets.QMessageBox.warning(main_window, u'错误', u'请先选择资产类型')
        return
    asset_dir = main_window.pm.get_asset_dir(main_window.current_asset_type, asset_name)
    if os.path.exists(asset_dir):
        open_folder_in_explorer(asset_dir.replace("/", "\\"))
    else:
        QtWidgets.QMessageBox.warning(main_window, u'错误', u'资产路径不存在:\n{}'.format(asset_dir))


def import_master(main_window, namespace=False):
    """Import Master文件"""
    if not main_window.pm or not main_window.current_asset_type:
        QtWidgets.QMessageBox.warning(main_window, u'错误', u'请先选择资产类型')
        return
    mf = main_window.pm.get_master_file(main_window.current_asset_type, main_window.selected_asset,
                                        main_window.selected_subtype)
    if not mf or not os.path.exists(mf):
        main_window.show_warning('错误', 'Master 文件不存在')
        return
    if IN_MAYA:
        try:
            if namespace:
                fname = mf.split("master")[-1]
                cmds.file(mf, i=True, namespace=fname.split(".ma")[0], options="v=0;")
            else:
                cmds.file(mf, i=True, options="v=0;")
            main_window.show_info_inview('Import Master Finished', "yellow")
        except Exception as e:
            main_window.show_warning('失败', str(e))
    else:
        main_window.show_info('路径', mf)


def reference_master(main_window, namespace=False):
    """Reference Master文件"""
    main_window.reference_master(namespace)


def open_subtype_path(main_window, subtype_name):
    """打开任务文件夹路径"""
    # from utils import open_folder_in_explorer
    if not main_window.pm or not main_window.current_asset_type or not main_window.selected_asset:
        QtWidgets.QMessageBox.warning(main_window, u'错误', u'请先选择资产')
        return
    subtype_dir = os.path.join(
        main_window.pm.get_asset_dir(main_window.current_asset_type, main_window.selected_asset),
        'components', subtype_name
    )
    if os.path.exists(subtype_dir):
        open_folder_in_explorer(subtype_dir.replace("/", "\\"))
    else:
        QtWidgets.QMessageBox.warning(main_window, u'错误', u'任务路径不存在:\n{}'.format(subtype_dir))


def open_version_path(main_window, version_name):
    """打开版本文件路径"""
    if not main_window.pm or not main_window.current_asset_type or not main_window.selected_asset or not main_window.selected_subtype:
        QtWidgets.QMessageBox.warning(main_window, u'错误', u'请先选择资产和任务')
        return
    version_path = os.path.join(
        main_window.pm.get_asset_dir(main_window.current_asset_type, main_window.selected_asset),
        'components', main_window.selected_subtype, 'workshop', version_name
    )
    if os.path.exists(version_path):
        open_file_in_explorer(version_path.replace("/", "\\"))
    else:
        QtWidgets.QMessageBox.warning(main_window, u'错误', u'版本文件不存在:\n{}'.format(version_path))


def get_file_info(main_window, version_filename):
    """获取版本文件的详细信息（大小、修改时间）"""
    asset_dir = main_window.pm.get_asset_dir(main_window.current_asset_type, main_window.selected_asset)
    file_path = os.path.join(asset_dir, 'components', main_window.selected_subtype, 'workshop', version_filename)
    if os.path.exists(file_path):
        try:
            size_bytes = os.path.getsize(file_path)
            mod_time = os.path.getmtime(file_path)
            return u"\n\n文件大小: {:.1f} KB\n最后修改: {}".format(
                size_bytes / 1024,
                datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
            )
        except:
            return u"\n\n(无法获取文件信息)"
    return ""


def delete_selected_version(main_window, version_filename):
    """删除选中的版本文件"""
    if not main_window.pm or not main_window.selected_asset or not main_window.selected_subtype:
        QtWidgets.QMessageBox.warning(main_window, '提示', '请先选择资产和任务')
        return

    asset_dir = main_window.pm.get_asset_dir(main_window.current_asset_type, main_window.selected_asset)
    task_dir = os.path.join(asset_dir, 'components', main_window.selected_subtype)
    workshop_dir = os.path.join(asset_dir, 'components', main_window.selected_subtype, 'workshop')
    file_path = os.path.join(workshop_dir, version_filename)

    if not os.path.exists(file_path):
        QtWidgets.QMessageBox.warning(main_window, u'错误', u'文件不存在:\n{}'.format(file_path))
        return

    # 确认对话框
    confirm_msg = u"确定要删除版本文件吗？\n\n文件路径: {}\n".format(file_path)
    reply = QtWidgets.QMessageBox.question(
        main_window, u'确认删除版本文件', confirm_msg,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No
    )

    if reply == QtWidgets.QMessageBox.Yes:
        try:
            # 备份到deleted文件夹（可选）
            backup_to_deleted_folder(file_path, asset_dir, main_window.selected_subtype, version_filename)
            os.remove(file_path)
            if not os.path.exists(file_path):
                QtWidgets.QMessageBox.information(main_window, u'成功', u'版本文件已删除')

                root_path = _cfg.get_project_root_path()
                project = _cfg.get_last_project().split("/")[-1]

                _pmg = ProjectManager(root_path, project)
                _pmg.write_note_info(task_dir, version_filename, u'Deleted', workshop=True)

                refresh_version_list(main_window)
            else:
                QtWidgets.QMessageBox.warning(main_window, u'删除失败', u'文件删除失败')
        except Exception as e:
            QtWidgets.QMessageBox.warning(main_window, u'删除失败', u'删除过程中发生错误:\n{}'.format(str(e)))


def backup_to_deleted_folder(file_path, asset_dir, subtype, filename):
    """备份文件到deleted文件夹"""
    try:
        deleted_dir = os.path.join(asset_dir, 'components', subtype, 'deleted')
        if not os.path.exists(deleted_dir):
            os.makedirs(deleted_dir)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = "{}_{}".format(timestamp, filename)
        backup_path = os.path.join(deleted_dir, backup_name)
        shutil.copy2(file_path, backup_path)
    except Exception as e:
        print(u"备份文件失败: {}".format(e))


def refresh_version_list(main_window):
    """刷新版本列表显示"""
    if not main_window.pm or not main_window.selected_asset or not main_window.selected_subtype:
        return
    versions = main_window.pm.get_workshop_versions(
        main_window.current_asset_type, main_window.selected_asset, main_window.selected_subtype
    )
    main_window.version_list.clear()
    for v in versions:
        main_window.version_list.addItem(v)


def export_fbx_for_version(main_window, version_filename, to_ue=False):
    """为选中的版本执行FBX导出操作"""
    if not IN_MAYA:
        QtWidgets.QMessageBox.warning(main_window, '错误', '此功能只能在Maya中运行')
        return

    if is_scene_strictly_empty() == False:
        mel.eval("file -f -new;")

    asset_dir = main_window.pm.get_asset_dir(main_window.current_asset_type, main_window.selected_asset)
    version_path = os.path.join(asset_dir, 'components', main_window.selected_subtype, 'workshop', version_filename)

    type_name = main_window.current_asset_type

    if not os.path.exists(version_path):
        QtWidgets.QMessageBox.warning(main_window, '错误', '版本文件不存在:\n{}'.format(version_path))
        return

    fbx_dir = os.path.join(asset_dir, 'components', main_window.selected_subtype, 'fbx')
    if not os.path.exists(fbx_dir):
        os.makedirs(fbx_dir)
    fbx_filename = "{}.fbx".format(main_window.selected_asset)
    fbx_path = os.path.join(fbx_dir, fbx_filename).replace("\\", "/")

    try:
        cmds.file(version_path, i=True)
        export_success = export_fbx_with_objects(main_window, fbx_path)
        if export_success:
            mel.eval("file -f -new;")
            obj_fold = {"chr": "Chr",
                            "Chr": "Chr",
                            "char": "Chr",
                            "prp": "Prp",
                            "Prp": "Prp"}
            base_name = main_window.selected_asset
            try:
                from work_patch.project_asset_browser.info import UnrealEditor, UE_PROJECT, CONTENT
                import work_patch.project_asset_browser.fbx_to_unreal as fbx_to_unreal
                reload(fbx_to_unreal)
                ue_content_path = "/Game/{}/{}".format(CONTENT, obj_fold[type_name])
                enable_to_ue = True
            except:
                enable_to_ue = False

            if to_ue and enable_to_ue:
                try:
                    om.MGlobal.displayInfo("run fbx to ue ......")
                    om.MGlobal.displayInfo(ue_content_path)
                    fbx_to_unreal.export_to_unreal(fbx_path, UnrealEditor, UE_PROJECT, ue_content_path, base_name)

                    QtWidgets.QMessageBox.information(main_window, 'FBX导入UE成功',
                                    u'FBX导入UE成功:\n\n导出对象: {}\n路径: {}\nUE项目: {}'.format(
                                        base_name, fbx_path, UE_PROJECT))

                except Exception as e:
                    QtWidgets.QMessageBox.warning(main_window,'导出UE失败', '{}\n前往ue手动运行ue_importer.py即可'.format(e))
    
            else:
                if enable_to_ue:
                    fbx_to_unreal.save_json(fbx_path, ue_content_path, base_name)
                QtWidgets.QMessageBox.information(main_window, '导出成功',
                                              u'FBX导出完成:\n\n导出对象: {} 和 {}\n导出路径: {}'.format(
                                                  main_window.fbx_config[0], main_window.fbx_config[1], fbx_path))
        else:
            QtWidgets.QMessageBox.warning(main_window, u'导出失败', u'FBX导出失败，请检查场景中的对象')
    except Exception as e:
        QtWidgets.QMessageBox.critical(main_window, u'错误', u'导出过程中发生错误:\n{}'.format(str(e)))

def delete_Matrix(Geo_grp="Geo_grp"):
    import pymel.core as pm
    get_mesh = pm.listRelatives(Geo_grp, s=1, ad=1, ni=1)
    get_mxs = []

    for m in get_mesh:
        skin_nodes = pm.ls(pm.listHistory(m, type='skinCluster'))
        if skin_nodes:
            skin_node = skin_nodes[0]
            matrixs = pm.listAttr(skin_node + '.matrix', m=1)
            for mx in matrixs:
                get_mx = pm.listConnections(skin_node + '.' + mx, d=1)[0]
                if pm.nodeType(get_mx) == 'multMatrix':
                    get_j = pm.listConnections(get_mx + '.matrixIn[0]', d=1, p=1)[0]
                    pm.connectAttr(get_j, skin_node + '.' + mx, f=1)
                    get_mxs.append(get_mx)

    if get_mxs:
        pm.delete(get_mxs)

def delete_bs_node(Geo_grp="Geo_grp"):
    import pymel.core as pm
    if Geo_grp:
        objs = []
        if pm.listRelatives(Geo_grp, ad=1, type='mesh'):
            objs.extend([pm.listRelatives(x, p=1)[0] for x in pm.listRelatives(Geo_grp, ad=1, type='mesh')])
        objs = list(set(objs))

    if not objs:
        return
    for i in objs:
        bsNode = i.history(type='blendShape')
        if bsNode:
            pm.delete(bsNode)

        pm.displayInfo(u"delete {}".format(bsNode))

def export_fbx_with_objects(main_window, fbx_path):
    """根据配置的对象名称导出FBX"""
    if not IN_MAYA:
        return False

    geo_group = main_window.fbx_config[0]
    root_joint = main_window.fbx_config[1]
    export_objects = []

    # 查找几何体组
    if cmds.objExists(geo_group):
        export_objects.append(geo_group)
    else:
        all_transforms = cmds.ls(type='transform')
        for obj in all_transforms:
            if geo_group.lower() in obj.lower():
                export_objects.append(obj)
                break

    if cmds.objExists(root_joint):
        export_objects.append(root_joint)
    else:
        all_joints = cmds.ls(type='joint')
        for obj in all_joints:
            if root_joint.lower() in obj.lower():
                export_objects.append(obj)
                break

    if not export_objects:
        QtWidgets.QMessageBox.warning(main_window, '错误',
                                      u'未找到要导出的对象:\n几何体组: {}\n根关节: {}'.format(geo_group, root_joint))
        return False

    try:
        delete_Matrix(geo_group)  # 去除蒙皮逆矩阵
    except:
        pass
    delete_bs_node(geo_group)

    try:
        print(u"导出的对象: {}".format(fbx_path))
        if not cmds.pluginInfo('fbxmaya', q=True, l=True):
            cmds.loadPlugin('fbxmaya')

        cmds.select(export_objects, replace=True)
        mel.eval('file -force -options "v=0;" -typ "FBX export" -pr -es "{}";'.format(fbx_path))
        return os.path.exists(fbx_path)

    except Exception as e:
        print(u"导出FBX时发生错误: ", e)
        return False