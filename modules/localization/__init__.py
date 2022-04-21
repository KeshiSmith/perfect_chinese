import bpy
from os import listdir

from .localization import load_l10n_dict
from ..types import PC_Registerable
from ..utils import PC_Info

class PC_LocalizationManager(PC_Registerable):

  preferences = None
  module_infos = None
  enabled_modules = None
  missing_modules = None

  @classmethod
  def pc_register(cls):
    # 获取偏好设置
    cls.preferences = PC_Info.get_preferences()
    cls.module_infos = cls.preferences.module_infos
    cls.enabled_modules = cls.preferences.enabled_modules
    cls.missing_modules = cls.preferences.missing_modules
    # 更新本地模块列表
    cls.moudle_refresh()
    # 更新全局翻译
    cls.update_global_module()

  @classmethod
  def pc_unregister(cls):
    # 注销模块翻译
    for module_name in cls.enabled_modules.copy():
      if module_name not in cls.missing_modules:
        cls.unregister_module(module_name)
    # 注销全局翻译
    if cls.preferences.global_translation_toggle:
      cls.unregister_global_module()

  @classmethod
  def moudle_refresh(cls):
    # 刷新本地模块列表
    cls.module_infos.clear()
    # 获取模组列表
    for file in listdir(PC_Info.locale_path):
      if file.endswith(".po"):
        catagory, name, name_cn, author = file[:-3].split("#")
        module_info = cls.module_infos.add(name)
        module_info.catagory = catagory
        module_info.name_cn = name_cn
        module_info.author = author
    # 计算缺失模组
    cls.missing_modules.clear()
    for module_name in cls.enabled_modules:
      if module_name not in cls.module_infos.names():
        cls.missing_modules.add(module_name)
    # 计算过滤模组和过滤缺失模组
    cls.preferences.update_filtered_modules()

  @classmethod
  def register_global_module(cls):
    module_popath = "%s/blender.po" % (PC_Info.datafiles_path)
    l10n_dict = load_l10n_dict(module_popath)
    bpy.app.translations.register("blender", l10n_dict)

  @classmethod
  def unregister_global_module(cls):
    bpy.app.translations.unregister("blender")

  @classmethod
  def update_global_module_only(cls):
    cls.unregister_global_module()
    if cls.preferences.global_translation_toggle:
      cls.register_global_module()

  @classmethod
  def update_global_module(cls):
    # 普通模式更新所有模块的翻译
    cls.unregister_all_modules()
    if cls.preferences.addon_mode == 'NORMAL':
      if cls.preferences.global_translation_toggle:
        cls.register_all_modules()
    # 高级模式注册已启用模块的翻译
    elif cls.preferences.addon_mode == 'ADVANCE':
      if cls.preferences.global_translation_toggle:
        cls.register_enabled_modules()
    # 更新全局翻译模块
    cls.update_global_module_only()

  @classmethod
  def register_module(cls, module):
    # 注册模块翻译
    module_info = cls.module_infos[module]
    module_file_name = "#".join([
        module_info.catagory, module_info.name, module_info.name_cn,
        module_info.author
    ])
    module_popath = "%s/%s.po" % (PC_Info.locale_path, module_file_name)
    l10n_dict = load_l10n_dict(module_popath)
    bpy.app.translations.register(module, l10n_dict)

  @classmethod
  def register_module_and_add_to_list(cls, module):
    # 添加至启用模块列表
    cls.enabled_modules.add(module)
    # 注册模块翻译
    cls.register_module(module)

  @classmethod
  def unregister_module(cls, module):
    # 注销模块翻译
    if module in cls.missing_modules.copy():
      cls.missing_modules.remove(module)
    bpy.app.translations.unregister(module)

  @classmethod
  def unregister_module_and_remove_from_list(cls, module):
    # 注销模块翻译
    cls.unregister_module(module)
    # 从启用模块列表移除
    cls.enabled_modules.remove(module)

  @classmethod
  def register_enabled_modules(cls):
    # 注册已启用模块的翻译
    for module_name in cls.enabled_modules:
      if module_name not in cls.missing_modules:
        cls.register_module(module_name)

  @classmethod
  def unregister_enabled_modules(cls):
    # 注销已启用模块翻译
    for module_name in cls.enabled_modules:
      if module_name not in cls.missing_modules:
        cls.unregister_module(module_name)

  @classmethod
  def register_all_modules(cls):
    # 注册所有模块的翻译
    for module_name in cls.module_infos.names():
      if module_name not in cls.missing_modules:
        cls.register_module(module_name)

  @classmethod
  def unregister_all_modules(cls):
    # 注销所有模块的翻译
    for module_name in cls.module_infos.names():
      if module_name not in cls.missing_modules:
        cls.unregister_module(module_name)
