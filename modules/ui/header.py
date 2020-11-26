import bpy

from bpy.types import Header
from bpy.utils import register_class, unregister_class

from ..types import PC_Registerable
from ..operators.translation import PC_Translation
from ..utils import get_preferences

class PC_Header(Header, PC_Registerable):
    bl_idname = "CHINESE_HT_HEADER_PC_TranslationButton"
    bl_space_type = "TOPBAR"
    bl_label = "翻译按钮"

    @classmethod
    def pc_register(cls):
        bpy.types.TOPBAR_HT_upper_bar.append(cls.draw)

    @classmethod
    def pc_unregister(cls):
        bpy.types.TOPBAR_HT_upper_bar.remove(cls.draw)

    def draw(self, context):
        if get_preferences().button_toggle and context.region.alignment != 'RIGHT':
            view = context.preferences.view
            text = "中文模式" if view.use_translate_interface else "英文模式"
            self.layout.operator(PC_Translation.bl_idname, text=text)

