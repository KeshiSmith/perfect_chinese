import bpy

# 全局参数
addon_name = __package__[:-8]
addon_name_cn = "完美中文"

# 全局函数
def get_preferences():
    return bpy.context.preferences.addons[addon_name].preferences

# 全局路径
from os.path import dirname, realpath
root_path = dirname(dirname(realpath(__file__)))
