# -*- coding: utf-8 -*-

# .FileName:fbx_to_unreal.py
# .@Author : Yolanda Ping (You P)
# .@Email : yolandaping1224@gmail.com
# .Date....: 2026/6/19 17:36
# .Finish time:
import tempfile
import os
import subprocess
import json
import inspect

def get_current_dir():
    return os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )


def run_unreal(project_path, script_path):
    ue_exe = r"C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"

    cmd = [
        ue_exe,
        project_path,
        "-run=pythonscript",
        "-script=" + script_path
    ]

    subprocess.call(cmd)

# UE_EXE = r"C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
# UE_IMPORTER = r"D:\pipeline\ue_importer.py"

def save_json(fbx_path, ue_base_path, name):
    config = {
        "fbx": fbx_path,
        "base_path": ue_base_path,
        "name": name
    }

    CONFIG_PATH = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "Unreal Projects",
        "ue_import.json"
    )

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f)


def export_to_unreal(fbx_path, UE_EXE, ue_project, ue_base_path, name):

    if not os.path.exists(fbx_path):
        raise RuntimeError("FBX not found: {}".format(fbx_path))

    if not os.path.exists(ue_project):
        raise RuntimeError("UE project not found: {}".format(ue_project))

    if not os.path.exists(UE_EXE):
        raise RuntimeError("UE exe not found")

    save_json(fbx_path, ue_base_path, name)

    base_dir = get_current_dir()
    UE_IMPORTER = os.path.join(base_dir, "ue_importer.py")

    cmd = [
        UE_EXE,
        ue_project,
        "-run=pythonscript",
        "-script=" + UE_IMPORTER,
        "--fbx", fbx_path,
        "--dest", ue_base_path
    ]

    print("=" * 60)
    print("Launching Unreal import...")
    print(cmd)

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    stdout, stderr = p.communicate()

    print(stdout)
    print(stderr)

    if p.returncode != 0:
        raise RuntimeError("Error: Unreal import failed")

    print("=" * 60)