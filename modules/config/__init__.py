from os import mkdir
from os.path import isdir, isfile

from ..types import PC_Registerable
from ..utils import PC_Info


class PC_Config(PC_Registerable):
  @classmethod
  def pc_register(cls):
    # 加载配置文件
    PC_Config.load_config()

  @classmethod
  def pc_unregister(cls):
    pass

  @staticmethod
  def load_config():
    # 获取偏好设置
    enabled_modules = PC_Info.get_preferences().enabled_modules
    enabled_modules.clear()
    # 加载配置文件
    if not isdir(PC_Info.config_path):
      mkdir(PC_Info.config_path)
    elif isfile(PC_Info.settings_path):
      with open(PC_Info.settings_path, "r", encoding="utf-8") as settings:
        for line in settings:
          module_name = line[:-1]
          enabled_modules.add(module_name)

  @staticmethod
  def update_config():
    # 获取偏好设置
    enabled_modules = PC_Info.get_preferences().enabled_modules
    # 写入配置文件
    with open(PC_Info.settings_path, "w", encoding="utf-8") as config:
      for module_name in enabled_modules:
        config.write("%s\n" % module_name)
