import bpy
from os import mkdir
from os.path import isdir, isfile

from .localization import load_l10n_dict
from ..types import PC_Registerable
from ..utils import (
    datafiles_path,
    locale_path,
    config_path,
    settings_path,
    get_preferences, 
    modules_refresh,
    load_config,
    update_config
)

class PC_LocalizationManager(PC_Registerable):

    @classmethod
    def pc_register(cls):
        # 加载配置文件
        load_config()
        # 刷新本地模块列表
        modules_refresh()
        # 获取偏好设置
        preferences = get_preferences()
        enabled_modules = preferences.enabled_modules
        missing_modules = preferences.missing_modules
        # 注册已启用的翻译
        for module_name in enabled_modules:
            if module_name not in missing_modules:
                cls.register_module(module_name)
        # 注册全局翻译
        if get_preferences().global_translation_toggle:
            cls.register_global_module()
    

    @classmethod
    def pc_unregister(cls):
        # 获取偏好设置
        preferences = get_preferences()
        enabled_modules = preferences.enabled_modules
        missing_modules = preferences.missing_modules
        # 注销模块翻译
        for module_name in enabled_modules:
            if module_name not in missing_modules:
                cls.unregister_module(module_name)
        # 注销全局翻译
        if get_preferences().global_translation_toggle:
            cls.unregister_global_module()

    @classmethod
    def register_global_module(cls):
        module_popath = "%s\\blender.po"%(datafiles_path)
        l10n_dict = load_l10n_dict(module_popath)
        bpy.app.translations.register("blender", l10n_dict)
    
    @classmethod
    def unregister_global_module(cls):
        cls.unregister_module("blender")

    @classmethod
    def update_global_module(cls):
        cls.unregister_global_module()
        preferences = get_preferences()
        if get_preferences().global_translation_toggle:
            cls.register_global_module()

    @classmethod
    def register_module(cls, module):
        preferences = get_preferences()
        module_info = preferences.module_infos[module]
        module_file_name = "#".join([
            module_info.catagory,
            module_info.name,
            module_info.name_cn,
            module_info.author
        ])
        module_popath = "%s\\%s.po"%(locale_path, module_file_name)
        l10n_dict = load_l10n_dict(module_popath)
        bpy.app.translations.register(module, l10n_dict)

    @classmethod
    def unregister_module(cls, module):
        bpy.app.translations.unregister(module)

