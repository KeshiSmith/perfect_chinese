from .modules.props import PC_ModuleInfo
from .modules.preferences import PC_Preferences
from .modules.operators.modules import PC_ModuleEnable, PC_ModuleDisable
from .modules.operators.translation import PC_Translation
from .modules.ui.tab_panel import PC_TabPanel
from .modules.ui.translation_button import PC_TranslationButton
from .modules.localization import PC_LocalizationManager

ordered_classes = [
    # 自定义属性
    PC_ModuleInfo,
    # 操作
    PC_ModuleEnable,
    PC_Translation,
    PC_ModuleDisable,
    # 偏好设置
    PC_Preferences,
    # UI 界面
    # TODO: 侧边栏面板
    # PC_TabPanel,
    PC_TranslationButton,
    # 翻译管理器
    PC_LocalizationManager
]

from bpy.utils import register_class, unregister_class

def register():
    # register classes
    for cls in ordered_classes:
        cls.pc_register()

def unregister():
    # unregister classes
    for cls in ordered_classes[::-1]:
        cls.pc_unregister()
