from bpy.types import Operator

from ..types import PC_Registerable

class PC_Translation(Operator, PC_Registerable):
    bl_idname = "perfect_chinese.translation"
    bl_label = "切换中英文"
    bl_description = "一键切换中英文"

    def execute(self, context):
        view = context.preferences.view
        view.use_translate_interface = not view.use_translate_interface
        return {"FINISHED"}
    
