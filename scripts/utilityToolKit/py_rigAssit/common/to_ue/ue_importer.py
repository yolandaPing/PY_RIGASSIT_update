# -*- coding: utf-8 -*-

# .FileName: ue_importer.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/6/19 18:05
# .Finish time:
#
# 导入 FBX 后按 Materials / Meshes / Textures 归类资产。

import unreal
import os
import sys

try:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _THIS_DIR = os.path.join(unreal.Paths.project_content_dir(), "Python")
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import ue_asset_utils as utils

LOG_PREFIX = "[UEImporter]"

# 材质/贴图已在 UE 里时可关掉，只导网格
IMPORT_MATERIALS = True
IMPORT_TEXTURES = True

# 等待sleep
REGISTRY_TIMEOUT = 30.0


def import_fbx(fbx_path, dest_path):
    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = dest_path
    task.automated = True
    task.save = True
    task.replace_existing = True

    options = unreal.FbxImportUI()
    options.import_as_skeletal = True
    options.import_mesh = True
    options.import_animations = False
    options.import_materials = IMPORT_MATERIALS
    options.import_textures = IMPORT_TEXTURES

    task.options = options

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    imported = list(getattr(task, "imported_object_paths", []) or [])
    if not imported:
        unreal.log_warning(
            "{} No asset reported by import task: {}".format(LOG_PREFIX, fbx_path)
        )
    for p in imported:
        unreal.log("{} Imported: {}".format(LOG_PREFIX, p))


def main():
    try:
        cfg = utils.load_config()
        fbx_path = cfg["fbx"]
        base_path = cfg["base_path"]
        name = cfg["name"]

        if not os.path.isfile(fbx_path):
            unreal.log_error("{} FBX not found: {}".format(LOG_PREFIX, fbx_path))
            return

        root_path = utils.create_object_folder_structure(base_path, name)
        dest_path = root_path + "/Meshes"

        existing = unreal.EditorAssetLibrary.list_assets(dest_path)
        unreal.log(
            "{} {} import: {}".format(
                LOG_PREFIX, "Overwrite" if existing else "New", fbx_path
            )
        )

        import_fbx(fbx_path, dest_path)
        utils.wait_for_registry(dest_path, timeout=REGISTRY_TIMEOUT, log_prefix=LOG_PREFIX)
        stats = utils.organize_assets(root_path, log_prefix=LOG_PREFIX)

        unreal.EditorAssetLibrary.save_directory(root_path)
        unreal.log("{} Import Finished. stats={}".format(LOG_PREFIX, stats))

    except Exception as e:
        unreal.log_error("{} Import failed: {}".format(LOG_PREFIX, e))


main()