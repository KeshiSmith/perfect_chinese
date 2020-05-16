import bpy
from  bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    StringProperty
)
from bpy.types import AddonPreferences

from .utils import (
    addon_name,
    addon_name_cn
)
from .props import PC_ModuleInfo
from .types import PC_Registerable
from .ui.tab_panel import PC_TabPanel
from .ui.translation_button import PC_TranslationButton
from .localization import PC_LocalizationManager

class PC_Preferences(AddonPreferences, PC_Registerable):
    bl_idname = addon_name

    @classmethod
    def pc_register(cls):
        cls.module_infos = CollectionProperty(type=PC_ModuleInfo)
        super().pc_register()

    tabs : EnumProperty(
        name="选项卡",
        items=[
            ("CHINESE", "汉化", "汉化插件"),
            ("OPTIONS", "选项", "插件选项"),
            ("UPDATE", "更新", "插件更新")
        ]
    )

    def __update_global_translation_toggle(self, context):
        PC_LocalizationManager.update_global_module()

    global_translation_toggle : BoolProperty(
        name="全局翻译",
        description=
            "启用/禁用全局翻译.\n"
            "PS: 包括插件界面翻译以及部分官方未完成的翻译",
        default=True,
        update=__update_global_translation_toggle
    )

    def __update_button_toggle(self, context):
        PC_TranslationButton.update_button_toggle(self.button_toggle)

    button_toggle : BoolProperty(
        name="一键翻译",
        description=
            "启动/禁用一键翻译按钮.\n"
            "PS: 翻译按钮显示在顶栏上",
        default=True,
        update=__update_button_toggle
    )

    def __update_sidebar_toggle(self, context):
        PC_TabPanel.update_sidebar_toggle(
            self.sidebar_toggle,
            self.tab_category
        )

    sidebar_toggle : BoolProperty(
        name="侧边栏",
        description="启用/禁用侧边栏",
        default=True,
        update=__update_sidebar_toggle
    )

    def __update_tab_category(self, context):
        PC_TabPanel.update_tab_category(self.tab_category)

    tab_category : StringProperty(
        name="选项卡名称",
        description="自定义插件面板的选项卡名称",
        default=addon_name_cn,
        update=__update_tab_category
    )

    def draw(self, context):
        layout=self.layout
        row = layout.row()
        row.prop(self, "tabs", expand=True)
        layout.separator()
        if self.tabs == "CHINESE":
            layout.prop(self, "global_translation_toggle")
            for module_info in self.module_infos:
                inner_box = layout.box()
                row = inner_box.row()
                is_enabled = module_info.enabled
                module_name = module_info.name
                row.operator(
                    "perfect_chinese.module_disable" if is_enabled else "perfect_chinese.module_enable",
                    icon='CHECKBOX_HLT' if is_enabled else 'CHECKBOX_DEHLT', text="",
                    emboss=False,
                ).module = module_name
                row.label(
                    text="%s: %s | %s | %s汉化" %(
                    module_info.catagory,
                    module_info.name,
                    module_info.name_cn,
                    module_info.author
                    )
                )
        elif self.tabs == "OPTIONS":
            row = layout.row()
            row.prop(self, "button_toggle")
            row = layout.row()
            # TODO 侧边栏面板
            # row.label(text="侧边栏")
            # row.prop(self, "sidebar_toggle", text="")
            # split = row.split()
            # split.enabled = self.sidebar_toggle
            # split.prop(self, "tab_category", text="")
        layout.separator()

