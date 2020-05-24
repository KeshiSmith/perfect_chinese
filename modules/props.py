from bpy.props import BoolProperty, StringProperty
from bpy.types import PropertyGroup

from .types import PC_Registerable

class PC_ModuleInfo(PropertyGroup, PC_Registerable):

    enabled : BoolProperty(
        name="启用",
        default=False
    )
    catagory : StringProperty(
        name = "类别",
        default = "未分类"
    )
    name : StringProperty(
        name="模块名",
        default="Unkown"
    )
    name_cn : StringProperty(
        name="汉化名",
        default="未知"
    )
    author : StringProperty(
        name="作者名",
        default="佚名"
    )

