from bpy.props import StringProperty
from bpy.types import Operator

from ..localization import PC_LocalizationManager
from ..types import PC_Registerable
from ..utils import PC_Info
from ..config import PC_Config


class PC_ModuleEnable(Operator, PC_Registerable):
  bl_idname = "perfect_chinese.module_enable"
  bl_label = "注册模组翻译"
  bl_options = {'INTERNAL'}

  module: StringProperty(name="模组", description="注册翻译的模组名字")

  def execute(self, context):
    PC_LocalizationManager.register_module_and_add_to_list(self.module)
    PC_LocalizationManager.update_global_module_only()
    PC_Config.update_config()
    return {"FINISHED"}


class PC_ModuleDisable(Operator, PC_Registerable):
  bl_idname = "perfect_chinese.module_disable"
  bl_label = "注销模组翻译"
  bl_options = {'INTERNAL'}

  module: StringProperty(name="模组", description="注销翻译模组的名字")

  def execute(self, context):
    PC_LocalizationManager.unregister_module_and_remove_from_list(self.module)
    PC_Config.update_config()
    return {"FINISHED"}


class PC_ModuleRefresh(Operator, PC_Registerable):
  bl_idname = "perfect_chinese.module_refresh"
  bl_label = "刷新"
  bl_description = "刷新本地模块列表"
  bl_options = {'INTERNAL'}

  def execute(self, context):
    PC_LocalizationManager.moudle_refresh()
    return {'FINISHED'}


class PC_UpdateGlobalModule(Operator, PC_Registerable):
  bl_idname = "perfect_chinese.update_global_module"
  bl_label = "更新全局翻译"
  bl_options = {'INTERNAL'}

  def execute(self, context):
    PC_LocalizationManager.update_global_module()
    return {"FINISHED"}
