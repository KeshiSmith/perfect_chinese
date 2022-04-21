# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
"""Blender UI integrations for the addon updater.

Implements draw calls, popups, and operators that use the addon_updater.
"""

import os
import traceback

import bpy
from bpy.app.handlers import persistent

# Safely import the updater.
# Prevents popups for users with invalid python installs e.g. missing libraries
# and will replace with a fake class instead if it fails (so UI draws work).
try:
  from .addon_updater import Updater as updater
except Exception as e:
  print("初始化更新器错误")
  print(str(e))
  traceback.print_exc()

  class SingletonUpdaterNone(object):
    """Fake, bare minimum fields and functions for the updater object."""
    def __init__(self):
      self.invalid_updater = True  # Used to distinguish bad install.

      self.addon = None
      self.verbose = False
      self.use_print_traces = True
      self.error = None
      self.error_msg = None
      self.async_checking = None

    def clear_state(self):
      self.addon = None
      self.verbose = False
      self.invalid_updater = True
      self.error = None
      self.error_msg = None
      self.async_checking = None

    def run_update(self, force, callback, clean):
      pass

    def check_for_update(self, now):
      pass

  updater = SingletonUpdaterNone()
  updater.error = "错误: 初始化更新器模组"
  updater.error_msg = str(e)

# Must declare this before classes are loaded, otherwise the bl_idname's will
# not match and have errors. Must be all lowercase and no spaces! Should also
# be unique among any other addons that could exist (using this updater code),
# to avoid clashes in operator registration.
updater.addon = "perfect_chinese"


# -----------------------------------------------------------------------------
# Blender version utils
# -----------------------------------------------------------------------------
def make_annotations(cls):
  """Add annotation attribute to fields to avoid Blender 2.8+ warnings"""
  if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
    return cls
  if bpy.app.version < (2, 93, 0):
    bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
  else:
    bl_props = {
        k: v
        for k, v in cls.__dict__.items()
        if isinstance(v, bpy.props._PropertyDeferred)
    }
  if bl_props:
    if '__annotations__' not in cls.__dict__:
      setattr(cls, '__annotations__', {})
    annotations = cls.__dict__['__annotations__']
    for k, v in bl_props.items():
      annotations[k] = v
      delattr(cls, k)
  return cls


def layout_split(layout, factor=0.0, align=False):
  """Intermediate method for pre and post blender 2.8 split UI function"""
  if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
    return layout.split(percentage=factor, align=align)
  return layout.split(factor=factor, align=align)


def get_user_preferences(context=None):
  """Intermediate method for pre and post blender 2.8 grabbing preferences"""
  if not context:
    context = bpy.context
  prefs = None
  if hasattr(context, "user_preferences"):
    prefs = context.user_preferences.addons.get(__package__, None)
  elif hasattr(context, "preferences"):
    prefs = context.preferences.addons.get(__package__, None)
  if prefs:
    return prefs.preferences
  # To make the addon stable and non-exception prone, return None
  # raise Exception("Could not fetch user preferences")
  return None


# -----------------------------------------------------------------------------
# Updater operators
# -----------------------------------------------------------------------------


# Simple popup to prompt use to check for update & offer install if available.
class AddonUpdaterInstallPopup(bpy.types.Operator):
  """Check and install update if available"""
  bl_label = "更新 '完美中文'"
  bl_idname = updater.addon + ".updater_install_popup"
  bl_description = "弹出检查并显示当前可获取的更新"
  bl_options = {'REGISTER', 'INTERNAL'}

  # if true, run clean install - ie remove all files before adding new
  # equivalent to deleting the addon and reinstalling, except the
  # updater folder/backup folder remains
  clean_install = bpy.props.BoolProperty(
      name="清洁安装",
      description="如果开启, 更新之前将完全清除插件目录，然后创建一个干净的安装",
      default=False,
      options={'HIDDEN'})

  ignore_enum = bpy.props.EnumProperty(name="运行更新",
                                       description="决定安装, 忽略, 或是推迟安装",
                                       items=[("install", "立刻更新", "立刻安装更新"),
                                              ("ignore", "忽略",
                                               "忽略这次更新以阻止弹窗提醒"),
                                              ("defer", "推迟",
                                               "推迟选择直到下次 blender 会话")],
                                       options={'HIDDEN'})

  def check(self, context):
    return True

  def invoke(self, context, event):
    return context.window_manager.invoke_props_dialog(self)

  def draw(self, context):
    layout = self.layout
    if updater.invalid_updater:
      layout.label(text="更新程序模组错误")
      return
    elif updater.update_ready:
      col = layout.column()
      col.scale_y = 0.7
      col.label(text="已准备更新至 {} !".format(str(updater.update_version)),
                icon="LOOP_FORWARDS")
      col.label(text="选择'立刻更新'并点击'确认'以完成安装, ", icon="BLANK1")
      col.label(text="或点击窗外可以延迟更新", icon="BLANK1")
      row = col.row()
      row.prop(self, "ignore_enum", expand=True)
      col.split()
    elif not updater.update_ready:
      col = layout.column()
      col.scale_y = 0.7
      col.label(text="没有获取到更新")
      col.label(text="按下'确认'以取消对话框")
      # add option to force install
    else:
      # Case: updater.update_ready = None
      # we have not yet checked for the update.
      layout.label(text="现在检查更新吗?")

    # Potentially in future, UI to 'check to select/revert to old version'.

  def execute(self, context):
    # In case of error importing updater.
    if updater.invalid_updater:
      return {'CANCELLED'}

    if updater.manual_only:
      bpy.ops.wm.url_open(url=updater.website)
    elif updater.update_ready:

      # Action based on enum selection.
      if self.ignore_enum == 'defer':
        return {'FINISHED'}
      elif self.ignore_enum == 'ignore':
        updater.ignore_update()
        return {'FINISHED'}

      res = updater.run_update(force=False,
                               callback=post_update_callback,
                               clean=self.clean_install)

      # Should return 0, if not something happened.
      if updater.verbose:
        if res == 0:
          print("更新器成功返回")
        else:
          print("更新器返回 {}, 发生错误".format(res))
    elif updater.update_ready is None:
      _ = updater.check_for_update(now=True)

      # Re-launch this dialog.
      atr = AddonUpdaterInstallPopup.bl_idname.split(".")
      getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
    else:
      updater.print_verbose("什么也没做, 没有更新准备")
    return {'FINISHED'}


# User preference check-now operator
class AddonUpdaterCheckNow(bpy.types.Operator):
  bl_label = "立刻为 '完美中文' 检查更新"
  bl_idname = updater.addon + ".updater_check_now"
  bl_description = "立刻为插件 '完美中文' 检查更新".format(updater.addon)
  bl_options = {'REGISTER', 'INTERNAL'}

  def execute(self, context):
    if updater.invalid_updater:
      return {'CANCELLED'}

    if updater.async_checking and updater.error is None:
      # Check already happened.
      # Used here to just avoid constant applying settings below.
      # Ignoring if error, to prevent being stuck on the error screen.
      return {'CANCELLED'}

    # apply the UI settings
    settings = get_user_preferences(context)
    if not settings:
      updater.print_verbose("无法获取 {} 的偏好设置, 跳过检查更新".format(__package__))
      return {'CANCELLED'}

    updater.set_check_interval(enabled=settings.auto_check_update,
                               months=settings.updater_interval_months,
                               days=settings.updater_interval_days,
                               hours=settings.updater_interval_hours,
                               minutes=settings.updater_interval_minutes)

    # Input is an optional callback function. This function should take a
    # bool input. If true: update ready, if false: no update ready.
    updater.check_for_update_now(ui_refresh)

    return {'FINISHED'}


class AddonUpdaterUpdateNow(bpy.types.Operator):
  bl_label = "立刻更新 '完美中文'"
  bl_idname = updater.addon + ".updater_update_now"
  bl_description = "更新 '完美中文' 至最新版本"
  bl_options = {'REGISTER', 'INTERNAL'}

  # If true, run clean install - ie remove all files before adding new
  # equivalent to deleting the addon and reinstalling, except the updater
  # folder/backup folder remains.
  clean_install = bpy.props.BoolProperty(
      name="清洁安装",
      description="如果开启, 更新之前将完全清除插件目录，然后创建一个干净的安装",
      default=False,
      options={'HIDDEN'})

  def execute(self, context):

    # in case of error importing updater
    if updater.invalid_updater:
      return {'CANCELLED'}

    if updater.manual_only:
      bpy.ops.wm.url_open(url=updater.website)
    if updater.update_ready:
      # if it fails, offer to open the website instead
      try:
        res = updater.run_update(force=False,
                                 callback=post_update_callback,
                                 clean=self.clean_install)

        # Should return 0, if not something happened.
        if updater.verbose:
          if res == 0:
            print("更新器成功返回")
          else:
            print("更新器返回 " + str(res) + ", 发生错误")
      except Exception as expt:
        updater._error = "尝试运行更新发生错误"
        updater._error_msg = str(expt)
        updater.print_trace()
        atr = AddonUpdaterInstallManually.bl_idname.split(".")
        getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
    elif updater.update_ready is None:
      (update_ready, version, link) = updater.check_for_update(now=True)
      # Re-launch this dialog.
      atr = AddonUpdaterInstallPopup.bl_idname.split(".")
      getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')

    elif not updater.update_ready:
      self.report({'INFO'}, "没有更新")
      return {'CANCELLED'}
    else:
      self.report({'ERROR'}, "尝试运行更新时发生错误")
      return {'CANCELLED'}

    return {'FINISHED'}


class AddonUpdaterUpdateTarget(bpy.types.Operator):
  bl_label = "'完美中文' 目标版本"
  bl_idname = updater.addon + ".updater_update_target"
  bl_description = "安装一个 '完美中文' 的目标版本"
  bl_options = {'REGISTER', 'INTERNAL'}

  def target_version(self, context):
    # In case of error importing updater.
    if updater.invalid_updater:
      ret = []

    ret = []
    i = 0
    for tag in updater.tags:
      ret.append((tag, tag, "选择安装 " + tag))
      i += 1
    return ret

  target = bpy.props.EnumProperty(name="安装的目标版本",
                                  description="选择安装的版本",
                                  items=target_version)

  # If true, run clean install - ie remove all files before adding new
  # equivalent to deleting the addon and reinstalling, except the
  # updater folder/backup folder remains.
  clean_install = bpy.props.BoolProperty(
      name="清洁安装",
      description="如果开启, 更新之前将完全清除插件目录，然后创建一个干净的安装",
      default=False,
      options={'HIDDEN'})

  @classmethod
  def poll(cls, context):
    if updater.invalid_updater:
      return False
    return updater.update_ready is not None and len(updater.tags) > 0

  def invoke(self, context, event):
    return context.window_manager.invoke_props_dialog(self)

  def draw(self, context):
    layout = self.layout
    if updater.invalid_updater:
      layout.label(text="更新错误")
      return
    split = layout_split(layout, factor=0.5)
    sub_col = split.column()
    sub_col.label(text="选择安装版本")
    sub_col = split.column()
    sub_col.prop(self, "target", text="")

  def execute(self, context):
    # In case of error importing updater.
    if updater.invalid_updater:
      return {'CANCELLED'}

    res = updater.run_update(force=False,
                             revert_tag=self.target,
                             callback=post_update_callback,
                             clean=self.clean_install)

    # Should return 0, if not something happened.
    if res == 0:
      updater.print_verbose("更新器成功返回")
    else:
      updater.print_verbose("更新器返回 {}, 发生错误".format(res))
      return {'CANCELLED'}

    return {'FINISHED'}


class AddonUpdaterInstallManually(bpy.types.Operator):
  """As a fallback, direct the user to download the addon manually"""
  bl_label = "手动安装更新"
  bl_idname = updater.addon + ".updater_install_manually"
  bl_description = "手动开始安装更新"
  bl_options = {'REGISTER', 'INTERNAL'}

  error = bpy.props.StringProperty(name="发生错误", default="", options={'HIDDEN'})

  def invoke(self, context, event):
    return context.window_manager.invoke_popup(self)

  def draw(self, context):
    layout = self.layout

    if updater.invalid_updater:
      layout.label(text="更新错误")
      return

    # Display error if a prior autoamted install failed.
    if self.error != "":
      col = layout.column()
      col.scale_y = 0.7
      col.label(text="尝试自动安装时发生一个问题", icon="ERROR")
      col.label(text="点击下面的'下载'按钮以安装", icon="BLANK1")
      col.label(text="这个 zip 文件似乎是一个正常的插件.", icon="BLANK1")
    else:
      col = layout.column()
      col.scale_y = 0.7
      col.label(text="手动安装插件")
      col.label(text="点击下面的'下载'按钮以安装", icon="BLANK1")
      col.label(text="这个 zip 文件似乎是一个正常的插件.", icon="BLANK1")

    # If check hasn't happened, i.e. accidentally called this menu,
    # allow to check here.

    row = layout.row()

    if updater.update_link is not None:
      row.operator("wm.url_open", text="直接下载").url = updater.update_link
    else:
      row.operator("wm.url_open", text="(检索直接下载失败)")
      row.enabled = False

      if updater.website is not None:
        row = layout.row()
        ops = row.operator("wm.url_open", text="打开网站")
        ops.url = updater.website
      else:
        row = layout.row()
        row.label(text="查看源网站下载更新")

  def execute(self, context):
    return {'FINISHED'}


class AddonUpdaterUpdatedSuccessful(bpy.types.Operator):
  """Addon in place, popup telling user it completed or what went wrong"""
  bl_label = "安装报告"
  bl_idname = updater.addon + ".updater_update_successful"
  bl_description = "更新安装响应"
  bl_options = {'REGISTER', 'INTERNAL', 'UNDO'}

  error = bpy.props.StringProperty(name="发生错误", default="", options={'HIDDEN'})

  def invoke(self, context, event):
    return context.window_manager.invoke_props_popup(self, event)

  def draw(self, context):
    layout = self.layout

    if updater.invalid_updater:
      layout.label(text="更新器错误")
      return

    saved = updater.json
    if self.error != "":
      col = layout.column()
      col.scale_y = 0.7
      col.label(text="错误: 不能安装", icon="ERROR")
      if updater.error_msg:
        msg = updater.error_msg
      else:
        msg = self.error
      col.label(text=str(msg), icon="BLANK1")
      rw = col.row()
      rw.scale_y = 2
      rw.operator("wm.url_open", text="点击以手动安装.",
                  icon="BLANK1").url = updater.website
    elif not updater.auto_reload_post_update:
      # Tell user to restart blender after an update/restore!
      if "just_restored" in saved and saved["just_restored"]:
        col = layout.column()
        col.label(text="插件已恢复", icon="RECOVER_LAST")
        alert_row = col.row()
        alert_row.alert = True
        alert_row.operator("wm.quit_blender",
                           text="重启 blender 以重新加载",
                           icon="BLANK1")
        updater.json_reset_restore()
      else:
        col = layout.column()
        col.label(text="插件已成功安装", icon="FILE_TICK")
        alert_row = col.row()
        alert_row.alert = True
        alert_row.operator("wm.quit_blender",
                           text="重启 blender 以重新加载",
                           icon="BLANK1")

    else:
      # reload addon, but still recommend they restart blender
      if "just_restored" in saved and saved["just_restored"]:
        col = layout.column()
        col.scale_y = 0.7
        col.label(text="插件已恢复", icon="RECOVER_LAST")
        col.label(text="考虑重启 blender 以全部重新加载", icon="BLANK1")
        updater.json_reset_restore()
      else:
        col = layout.column()
        col.scale_y = 0.7
        col.label(text="插件已成功安装", icon="FILE_TICK")
        col.label(text="考虑重启 blender 以全部重新加载", icon="BLANK1")

  def execute(self, context):
    return {'FINISHED'}


class AddonUpdaterRestoreBackup(bpy.types.Operator):
  """Restore addon from backup"""
  bl_label = "恢复备份"
  bl_idname = updater.addon + ".updater_restore_backup"
  bl_description = "恢复备份插件"
  bl_options = {'REGISTER', 'INTERNAL'}

  @classmethod
  def poll(cls, context):
    try:
      return os.path.isdir(os.path.join(updater.stage_path, "backup"))
    except:
      return False

  def execute(self, context):
    # in case of error importing updater
    if updater.invalid_updater:
      return {'CANCELLED'}
    updater.restore_backup()
    return {'FINISHED'}


class AddonUpdaterIgnore(bpy.types.Operator):
  """Ignore update to prevent future popups"""
  bl_label = "忽略更新"
  bl_label = "Ignore update"
  bl_idname = updater.addon + ".updater_ignore"
  bl_description = "忽略更新以阻止弹窗提醒"
  bl_options = {'REGISTER', 'INTERNAL'}

  @classmethod
  def poll(cls, context):
    if updater.invalid_updater:
      return False
    elif updater.update_ready:
      return True
    else:
      return False

  def execute(self, context):
    # in case of error importing updater
    if updater.invalid_updater:
      return {'CANCELLED'}
    updater.ignore_update()
    self.report({"INFO"}, "打开更新器首选项")
    return {'FINISHED'}


class AddonUpdaterEndBackground(bpy.types.Operator):
  """Stop checking for update in the background"""
  bl_label = "停止后台检查"
  bl_idname = updater.addon + ".end_background_check"
  bl_description = "停止后台的更新检查"
  bl_options = {'REGISTER', 'INTERNAL'}

  def execute(self, context):
    # in case of error importing updater
    if updater.invalid_updater:
      return {'CANCELLED'}
    updater.stop_async_check_update()
    return {'FINISHED'}


# -----------------------------------------------------------------------------
# Handler related, to create popups
# -----------------------------------------------------------------------------

# global vars used to prevent duplicate popup handlers
ran_auto_check_install_popup = False
ran_update_success_popup = False

# global var for preventing successive calls
ran_background_check = False


@persistent
def updater_run_success_popup_handler(scene):
  global ran_update_success_popup
  ran_update_success_popup = True

  # in case of error importing updater
  if updater.invalid_updater:
    return

  try:
    if "scene_update_post" in dir(bpy.app.handlers):
      bpy.app.handlers.scene_update_post.remove(
          updater_run_success_popup_handler)
    else:
      bpy.app.handlers.depsgraph_update_post.remove(
          updater_run_success_popup_handler)
  except:
    pass

  atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
  getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')


@persistent
def updater_run_install_popup_handler(scene):
  global ran_auto_check_install_popup
  ran_auto_check_install_popup = True
  updater.print_verbose("Running the install popup handler.")

  # in case of error importing updater
  if updater.invalid_updater:
    return

  try:
    if "scene_update_post" in dir(bpy.app.handlers):
      bpy.app.handlers.scene_update_post.remove(
          updater_run_install_popup_handler)
    else:
      bpy.app.handlers.depsgraph_update_post.remove(
          updater_run_install_popup_handler)
  except:
    pass

  if "ignore" in updater.json and updater.json["ignore"]:
    return  # Don't do popup if ignore pressed.
  elif "version_text" in updater.json and updater.json["version_text"].get(
      "version"):
    version = updater.json["version_text"]["version"]
    ver_tuple = updater.version_tuple_from_text(version)

    if ver_tuple < updater.current_version:
      # User probably manually installed to get the up to date addon
      # in here. Clear out the update flag using this function.
      updater.print_verbose("{} 更新器: 显示用户已更新, 清除标记".format(updater.addon))
      updater.json_reset_restore()
      return
  atr = AddonUpdaterInstallPopup.bl_idname.split(".")
  getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')


def background_update_callback(update_ready):
  """Passed into the updater, background thread updater"""
  global ran_auto_check_install_popup
  updater.print_verbose("运行后台更新回调")

  # In case of error importing updater.
  if updater.invalid_updater:
    return
  if not updater.show_popups:
    return
  if not update_ready:
    return

  # See if we need add to the update handler to trigger the popup.
  handlers = []
  if "scene_update_post" in dir(bpy.app.handlers):  # 2.7x
    handlers = bpy.app.handlers.scene_update_post
  else:  # 2.8+
    handlers = bpy.app.handlers.depsgraph_update_post
  in_handles = updater_run_install_popup_handler in handlers

  if in_handles or ran_auto_check_install_popup:
    return

  if "scene_update_post" in dir(bpy.app.handlers):  # 2.7x
    bpy.app.handlers.scene_update_post.append(
        updater_run_install_popup_handler)
  else:  # 2.8+
    bpy.app.handlers.depsgraph_update_post.append(
        updater_run_install_popup_handler)
  ran_auto_check_install_popup = True
  updater.print_verbose("尝试弹出提示对话框")


def post_update_callback(module_name, res=None):
  """Callback for once the run_update function has completed.

    Only makes sense to use this if "auto_reload_post_update" == False,
    i.e. don't auto-restart the addon.

    Arguments:
        module_name: returns the module name from updater, but unused here.
        res: If an error occurred, this is the detail string.
    """

  # In case of error importing updater.
  if updater.invalid_updater:
    return

  if res is None:
    # This is the same code as in conditional at the end of the register
    # function, ie if "auto_reload_post_update" == True, skip code.
    updater.print_verbose("{} 更新器: 运行 POST 更新回调".format(updater.addon))

    atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
    getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
    global ran_update_success_popup
    ran_update_success_popup = True
  else:
    # Some kind of error occurred and it was unable to install, offer
    # manual download instead.
    atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
    getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT', error=res)
  return


def ui_refresh(update_status):
  """Redraw the ui once an async thread has completed"""
  for windowManager in bpy.data.window_managers:
    for window in windowManager.windows:
      for area in window.screen.areas:
        area.tag_redraw()


def check_for_update_background():
  """Function for asynchronous background check.

    *Could* be called on register, but would be bad practice as the bare
    minimum code should run at the moment of registration (addon ticked).
    """
  if updater.invalid_updater:
    return
  global ran_background_check
  if ran_background_check:
    # Global var ensures check only happens once.
    return
  elif updater.update_ready is not None or updater.async_checking:
    # Check already happened.
    # Used here to just avoid constant applying settings below.
    return

  # Apply the UI settings.
  settings = get_user_preferences(bpy.context)
  if not settings:
    return
  updater.set_check_interval(enabled=settings.auto_check_update,
                             months=settings.updater_interval_months,
                             days=settings.updater_interval_days,
                             hours=settings.updater_interval_hours,
                             minutes=settings.updater_interval_minutes)

  # Input is an optional callback function. This function should take a bool
  # input, if true: update ready, if false: no update ready.
  updater.check_for_update_async(background_update_callback)
  ran_background_check = True


def check_for_update_nonthreaded(self, context):
  """Can be placed in front of other operators to launch when pressed"""
  if updater.invalid_updater:
    return

  # Only check if it's ready, ie after the time interval specified should
  # be the async wrapper call here.
  settings = get_user_preferences(bpy.context)
  if not settings:
    if updater.verbose:
      print("无法获取 {} 偏好设置, 跳过检查更新".format(__package__))
    return
  updater.set_check_interval(enabled=settings.auto_check_update,
                             months=settings.updater_interval_months,
                             days=settings.updater_interval_days,
                             hours=settings.updater_interval_hours,
                             minutes=settings.updater_interval_minutes)

  (update_ready, version, link) = updater.check_for_update(now=False)
  if update_ready:
    atr = AddonUpdaterInstallPopup.bl_idname.split(".")
    getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
  else:
    updater.print_verbose("没有更新准备")
    self.report({'INFO'}, "没有更新准备")


def show_reload_popup():
  """For use in register only, to show popup after re-enabling the addon.

    Must be enabled by developer.
    """
  if updater.invalid_updater:
    return
  saved_state = updater.json
  global ran_update_success_popup

  has_state = saved_state is not None
  just_updated = "just_updated" in saved_state
  updated_info = saved_state["just_updated"]

  if not (has_state and just_updated and updated_info):
    return

  updater.json_reset_postupdate()  # So this only runs once.

  # No handlers in this case.
  if not updater.auto_reload_post_update:
    return

  # See if we need add to the update handler to trigger the popup.
  handlers = []
  if "scene_update_post" in dir(bpy.app.handlers):  # 2.7x
    handlers = bpy.app.handlers.scene_update_post
  else:  # 2.8+
    handlers = bpy.app.handlers.depsgraph_update_post
  in_handles = updater_run_success_popup_handler in handlers

  if in_handles or ran_update_success_popup:
    return

  if "scene_update_post" in dir(bpy.app.handlers):  # 2.7x
    bpy.app.handlers.scene_update_post.append(
        updater_run_success_popup_handler)
  else:  # 2.8+
    bpy.app.handlers.depsgraph_update_post.append(
        updater_run_success_popup_handler)
  ran_update_success_popup = True


# -----------------------------------------------------------------------------
# Example UI integrations
# -----------------------------------------------------------------------------
def update_notice_box_ui(self, context):
  """Update notice draw, to add to the end or beginning of a panel.

    After a check for update has occurred, this function will draw a box
    saying an update is ready, and give a button for: update now, open website,
    or ignore popup. Ideal to be placed at the end / beginning of a panel.
    """

  if updater.invalid_updater:
    return

  saved_state = updater.json
  if not updater.auto_reload_post_update:
    if "just_updated" in saved_state and saved_state["just_updated"]:
      layout = self.layout
      box = layout.box()
      col = box.column()
      alert_row = col.row()
      alert_row.alert = True
      alert_row.operator("wm.quit_blender", text="重启 blender", icon="ERROR")
      col.label(text="以完成更新")
      return

  # If user pressed ignore, don't draw the box.
  if "ignore" in updater.json and updater.json["ignore"]:
    return
  if not updater.update_ready:
    return

  layout = self.layout
  box = layout.box()
  col = box.column(align=True)
  col.alert = True
  col.label(text="更新已准备完毕!", icon="ERROR")
  col.alert = False
  col.separator()
  row = col.row(align=True)
  split = row.split(align=True)
  colL = split.column(align=True)
  colL.scale_y = 1.5
  colL.operator(AddonUpdaterIgnore.bl_idname, icon="X", text="Ignore")
  colR = split.column(align=True)
  colR.scale_y = 1.5
  if not updater.manual_only:
    colR.operator(AddonUpdaterUpdateNow.bl_idname,
                  text="更新",
                  icon="LOOP_FORWARDS")
    col.operator("wm.url_open", text="打开网站").url = updater.website
    # ops = col.operator("wm.url_open",text="Direct download")
    # ops.url=updater.update_link
    col.operator(AddonUpdaterInstallManually.bl_idname,
                 text="Install manually")
  else:
    # ops = col.operator("wm.url_open", text="Direct download")
    # ops.url=updater.update_link
    col.operator("wm.url_open", text="Get it now").url = updater.website


def update_settings_ui(self, context, element=None):
  """Preferences - for drawing with full width inside user preferences

    A function that can be run inside user preferences panel for prefs UI.
    Place inside UI draw using:
        addon_updater_ops.update_settings_ui(self, context)
    or by:
        addon_updater_ops.update_settings_ui(context)
    """

  # Element is a UI element, such as layout, a row, column, or box.
  if element is None:
    element = self.layout
  box = element.box()

  # In case of error importing updater.
  if updater.invalid_updater:
    box.label(text="初始化更新器错误代码:")
    box.label(text=updater.error_msg)
    return
  settings = get_user_preferences(context)
  if not settings:
    box.label(text="获取更新器偏好设置错误", icon='ERROR')
    return

  # auto-update settings
  box.label(text="更新器设置")
  row = box.row()

  # special case to tell user to restart blender, if set that way
  if not updater.auto_reload_post_update:
    saved_state = updater.json
    if "just_updated" in saved_state and saved_state["just_updated"]:
      row.alert = True
      row.operator("wm.quit_blender", text="重启 Blender 以完成更新", icon="ERROR")
      return

  split = layout_split(row, factor=0.4)
  sub_col = split.column()
  sub_col.prop(settings, "auto_check_update")
  sub_col = split.column()

  if not settings.auto_check_update:
    sub_col.enabled = False
  sub_row = sub_col.row()
  sub_row.label(text="更新检查间隔")
  sub_row = sub_col.row(align=True)
  check_col = sub_row.column(align=True)
  check_col.prop(settings, "updater_interval_months")
  check_col = sub_row.column(align=True)
  check_col.prop(settings, "updater_interval_days")
  # check_col = sub_row.column(align=True)
  # check_col.prop(settings,"updater_interval_hours")
  # check_col = sub_row.column(align=True)
  # check_col.prop(settings,"updater_interval_minutes")

  # Checking / managing updates.
  row = box.row()
  col = row.column()
  if updater.error is not None:
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.scale_y = 2
    if "ssl" in updater.error_msg.lower():
      split.enabled = True
      split.operator(AddonUpdaterInstallManually.bl_idname, text=updater.error)
    else:
      split.enabled = False
      split.operator(AddonUpdaterCheckNow.bl_idname, text=updater.error)
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname,
                   text="",
                   icon="FILE_REFRESH")

  elif updater.update_ready is None and not updater.async_checking:
    col.scale_y = 2
    col.operator(AddonUpdaterCheckNow.bl_idname)
  elif updater.update_ready is None:  # async is running
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.enabled = False
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname, text="检查中...")
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterEndBackground.bl_idname, text="", icon="X")

  elif updater.include_branches and \
          len(updater.tags) == len(updater.include_branch_list) and not \
          updater.manual_only:
    # No releases found, but still show the appropriate branch.
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.scale_y = 2
    update_now_txt = "直接更新至 {}".format(updater.include_branch_list[0])
    split.operator(AddonUpdaterUpdateNow.bl_idname, text=update_now_txt)
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname,
                   text="",
                   icon="FILE_REFRESH")

  elif updater.update_ready and not updater.manual_only:
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterUpdateNow.bl_idname,
                   text="直接更新至 " + str(updater.update_version))
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname,
                   text="",
                   icon="FILE_REFRESH")

  elif updater.update_ready and updater.manual_only:
    col.scale_y = 2
    dl_now_txt = "下载 " + str(updater.update_version)
    col.operator("wm.url_open", text=dl_now_txt).url = updater.website
  else:  # i.e. that updater.update_ready == False.
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.enabled = False
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname, text="插件已更新至最新")
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname,
                   text="",
                   icon="FILE_REFRESH")

  if not updater.manual_only:
    col = row.column(align=True)
    if updater.include_branches and len(updater.include_branch_list) > 0:
      branch = updater.include_branch_list[0]
      col.operator(AddonUpdaterUpdateTarget.bl_idname,
                   text="安装最新的 {} 版本 / 老版本".format(branch))
    else:
      col.operator(AddonUpdaterUpdateTarget.bl_idname, text="重新安装 / 安装旧版本")
    last_date = "未发现"
    backup_path = os.path.join(updater.stage_path, "backup")
    if "backup_date" in updater.json and os.path.isdir(backup_path):
      if updater.json["backup_date"] == "":
        last_date = "日期未发现"
      else:
        last_date = updater.json["backup_date"]
    backup_text = "恢复插件备份 ({})".format(last_date)
    col.operator(AddonUpdaterRestoreBackup.bl_idname, text=backup_text)

  row = box.row()
  row.scale_y = 0.7
  last_check = updater.json["last_check"]
  if updater.error is not None and updater.error_msg is not None:
    row.label(text=updater.error_msg)
  elif last_check:
    last_check = last_check[0:last_check.index(".")]
    row.label(text="上次检查时间: " + last_check)
  else:
    row.label(text="上次检查时间: 无")


def update_settings_ui_condensed(self, context, element=None):
  """Preferences - Condensed drawing within preferences.

    Alternate draw for user preferences or other places, does not draw a box.
    """

  # Element is a UI element, such as layout, a row, column, or box.
  if element is None:
    element = self.layout
  row = element.row()

  # In case of error importing updater.
  if updater.invalid_updater:
    row.label(text="错误初始化更新器代码:")
    row.label(text=updater.error_msg)
    return
  settings = get_user_preferences(context)
  if not settings:
    row.label(text="错误获取更新器偏好设置", icon='ERROR')
    return

  # Special case to tell user to restart blender, if set that way.
  if not updater.auto_reload_post_update:
    saved_state = updater.json
    if "just_updated" in saved_state and saved_state["just_updated"]:
      row.alert = True  # mark red
      row.operator("wm.quit_blender", text="重启 blender 以完成更新", icon="ERROR")
      return

  col = row.column()
  if updater.error is not None:
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.scale_y = 2
    if "ssl" in updater.error_msg.lower():
      split.enabled = True
      split.operator(AddonUpdaterInstallManually.bl_idname, text=updater.error)
    else:
      split.enabled = False
      split.operator(AddonUpdaterCheckNow.bl_idname, text=updater.error)
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname,
                   text="",
                   icon="FILE_REFRESH")

  elif updater.update_ready is None and not updater.async_checking:
    col.scale_y = 2
    col.operator(AddonUpdaterCheckNow.bl_idname)
  elif updater.update_ready is None:  # Async is running.
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.enabled = False
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname, text="检查中...")
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterEndBackground.bl_idname, text="", icon="X")

  elif updater.include_branches and \
          len(updater.tags) == len(updater.include_branch_list) and not \
          updater.manual_only:
    # No releases found, but still show the appropriate branch.
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.scale_y = 2
    now_txt = "直接更新至 " + str(updater.include_branch_list[0])
    split.operator(AddonUpdaterUpdateNow.bl_idname, text=now_txt)
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname,
                   text="",
                   icon="FILE_REFRESH")

  elif updater.update_ready and not updater.manual_only:
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterUpdateNow.bl_idname,
                   text="立刻更新至 " + str(updater.update_version))
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname,
                   text="",
                   icon="FILE_REFRESH")

  elif updater.update_ready and updater.manual_only:
    col.scale_y = 2
    dl_txt = "下载" + str(updater.update_version)
    col.operator("wm.url_open", text=dl_txt).url = updater.website
  else:  # i.e. that updater.update_ready == False.
    sub_col = col.row(align=True)
    sub_col.scale_y = 1
    split = sub_col.split(align=True)
    split.enabled = False
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname, text="插件已更新至最新")
    split = sub_col.split(align=True)
    split.scale_y = 2
    split.operator(AddonUpdaterCheckNow.bl_idname,
                   text="",
                   icon="FILE_REFRESH")

  row = element.row()
  row.prop(settings, "auto_check_update")

  row = element.row()
  row.scale_y = 0.7
  last_check = updater.json["last_check"]
  if updater.error is not None and updater.error_msg is not None:
    row.label(text=updater.error_msg)
  elif last_check != "" and last_check is not None:
    last_check = last_check[0:last_check.index(".")]
    row.label(text="上次检查时间: " + last_check)
  else:
    row.label(text="上次检查时间: 无")


def skip_tag_function(self, tag):
  """A global function for tag skipping.

    A way to filter which tags are displayed, e.g. to limit downgrading too
    long ago.

    Args:
        self: The instance of the singleton addon update.
        tag: the text content of a tag from the repo, e.g. "v1.2.3".

    Returns:
        bool: True to skip this tag name (ie don't allow for downloading this
            version), or False if the tag is allowed.
    """

  # In case of error importing updater.
  if self.invalid_updater:
    return False

  # ---- write any custom code here, return true to disallow version ---- #
  #
  # # Filter out e.g. if 'beta' is in name of release
  # if 'beta' in tag.lower():
  # 	return True
  # ---- write any custom code above, return true to disallow version --- #

  if self.include_branches:
    for branch in self.include_branch_list:
      if tag["name"].lower() == branch:
        return False

  # Function converting string to tuple, ignoring e.g. leading 'v'.
  # Be aware that this strips out other text that you might otherwise
  # want to be kept and accounted for when checking tags (e.g. v1.1a vs 1.1b)
  tupled = self.version_tuple_from_text(tag["name"])
  if not isinstance(tupled, tuple):
    return True

  # Select the min tag version - change tuple accordingly.
  if self.version_min_update is not None:
    if tupled < self.version_min_update:
      return True  # Skip if current version below this.

  # Select the max tag version.
  if self.version_max_update is not None:
    if tupled >= self.version_max_update:
      return True  # Skip if current version at or above this.

  # In all other cases, allow showing the tag for updating/reverting.
  # To simply and always show all tags, this return False could be moved
  # to the start of the function definition so all tags are allowed.
  return False


def select_link_function(self, tag):
  """Only customize if trying to leverage "attachments" in *GitHub* releases.

    A way to select from one or multiple attached downloadable files from the
    server, instead of downloading the default release/tag source code.
    """

  # -- Default, universal case (and is the only option for GitLab/Bitbucket)
  link = tag["zipball_url"]

  # -- Example: select the first (or only) asset instead source code --
  # if "assets" in tag and "browser_download_url" in tag["assets"][0]:
  # 	link = tag["assets"][0]["browser_download_url"]

  # -- Example: select asset based on OS, where multiple builds exist --
  # # not tested/no error checking, modify to fit your own needs!
  # # assume each release has three attached builds:
  # #		release_windows.zip, release_OSX.zip, release_linux.zip
  # # This also would logically not be used with "branches" enabled
  # if platform.system() == "Darwin": # ie OSX
  # 	link = [asset for asset in tag["assets"] if 'OSX' in asset][0]
  # elif platform.system() == "Windows":
  # 	link = [asset for asset in tag["assets"] if 'windows' in asset][0]
  # elif platform.system() == "Linux":
  # 	link = [asset for asset in tag["assets"] if 'linux' in asset][0]

  return link


# -----------------------------------------------------------------------------
# Register, should be run in the register module itself
# -----------------------------------------------------------------------------
classes = (AddonUpdaterInstallPopup, AddonUpdaterCheckNow,
           AddonUpdaterUpdateNow, AddonUpdaterUpdateTarget,
           AddonUpdaterInstallManually, AddonUpdaterUpdatedSuccessful,
           AddonUpdaterRestoreBackup, AddonUpdaterIgnore,
           AddonUpdaterEndBackground)


def register(bl_info):
  """Registering the operators in this module"""
  # Safer failure in case of issue loading module.
  if updater.error:
    print("退出更新器注册, " + updater.error)
    return
  updater.clear_state()  # Clear internal vars, avoids reloading oddities.

  # Confirm your updater "engine" (Github is default if not specified).
  updater.engine = "Github"
  # updater.engine = "GitLab"
  # updater.engine = "Bitbucket"

  # If using private repository, indicate the token here.
  # Must be set after assigning the engine.
  # **WARNING** Depending on the engine, this token can act like a password!!
  # Only provide a token if the project is *non-public*, see readme for
  # other considerations and suggestions from a security standpoint.
  updater.private_token = None  # "tokenstring"

  # Choose your own username, must match website (not needed for GitLab).
  updater.user = "KeshiSmith"

  # Choose your own repository, must match git name for GitHUb and Bitbucket,
  # for GitLab use project ID (numbers only).
  updater.repo = "perfect_chinese"

  # updater.addon = # define at top of module, MUST be done first

  # Website for manual addon download, optional but recommended to set.
  updater.website = "https://github.com/KeshiSmith/perfect_chinese/"

  # Addon subfolder path.
  # "sample/path/to/addon"
  # default is "" or None, meaning root
  updater.subfolder_path = ""

  # Used to check/compare versions.
  updater.current_version = bl_info["version"]

  # Optional, to hard-set update frequency, use this here - however, this
  # demo has this set via UI properties.
  # updater.set_check_interval(enabled=False, months=0, days=0, hours=0, minutes=2)

  # Optional, consider turning off for production or allow as an option
  # This will print out additional debugging info to the console
  updater.verbose = True  # make False for production default

  # Optional, customize where the addon updater processing subfolder is,
  # essentially a staging folder used by the updater on its own
  # Needs to be within the same folder as the addon itself
  # Need to supply a full, absolute path to folder
  # updater.updater_path = # set path of updater folder, by default:
  # 			/addons/{__package__}/{__package__}_updater

  # Auto create a backup of the addon when installing other versions.
  updater.backup_current = True  # True by default

  # Sample ignore patterns for when creating backup of current during update.
  updater.backup_ignore_patterns = ["__pycache__"]
  # Alternate example patterns:
  # updater.backup_ignore_patterns = [".git", "__pycache__", "*.bat", ".gitignore", "*.exe"]

  # Patterns for files to actively overwrite if found in new update file and
  # are also found in the currently installed addon. Note that by default
  # (ie if set to []), updates are installed in the same way as blender:
  # .py files are replaced, but other file types (e.g. json, txt, blend)
  # will NOT be overwritten if already present in current install. Thus
  # if you want to automatically update resources/non py files, add them as a
  # part of the pattern list below so they will always be overwritten by an
  # update. If a pattern file is not found in new update, no action is taken
  # NOTE: This does NOT delete anything proactively, rather only defines what
  # is allowed to be overwritten during an update execution.
  updater.overwrite_patterns = ["*.po", "README.md"]
  # updater.overwrite_patterns = []
  # other examples:
  # ["*"] means ALL files/folders will be overwritten by update, was the
  #    behavior pre updater v1.0.4.
  # [] or ["*.py","*.pyc"] matches default blender behavior, ie same effect
  #    if user installs update manually without deleting the existing addon
  #    first e.g. if existing install and update both have a resource.blend
  #    file, the existing installed one will remain.
  # ["some.py"] means if some.py is found in addon update, it will overwrite
  #    any existing some.py in current addon install, if any.
  # ["*.json"] means all json files found in addon update will overwrite
  #    those of same name in current install.
  # ["*.png","README.md","LICENSE.txt"] means the readme, license, and all
  #    pngs will be overwritten by update.

  # Patterns for files to actively remove prior to running update.
  # Useful if wanting to remove old code due to changes in filenames
  # that otherwise would accumulate. Note: this runs after taking
  # a backup (if enabled) but before placing in new update. If the same
  # file name removed exists in the update, then it acts as if pattern
  # is placed in the overwrite_patterns property. Note this is effectively
  # ignored if clean=True in the run_update method.
  updater.remove_pre_update_patterns = ["*.py", "*.pyc"]
  # Note setting ["*"] here is equivalent to always running updates with
  # clean = True in the run_update method, ie the equivalent of a fresh,
  # new install. This would also delete any resources or user-made/modified
  # files setting ["__pycache__"] ensures the pycache folder always removed.
  # The configuration of ["*.py", "*.pyc"] is a safe option as this
  # will ensure no old python files/caches remain in event different addon
  # versions have different filenames or structures.

  # Allow branches like 'master' as an option to update to, regardless
  # of release or version.
  # Default behavior: releases will still be used for auto check (popup),
  # but the user has the option from user preferences to directly
  # update to the master branch or any other branches specified using
  # the "install {branch}/older version" operator.
  updater.include_branches = True

  # (GitHub only) This options allows using "releases" instead of "tags",
  # which enables pulling down release logs/notes, as well as installs update
  # from release-attached zips (instead of the auto-packaged code generated
  # with a release/tag). Setting has no impact on BitBucket or GitLab repos.
  updater.use_releases = False
  # Note: Releases always have a tag, but a tag may not always be a release.
  # Therefore, setting True above will filter out any non-annotated tags.
  # Note 2: Using this option will also display (and filter by) the release
  # name instead of the tag name, bear this in mind given the
  # skip_tag_function filtering above.

  # Populate if using "include_branches" option above.
  # Note: updater.include_branch_list defaults to ['master'] branch if set to
  # none. Example targeting another multiple branches allowed to pull from:
  # updater.include_branch_list = ['master', 'dev']
  updater.include_branch_list = None  # None is the equivalent = ['master']

  # Only allow manual install, thus prompting the user to open
  # the addon's web page to download, specifically: updater.website
  # Useful if only wanting to get notification of updates but not
  # directly install.
  updater.manual_only = False

  # Used for development only, "pretend" to install an update to test
  # reloading conditions.
  updater.fake_install = False  # Set to true to test callback/reloading.

  # Show popups, ie if auto-check for update is enabled or a previous
  # check for update in user preferences found a new version, show a popup
  # (at most once per blender session, and it provides an option to ignore
  # for future sessions); default behavior is set to True.
  updater.show_popups = True
  # note: if set to false, there will still be an "update ready" box drawn
  # using the `update_notice_box_ui` panel function.

  # Override with a custom function on what tags
  # to skip showing for updater; see code for function above.
  # Set the min and max versions allowed to install.
  # Optional, default None
  # min install (>=) will install this and higher
  updater.version_min_update = (0, 0, 0)
  # updater.version_min_update = None  # None or default for no minimum.

  # Max install (<) will install strictly anything lower than this version
  # number, useful to limit the max version a given user can install (e.g.
  # if support for a future version of blender is going away, and you don't
  # want users to be prompted to install a non-functioning addon)
  # updater.version_max_update = (9,9,9)
  updater.version_max_update = None  # None or default for no max.

  # Function defined above, customize as appropriate per repository
  updater.skip_tag = skip_tag_function  # min and max used in this function

  # Function defined above, optionally customize as needed per repository.
  updater.select_link = select_link_function

  # Recommended false to encourage blender restarts on update completion
  # Setting this option to True is NOT as stable as false (could cause
  # blender crashes).
  updater.auto_reload_post_update = False

  # The register line items for all operators/panels.
  # If using bpy.utils.register_module(__name__) to register elsewhere
  # in the addon, delete these lines (also from unregister).
  for cls in classes:
    # Apply annotations to remove Blender 2.8+ warnings, no effect on 2.7
    make_annotations(cls)
    # Comment out this line if using bpy.utils.register_module(__name__)
    bpy.utils.register_class(cls)

  # Special situation: we just updated the addon, show a popup to tell the
  # user it worked. Could enclosed in try/catch in case other issues arise.
  show_reload_popup()


def unregister():
  for cls in reversed(classes):
    # Comment out this line if using bpy.utils.unregister_module(__name__).
    bpy.utils.unregister_class(cls)

  # Clear global vars since they may persist if not restarting blender.
  updater.clear_state()  # Clear internal vars, avoids reloading oddities.

  global ran_auto_check_install_popup
  ran_auto_check_install_popup = False

  global ran_update_success_popup
  ran_update_success_popup = False

  global ran_background_check
  ran_background_check = False
