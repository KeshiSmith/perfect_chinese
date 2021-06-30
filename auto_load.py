from .modules.preferences import PC_Preferences
from .modules.operators.module import (
    PC_ModuleEnable, 
    PC_ModuleDisable, 
    PC_ModuleRefresh,
    PC_UpdateGlobalModule
)
from .modules.operators.translation import PC_Translation
from .modules.ui.panel import PC_TabPanel
from .modules.ui.header import PC_Header
from .modules.config import PC_Config
from .modules.localization import PC_LocalizationManager

ordered_classes = [
    # 操作
    PC_ModuleEnable,
    PC_ModuleDisable,
    PC_ModuleRefresh,
    PC_UpdateGlobalModule,
    PC_Translation,
    # 偏好设置
    PC_Preferences,
    # UI 界面
    # TODO: 侧边栏面板
    # PC_TabPanel,
    PC_Header,
    # 插件配置
    PC_Config,
    # 翻译管理器
    PC_LocalizationManager
]

def register():
    # 注册相关类
    for cls in ordered_classes:
        cls.pc_register()

def unregister():
    # 注销相关类
    for cls in ordered_classes[::-1]:
        cls.pc_unregister()
