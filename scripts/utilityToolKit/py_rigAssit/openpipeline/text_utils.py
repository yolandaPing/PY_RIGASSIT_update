# -*- coding: utf-8 -*-
"""OpenPipeline 公共文本工具。

集中原先散落在 pyopenpipeline / ui_openpipeline / version_context /
fbx_service 四份完全一致的 ``_u()``，避免实现漂移。

本模块不依赖 Qt / Maya / Pipeline，可在任意环境安全导入。
"""


def _u(value):
    """Py2/Py3 安全转 unicode。"""
    if value is None:
        return u''
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except Exception:
            try:
                return value.decode('gbk')
            except Exception:
                return value.decode('utf-8', 'replace')
    if isinstance(value, str):
        return value
    try:
        return unicode(value)  # noqa: F821
    except Exception:
        return u'{}'.format(value)
