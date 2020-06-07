from bpy.types import Operator
from os import listdir

from ..types import PC_Registerable
from ..utils import modules_refresh

class PC_Refresh(Operator, PC_Registerable):
    bl_idname = "perfect_chinese.refresh"
    bl_label = "刷新"
    bl_description = "刷新本地模块列表"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        modules_refresh()
        return {'FINISHED'}