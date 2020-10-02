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
    addon_name_cn,
    get_preferences,
    locale_path
)
from .props import PC_ModuleInfos
from .types import PC_Registerable
from .ui.panel import PC_TabPanel
from .localization import PC_LocalizationManager

from .. import addon_updater_ops

class PC_Preferences(AddonPreferences, PC_Registerable):
    bl_idname = addon_name

    module_infos = PC_ModuleInfos()
    enabled_modules = set()
    missing_modules = set()
    filtered_modules = []
    filtered_missing_modules = []

    @classmethod
    def pc_register(cls):
        # 准备并注册当前类
        addon_updater_ops.make_annotations(cls)
        super().pc_register()
        # 初始化数据
        preferences = get_preferences()
        preferences.module_search = ""

    tabs : EnumProperty(
        items=[
            ("CHINESE", "汉化", "汉化插件"),
            ("OPTIONS", "选项", "插件选项"),
            ("UPDATE", "更新", "插件更新")
        ],
        name="选项卡",
        description="设置选项卡"
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

    def __update_module_filter(self, context):
        self.update_filtered_modules()

    show_modules_enabled_only : BoolProperty(
        name="仅已启用模块",
        description="仅显示已启用模块, 取消勾选显示全部本地的模块",
        default=False,
        update=__update_module_filter
    )

    def module_filter_items(self, context):
        items=[
            ("ALL", "全部", "全部模块")
        ]
        items_unique = set()
        module_infos = self.module_infos
        for module_name in module_infos.names():
            module_info = module_infos[module_name]
            items_unique.add(module_info.catagory)
        items.extend([(cat, cat, "") for cat in sorted(items_unique)])
        return items

    module_filter : EnumProperty(
        items=module_filter_items,
        name="类别",
        description="过滤模块类别",
        update=__update_module_filter
    )

    def update_filtered_modules(self):
        """ 计算过滤模组和过滤缺失模组 """
        module_filter = self.module_filter
        module_search = self.module_search.lower()
        filtered_modules = self.filtered_modules
        filtered_modules.clear()
        # 计算过滤模组
        for module_name in self.module_infos.names():
            module_info = self.module_infos[module_name]
            is_enabled = module_name in self.enabled_modules
            # 过滤状态
            if self.show_modules_enabled_only \
                and module_name not in self.enabled_modules:
                continue
            # 过滤类别
            if module_filter != 'ALL' and module_filter != module_info.catagory:
                continue
            # 过滤关键词
            if module_search in module_name.lower() \
                or module_search in module_info.name_cn.lower() \
                or module_search in module_info.author.lower():
                filtered_modules.append(module_name)
        # 计算过滤缺失模组
        filtered_missing_modules = self.filtered_missing_modules
        filtered_missing_modules.clear()
        filtered_missing_modules += [
            module_name
            for module_name in self.missing_modules
            if module_search in module_name.lower()
        ]

    def __update_module_search(self, context):
        self.update_filtered_modules()

    module_search : StringProperty(
        name="查找",
        description="在过滤器中查找插件翻译模组",
        default="",
        options={'SKIP_SAVE', 'TEXTEDIT_UPDATE'},
        update=__update_module_search
    )

    button_toggle : BoolProperty(
        name="一键翻译",
        description=
            "启动/禁用一键翻译按钮.\n"
            "PS: 翻译按钮显示在顶栏上",
        default=True
    )

    tooltips_included : BoolProperty(
        name="工具提示",
        description=
            "使用一键翻译进行切换时将包含工具提示的切换.\n"
            "PS: 默认已包含界面的切换",
        default=True
    )

    new_dataname_included : BoolProperty(
        name="新建数据",
        description=
            "使用一键翻译进行切换时将包含新建数据的切换.\n"
            "PS: 默认已包含界面的切换",
        default=False
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

    auto_check_update = bpy.props.BoolProperty(
        name="自动检查更新",
        description="如果启用, 每间隔一段时间自动检查更新",
        default=False,
    )
    updater_intrval_months = bpy.props.IntProperty(
        name='月',
        description="检查更新间隔的月份",
        default=0,
        min=0
    )
    updater_intrval_days = bpy.props.IntProperty(
        name='日',
        description="检查更新间隔的天数",
        default=7,
        min=0,
        max=31
    )
    updater_intrval_hours = bpy.props.IntProperty(
        name='时',
        description="检查更新间隔的小时数",
        default=0,
        min=0,
        max=23
    )
    updater_intrval_minutes = bpy.props.IntProperty(
        name='分',
        description="检查更新间隔的分钟数",
        default=0,
        min=0,
        max=59
    )

    def draw_chinese(self, context):
        layout = self.layout

        sub = layout.split(factor=0.66)
        sub.prop(self, "global_translation_toggle")
        sub = sub.split(align=True)
        sub.operator("wm.path_open", text="源文件夹", icon='FILEBROWSER'
            ).filepath = locale_path
        sub.operator("perfect_chinese.module_refresh", icon='FILE_REFRESH')

        sub = layout.split()
        sub.prop(self, "show_modules_enabled_only")
        sub.prop(self, "module_filter", text="")
        sub.prop(self, "module_search", text="", icon='VIEWZOOM')

        # 显示模组列表
        layout = layout.column()
        for module_name in self.filtered_modules:
            module_info = self.module_infos[module_name]
            is_enabled = module_name in self.enabled_modules
            inner_box = layout.box()
            row = inner_box.row()
            row.operator(
                "perfect_chinese.module_disable"
                    if is_enabled
                    else "perfect_chinese.module_enable",
                icon='CHECKBOX_HLT'
                    if is_enabled
                    else 'CHECKBOX_DEHLT',
                text="",
                emboss=False,
            ).module = module_name
            row.label(
                text="%s: %s%s%s" %(
                module_info.catagory,
                module_info.name,
                " | %s"%module_info.name_cn
                    if module_info.name_cn != "" else "",
                " | %s汉化"%module_info.author
                    if module_info.author != "" else ""
                )
            )

        # 显示缺失模组        
        if self.module_filter == 'ALL':
            missing_modules = self.filtered_missing_modules
            if len(missing_modules) > 0:
                layout.separator()
                layout.label(text="缺失的翻译文件")
                for module_name in missing_modules:
                    inner_box = layout.box()
                    row = inner_box.row()
                    row.operator(
                        "perfect_chinese.module_disable",
                        icon='CHECKBOX_HLT',
                        text="",
                        emboss=False,
                    ).module = module_name
                    row.label(text=module_name)

    def draw_options(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "button_toggle")
        if self.button_toggle:
            row.prop(self, "tooltips_included")
            row.prop(self, "new_dataname_included")
        # TODO 侧边栏面板
        # row.label(text="侧边栏")
        # row.prop(self, "sidebar_toggle", text="")
        # split = row.split()
        # split.enabled = self.sidebar_toggle
        # split.prop(self, "tab_category", text="")
    
    def draw_update(self, context):
        addon_updater_ops.update_settings_ui(self, context)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "tabs", expand=True)
        layout.separator()
        if self.tabs == 'CHINESE':
            self.draw_chinese(context)
        elif self.tabs == 'OPTIONS':
            self.draw_options(context)
        elif self.tabs == 'UPDATE':
            self.draw_update(context)
        layout.separator()

