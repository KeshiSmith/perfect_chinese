bl_info = {
    "name": "Prefect Chinese | 完美中文",
    "description": "一键切换中英文 + 快速汉化 Blender 插件.",
    "author": "可是·喵",
    "version": (0, 1, 0),
    "blender": (2, 83, 0),
    "location": "偏好设置",
	"wiki_url":    "https://github.com/KeshiSmith/prefect_chinese",
	"tracker_url": "https://github.com/KeshiSmith/prefect_chinese/issues",
    "category": "中文版",
}

from . import addon_updater_ops
from . import auto_load

def register():
    addon_updater_ops.register(bl_info)
    auto_load.register()

def unregister():
    addon_updater_ops.unregister(bl_info)
    auto_load.unregister()
