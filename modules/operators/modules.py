from bpy.props import StringProperty
from bpy.types import Operator

from ..localization import PC_LocalizationManager
from ..types import PC_Registerable
from ..utils import get_preferences

class PC_ModuleEnable(Operator, PC_Registerable):
    bl_idname = "perfect_chinese.module_enable"
    bl_label = "注册模组翻译"
    bl_options = {'INTERNAL'}

    module: StringProperty(
        name="模组",
        description="注册翻译的模组名字",
    ) 

    def execute(self, context):
        preferences = get_preferences()
        preferences.module_infos[self.module].enabled = True
        PC_LocalizationManager.register_module(self.module)
        PC_LocalizationManager.update_global_module()
        PC_LocalizationManager.update_config()
        return {"FINISHED"}
    

class PC_ModuleDisable(Operator, PC_Registerable):
    bl_idname = "perfect_chinese.module_disable"
    bl_label = "注销模组翻译"
    bl_options = {'INTERNAL'}

    module: StringProperty(
        name="模组",
        description="注销翻译模组的名字",
    ) 

    def execute(self, context):
        preferences = get_preferences()
        preferences.module_infos[self.module].enabled = False
        PC_LocalizationManager.unregister_module(self.module)
        PC_LocalizationManager.update_config()
        return {"FINISHED"}
    
