# -*- coding: utf-8 -*-

import unreal
import json
import os
import time

LOG_PREFIX = "[UEAssetUtils]"

SUBS = ["Materials", "Meshes", "Textures"]

# 先匹配具体的类型
TYPE_RULES = [
    ("MaterialInstance", "Materials"),
    ("MaterialFunction", "Materials"),
    ("MaterialParameterCollection", "Materials"),
    ("Material", "Materials"),
    ("Texture", "Textures"),
]

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.expanduser("~"),
    "Documents",
    "Unreal Projects",
    "ue_import.json",
)

REQUIRED_KEYS = ("fbx", "base_path", "name")


def load_config(path=None):
    path = path or DEFAULT_CONFIG_PATH
    if not os.path.isfile(path):
        raise RuntimeError("Config not found: {}".format(path))

    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)

    missing = [k for k in REQUIRED_KEYS if not cfg.get(k)]
    if missing:
        raise RuntimeError("Config missing keys: {}".format(", ".join(missing)))
    return cfg


def get_root_path(cfg):
    return "{}/{}".format(cfg["base_path"], cfg["name"])


def ensure_sub_folders(root_path):
    if not unreal.EditorAssetLibrary.does_directory_exist(root_path):
        unreal.EditorAssetLibrary.make_directory(root_path)

    for sub in SUBS:
        path = "{}/{}".format(root_path, sub)
        if not unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.make_directory(path)

    return root_path


def create_object_folder_structure(base_path, root_name):
    return ensure_sub_folders("{}/{}".format(base_path, root_name))


def classify(class_name):
    for key, folder in TYPE_RULES:
        if key in class_name:
            return folder
    return None


def move_asset(asset_path, asset, target_folder, asset_name,
               dry_run=False, log_prefix=LOG_PREFIX):
    new_path = "{}/{}".format(target_folder, asset_name)

    if asset_path == new_path:
        return "skip_same"

    if unreal.EditorAssetLibrary.does_asset_exist(new_path):
        unreal.log_warning(
            "{} [Skip] Target exists: {} -> {}".format(log_prefix, asset_path, new_path)
        )
        return "skip_exists"

    unreal.log("{} Move: {} -> {}".format(log_prefix, asset_path, new_path))
    if dry_run:
        return "planned"

    try:
        if unreal.EditorAssetLibrary.rename_asset(asset_path, new_path):
            return "moved"
    except Exception as e:
        unreal.log_warning(
            "{} rename_asset failed ({}), fallback to AssetTools".format(log_prefix, e)
        )

    try:
        rename_data = [unreal.AssetRenameData(asset, target_folder, asset_name)]
        unreal.AssetToolsHelpers.get_asset_tools().rename_assets(rename_data)
        return "moved"
    except Exception as e:
        unreal.log_error(
            "{} Move failed: {} -> {} | {}".format(log_prefix, asset_path, new_path, e)
        )
        return "failed"


def organize_assets(root_folder, dry_run=False, log_prefix=LOG_PREFIX):
    """递归扫描 root_folder，把材质类移到 Materials、贴图类移到 Textures。"""
    ensure_sub_folders(root_folder)

    assets_list = unreal.EditorAssetLibrary.list_assets(root_folder, recursive=True)
    stats = {"moved": 0, "skip_same": 0, "skip_exists": 0, "planned": 0, "failed": 0}

    for asset_path in assets_list:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if not asset:
            continue

        folder = classify(asset.get_class().get_name())
        if not folder:
            continue

        asset_name = asset_path.rsplit("/", 1)[-1]
        target_folder = "{}/{}".format(root_folder, folder)

        result = move_asset(
            asset_path, asset, target_folder, asset_name,
            dry_run=dry_run, log_prefix=log_prefix,
        )
        stats[result] = stats.get(result, 0) + 1

    unreal.log(
        "{} Organize: moved={moved}, skip_same={skip_same}, skip_exists={skip_exists}, "
        "planned={planned}, failed={failed}".format(log_prefix, **stats)
    )
    return stats


def wait_for_registry(path, timeout=30.0, log_prefix=LOG_PREFIX):
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        registry.scan_paths_synchronous([path], True, True)
    except Exception as e:
        unreal.log_warning("{} scan_paths_synchronous failed: {}".format(log_prefix, e))

    deadline = time.time() + timeout
    while time.time() < deadline:
        if unreal.EditorAssetLibrary.list_assets(path):
            return
        time.sleep(0.5)

    unreal.log_warning(
        "{} Registry wait timeout after {}s: {}".format(log_prefix, timeout, path)
    )