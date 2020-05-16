import bpy
from os import mkdir, listdir
from os.path import isdir, isfile

from .localization import load_l10n_dict
from ..types import PC_Registerable
from ..utils import (
    get_preferences, 
    root_path,
)

datafiles_path = root_path + "\\datafiles"
locale_path = datafiles_path + "\\locale"
config_path = root_path + "\\config"
settings_path = config_path + "\\setttings"

class PC_LocalizationManager(PC_Registerable):

    @classmethod
    def pc_register(cls):
        # 获取偏好设置
        preferences = get_preferences()
        module_infos = preferences.module_infos
        module_infos.clear()
        # 读取文件
        for file in listdir(locale_path):
            if file.endswith(".po"):
                module_info = module_infos.add()
                catagory, name, name_cn, author = file[:-3].split("#")
                module_info.catagory = catagory
                module_info.name = name
                module_info.name_cn = name_cn
                module_info.author = author
        # 加载配置文件并注册翻译
        if not isdir(config_path):
            mkdir(config_path)
        if isfile(settings_path):
            with open(settings_path, "r", encoding="utf-8") as settings:
                for line in settings:
                    module_name = line[:-1]
                    if module_name in module_infos.keys():
                        module_infos[module_name].enabled = True
                        cls.register_module(module_name)
        # 注册全局翻译
        if get_preferences().global_translation_toggle:
            cls.register_global_module()
    

    @classmethod
    def pc_unregister(cls):
        # 获取偏好设置
        preferences = get_preferences()
        module_infos = preferences.module_infos
        # 注销模块翻译
        with open(settings_path, "r", encoding="utf-8") as settings:
            for line in settings:
                module_name = line[:-1]
                if module_name in module_infos.keys():
                    cls.unregister_module(module_name)
        # 注销全局翻译
        if get_preferences().global_translation_toggle:
            cls.unregister_global_module()

    @classmethod
    def update_config(cls):
        # 获取偏好设置
        preferences = get_preferences()
        module_infos = preferences.module_infos
        # 写入配置文件
        with open(settings_path, "w", encoding="utf-8") as config:
            for module_info in module_infos:
                if module_info.enabled:
                    config.write("%s\n"%module_info.name)


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

