bl_info = {
    "name": "Prefect Chinese | 完美中文",
    "author": "可是·喵",
    "version": (0, 0, 1),
    "blender": (2, 83, 0),
    "location": "偏好设置",
    "description": "一键切换中英文 + 快速汉化 Blender 插件.",
    "category": "中文版",
}

from . import auto_load

def register():
    auto_load.register()

def unregister():
    auto_load.unregister()
