# -*- coding: utf-8 -*-
# .FileName:quick_ng_transfer
# .Date....:2026-10-24 : 16 :15
# .@Author:You P
# .
# .Finish time:
"""
ngSkinTools2 快速操作脚本

功能：
  1. 快速导出当前选择模型的 ngSkinTools 权重到 JSON
  2. 快速导入指定路径 JSON 文件中的 ngSkinTools 权重到当前选择模型
     - 若目标模型没有 skinCluster，会从 JSON 读取关节，自动创建 skinCluster 后再导入
  3. 清理场景中所有 ngSkinTools 自定义节点
"""

from __future__ import print_function, unicode_literals

import os
from maya import cmds

from ngSkinTools2.api import export_json, import_json, FileFormat, VertexTransferMode, InfluenceMappingConfig
from ngSkinTools2.api.plugin import load_plugin, is_plugin_loaded
from ngSkinTools2.api.target_info import get_related_skin_cluster
from py_rigAssit.dialogs import mayaPrint


def _log(message):
    try:
        mayaPrint.log(message)
        return
    except Exception:
        pass
    try:
        print(message)
    except UnicodeEncodeError:
        try:
            print(message.encode("utf-8") if hasattr(message, "encode") else message)
        except Exception:
            pass


def _ensure_plugin_loaded():
    load_plugin()
    if not is_plugin_loaded():
        raise RuntimeError("ngSkinTools2 插件未能加载，请检查插件安装或插件路径设置")


def _is_mesh_node(node):
    """判断节点本身或其 shape 是否是 mesh"""
    if cmds.nodeType(node) == "mesh":
        return True
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
    return any(cmds.nodeType(s) == "mesh" for s in shapes)


def _get_mesh_from_skin_cluster(skin_cluster):
    """通过 skinCluster 的 geometry 查询反查被绑定的 mesh shape"""
    geos = cmds.skinCluster(skin_cluster, q=True, geometry=True) or []
    return geos[0] if geos else None


def _resolve_selected_target():
    """
    从当前选择解析出 skinCluster。
    找不到则返回 None（不抛异常，交给 auto_bind 决策）。
    """
    selection = cmds.ls(sl=True, long=True) or []
    if not selection:
        raise RuntimeError("请先选择一个已蒙皮的模型，或一个 skinCluster 节点")

    for node in selection:
        if cmds.nodeType(node) == "skinCluster":
            return node
        sc = get_related_skin_cluster(node)
        if sc:
            return sc
    return None


def _resolve_selected_mesh():
    """
    从当前选择解析出可绑定的 mesh（优先返回 transform）。
    """
    selection = cmds.ls(sl=True, long=True) or []
    if not selection:
        raise RuntimeError("请先选择一个模型")

    for node in selection:
        # 选中的是 skinCluster → 反查 mesh
        if cmds.nodeType(node) == "skinCluster":
            geo = _get_mesh_from_skin_cluster(node)
            if geo:
                parents = cmds.listRelatives(geo, parent=True, fullPath=True) or []
                return parents[0] if parents else geo
            continue

        # 选中的是 transform → 检查 shape
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(s) == "mesh" for s in shapes):
            return node

        # 选中的是 shape
        if cmds.nodeType(node) == "mesh":
            parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
            return parents[0] if parents else node

    raise RuntimeError("当前选择中没有可绑定的 mesh")


def _resolve_joint_path(info):
    """
    从一个 InfluenceInfo 解析出场景中真实存在的 DAG 长路径。
    优先 path，退化到 name（短名）。
    """
    if info.path and cmds.objExists(info.path):
        return cmds.ls(info.path, long=True)[0]
    if info.name and cmds.objExists(info.name):
        return cmds.ls(info.name, long=True)[0]
    return None


def _read_influences_from_json(file_path, format=FileFormat.JSON):
    """
    从 JSON 文件读取 influence 列表，按 logicalIndex 升序返回（与 skinCluster influence 顺序对应）。
    """
    from ngSkinTools2.api.import_export import FileFormatWrapper
    from ngSkinTools2.api import plugin
    from ngSkinTools2.api.target_info import unserialize_influences_from_json_data

    with FileFormatWrapper(file_path, format=format, read_mode=True) as f:
        data = plugin.ngst2tools(tool="importJsonFile", file=f.plain_file)

    infos = unserialize_influences_from_json_data(data["influences"])
    # 必须按 logicalIndex 排序——cmds.skinCluster 按参数顺序建立 influence
    infos.sort(key=lambda i: i.logicalIndex)
    return infos


def _create_skin_cluster_for_mesh(mesh, influences):
    """
    依据 influences 列表（已按 logicalIndex 排序）给 mesh 创建 skinCluster。
    返回新建的 skinCluster 名称。
    """
    joint_paths = []
    missing = []

    for info in influences:
        path = _resolve_joint_path(info)
        if path is None:
            missing.append(info.path or info.name or "(unknown)")
        else:
            joint_paths.append(path)

    if missing:
        raise RuntimeError(
            "以下关节在场景中不存在，无法自动绑定：\n  " + "\n  ".join(missing)
            + "\n\n请确认模型绑定所用关节仍在场景中，或手动创建 skinCluster 后再导入。"
        )

    if not joint_paths:
        raise RuntimeError("JSON 中没有可用的关节信息，无法自动绑定")

    # 去重但保持顺序
    seen = set()
    unique_joints = []
    for p in joint_paths:
        if p not in seen:
            seen.add(p)
            unique_joints.append(p)

    max_influences = max(4, len(unique_joints))

    # *args 之后只能用 **kwargs 展开。
    skin_kwargs = {
        "toSelectedBones": False,
        "normalizeWeights": 1,
        "maximumInfluences": max_influences,
        "obeyMaxInfluences": False,
        "removeUnusedInfluence": False,
    }
    result = cmds.skinCluster(mesh, *unique_joints, **skin_kwargs)

    skin_cluster = result[0] if isinstance(result, (list, tuple)) else result
    _log("[ngSkinTools] 已自动创建 skinCluster: %s (influences=%d)" % (skin_cluster, len(unique_joints)))
    return skin_cluster


def _pick_save_path():
    result = cmds.fileDialog2(
        caption="导出 ngSkinTools 权重 (JSON)",
        fileMode=0,
        fileFilter="JSON 文件 (*.json)",
        dialogStyle=2,
        okCaption="导出",
    )
    return result[0] if result else None


def _pick_open_path():
    result = cmds.fileDialog2(
        caption="导入 ngSkinTools 权重 (JSON)",
        fileMode=1,
        fileFilter="JSON 文件 (*.json)",
        dialogStyle=2,
        okCaption="导入",
    )
    return result[0] if result else None


def export_selected(file_path=None, format=FileFormat.JSON):
    """
    把当前选择模型的 ngSkinTools 权重导出到文件。
    """
    _ensure_plugin_loaded()
    target = _resolve_selected_target()
    if target is None:
        raise RuntimeError("当前选择的模型没有 skinCluster，无法导出权重")

    if not file_path:
        file_path = _pick_save_path()
        if not file_path:
            _log("[ngSkinTools] 已取消导出")
            return None

    parent_dir = os.path.dirname(file_path)
    if parent_dir and not os.path.isdir(parent_dir):
        try:
            os.makedirs(parent_dir)
        except OSError:
            # 并发/权限等边缘情况，忽略已存在的目录
            if not os.path.isdir(parent_dir):
                raise

    export_json(target, file_path, format=format)
    _log("[ngSkinTools] 已导出: %s -> %s" % (target, file_path))
    return file_path


def import_selected(
        file_path=None,
        vertex_transfer_mode=VertexTransferMode.closestPoint,
        format=FileFormat.JSON,
        auto_bind=True,
):
    """
    把指定文件中的 ngSkinTools 权重导入到当前选择模型。

    :param file_path: 文件路径；None 时弹出打开对话框
    :param vertex_transfer_mode: 顶点匹配模式
    :param format: FileFormat.JSON / FileFormat.CompressedJSON
    :param auto_bind: 为 True 时，若目标模型没有 skinCluster，会用 JSON 中的关节自动创建 skinCluster
    """
    _ensure_plugin_loaded()

    if not file_path:
        file_path = _pick_open_path()
        if not file_path:
            _log("[ngSkinTools] 已取消导入")
            return False

    if not os.path.isfile(file_path):
        raise RuntimeError("文件不存在: %s" % file_path)

    target = _resolve_selected_target()

    if target is None:
        if not auto_bind:
            raise RuntimeError(
                "当前模型没有 skinCluster。请先手动绑定，或使用 auto_bind=True 让脚本从 JSON 自动创建绑定。"
            )

        mesh = _resolve_selected_mesh()
        _log("[ngSkinTools] 目标模型无 skinCluster，准备自动绑定: %s" % mesh)
        influences = _read_influences_from_json(file_path, format=format)
        target = _create_skin_cluster_for_mesh(mesh, influences)

    mapping_config = InfluenceMappingConfig.transfer_defaults()
    import_json(
        target,
        file_path,
        vertex_transfer_mode=vertex_transfer_mode,
        influences_mapping_config=mapping_config,
        format=format,
    )

    # 如果 UI 处于打开状态，刷新会话事件
    try:
        from ngSkinTools2.api.session import session
        if session.active():
            session.events.targetChanged.emitIfChanged()
    except Exception:
        pass

    _log("[ngSkinTools] 已导入: %s -> %s" % (file_path, target))
    return True


def cleanup_scene_ng():
    """
    清理场景中所有 ngSkinTools 自定义节点（蒙皮权重保留，图层数据丢失）。
    """
    _ensure_plugin_loaded()

    try:
        from ngSkinTools2.operations.removeLayerData import remove_custom_nodes
        remove_custom_nodes(interactive=False)
        _log("[ngSkinTools] 场景清理完成")
        return
    except Exception as err:
        _log("[ngSkinTools] 官方清理失败，回退到直接删除: %s" % err)

    node_types = ["ngst2MeshDisplay", "ngst2SkinLayerData"]
    nodes_to_delete = []
    for t in node_types:
        nodes_to_delete.extend(cmds.ls(type=t) or [])

    if not nodes_to_delete:
        _log("[ngSkinTools] 场景中没有 ngSkinTools 自定义节点")
        return

    cmds.delete(nodes_to_delete)
    _log("[ngSkinTools] 已删除 %d 个 ngSkinTools 节点" % len(nodes_to_delete))


def import_vertex_mode(mode=1):
    if mode == 1:
        return VertexTransferMode.closestPoint
    elif mode == 2:
        return VertexTransferMode.uvSpace
    else:
        return VertexTransferMode.vertexId


def export_to(file_path=None):
    return export_selected(file_path=file_path)


def import_from(file_path, mode=1, auto_bind=True):
    return import_selected(file_path=file_path, vertex_transfer_mode=import_vertex_mode(mode), auto_bind=auto_bind)


if __name__ == "__main__":
    export_selected()