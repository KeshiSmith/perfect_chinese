import bpy

from os.path import dirname, realpath

class PC_Info():
  # 全局参数
  addon_name = __package__[:-8]
  addon_name_cn = "完美中文"
  
  # 全局路径
  root_path = dirname(dirname(realpath(__file__)))
  datafiles_path = root_path + "/datafiles"
  locale_path = datafiles_path + "/locale"
  config_path = root_path + "/config"
  settings_path = config_path + "/setttings"

  # 获取偏好设置
  @staticmethod
  def get_preferences():
    return bpy.context.preferences.addons[PC_Info.addon_name].preferences