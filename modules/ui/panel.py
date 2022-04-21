from bpy.types import Panel
from bpy.utils import register_class, unregister_class

from ..types import PC_Registerable
from ..utils import PC_Info


class PC_TabPanel(Panel, PC_Registerable):
  """ The addon panel in the sidebar """
  bl_idname = "CHINESE_PT_VIEW3D_PC_TabPanel"
  bl_space_type = 'VIEW_3D'
  bl_region_type = 'UI'
  bl_category = PC_Info.addon_name_cn
  bl_label = PC_Info.addon_name_cn

  @classmethod
  def pc_register(cls):
    if PC_Info.get_preferences().sidebar_toggle:
      cls.bl_category = PC_Info.get_preferences().tab_category
      register_class(cls)

  @classmethod
  def pc_unregister(cls):
    if PC_Info.get_preferences().sidebar_toggle:
      unregister_class(cls)

  @classmethod
  def update_sidebar_toggle(cls, toggle, tab_category):
    cls.bl_category = tab_category
    if toggle:
      register_class(cls)
    else:
      unregister_class(cls)

  @classmethod
  def update_tab_category(cls, tab_category):
    unregister_class(cls)
    cls.bl_category = tab_category
    register_class(cls)

  @classmethod
  def poll(cls, context):
    return context.mode == 'OBJECT'

  def draw(self, context):

    pass
