# 全局参数
addon_name = __package__[:-8]
addon_name_cn = "完美中文"

# 全局路径
from os.path import dirname, realpath
root_path = dirname(dirname(realpath(__file__)))
datafiles_path = root_path + "/datafiles"
locale_path = datafiles_path + "/locale"
config_path = root_path + "/config"
settings_path = config_path + "/setttings"

# 获取偏好设置
import bpy
def get_preferences():
    return bpy.context.preferences.addons[addon_name].preferences

from os import mkdir
from os.path import isdir, isfile
# 加载配置文件
def load_config():
    # 获取偏好设置
    enabled_modules = get_preferences().enabled_modules
    enabled_modules.clear()
    # 加载配置文件
    if not isdir(config_path):
        mkdir(config_path)
    elif isfile(settings_path):
        with open(settings_path, "r", encoding="utf-8") as settings:
            for line in settings:
                module_name = line[:-1]
                enabled_modules.add(module_name)

# 更新配置文件
def update_config():
    # 获取偏好设置
    enabled_modules = get_preferences().enabled_modules
    # 写入配置文件
    with open(settings_path, "w", encoding="utf-8") as config:
        for module_name in enabled_modules:
            config.write("%s\n"%module_name)
