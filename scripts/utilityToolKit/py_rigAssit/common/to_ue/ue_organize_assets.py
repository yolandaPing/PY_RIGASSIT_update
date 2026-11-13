# -*- coding: utf-8 -*-
"""
organize_assets.py
只归类，不导入 FBX。把已存在于 UE 里的材质/贴图移动到对应子文件夹。
"""

import unreal
import os
import sys

# 保证 ue_asset_utils 可被导入
try:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _THIS_DIR = os.path.join(unreal.Paths.project_content_dir(), "Python")
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import ue_asset_utils as utils

LOG_PREFIX = "[OrganizeAssets]"

# True: 只打印计划不移动；确认后再改 False
DRY_RUN = False


def main():
    try:
        cfg = utils.load_config()
        root = utils.get_root_path(cfg)

        if not unreal.EditorAssetLibrary.does_directory_exist(root):
            unreal.log_error("{} Root not found: {}".format(LOG_PREFIX, root))
            return

        stats = utils.organize_assets(root, dry_run=DRY_RUN, log_prefix=LOG_PREFIX)

        if not DRY_RUN:
            unreal.EditorAssetLibrary.save_directory(root)

        unreal.log("{} Done. stats={}".format(LOG_PREFIX, stats))

    except Exception as e:
        unreal.log_error("{} Failed: {}".format(LOG_PREFIX, e))


main()