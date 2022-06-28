from bpy.app import translations
from bpy.types import Operator

from ..types import PC_Registrable
from ..utils import PC_Info


class PC_Translation(Operator, PC_Registrable):
  bl_idname = "perfect_chinese.translation"
  bl_label = "切换中英文"
  bl_description = "一键切换中英文"

  def execute(self, context):
    view = context.preferences.view
    if translations.locale != 'zh_CN':
      view.language = 'zh_CN'
      view.use_translate_tooltips = False
      view.use_translate_interface = False
      view.use_translate_new_dataname = False
    preferences = PC_Info.get_preferences()
    if preferences.tooltips_included:
      view.use_translate_tooltips = not view.use_translate_interface
    if preferences.new_dataname_included:
      view.use_translate_new_dataname = not view.use_translate_interface
    view.use_translate_interface = not view.use_translate_interface
    return {"FINISHED"}
