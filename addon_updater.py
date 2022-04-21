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
"""
See documentation for usage
https://github.com/CGCookie/blender-addon-updater
"""

__version__ = "1.1.0"

import errno
import traceback
import platform
import ssl
import urllib.request
import urllib
import os
import json
import zipfile
import shutil
import threading
import fnmatch
from datetime import datetime, timedelta

# Blender imports, used in limited cases.
import bpy
import addon_utils

# -----------------------------------------------------------------------------
# The main class
# -----------------------------------------------------------------------------


class SingletonUpdater:
  """Addon updater service class.

    This is the singleton class to instance once and then reference where
    needed throughout the addon. It implements all the interfaces for running
    updates.
  """
  def __init__(self):

    self._engine = GithubEngine()
    self._user = None
    self._repo = None
    self._website = None
    self._current_version = None
    self._subfolder_path = None
    self._tags = list()
    self._tag_latest = None
    self._tag_names = list()
    self._latest_release = None
    self._use_releases = False
    self._include_branches = False
    self._include_branch_list = ['master']
    self._include_branch_auto_check = False
    self._manual_only = False
    self._version_min_update = None
    self._version_max_update = None

    # By default, backup current addon on update/target install.
    self._backup_current = True
    self._backup_ignore_patterns = None

    # Set patterns the files to overwrite during an update.
    self._overwrite_patterns = ["*.py", "*.pyc"]
    self._remove_pre_update_patterns = list()

    # By default, don't auto disable+re-enable the addon after an update,
    # as this is less stable/often won't fully reload all modules anyways.
    self._auto_reload_post_update = False

    # Settings for the frequency of automated background checks.
    self._check_interval_enabled = False
    self._check_interval_months = 0
    self._check_interval_days = 7
    self._check_interval_hours = 0
    self._check_interval_minutes = 0

    # runtime variables, initial conditions
    self._verbose = False
    self._use_print_traces = True
    self._fake_install = False
    self._async_checking = False  # only true when async daemon started
    self._update_ready = None
    self._update_link = None
    self._update_version = None
    self._source_zip = None
    self._check_thread = None
    self._select_link = None
    self.skip_tag = None

    # Get data from the running blender module (addon).
    self._addon = __package__.lower()
    self._addon_package = __package__  # Must not change.
    self._updater_path = os.path.join(os.path.dirname(__file__),
                                      self._addon + "_updater")
    self._addon_root = os.path.dirname(__file__)
    self._json = dict()
    self._error = None
    self._error_msg = None
    self._prefiltered_tag_count = 0

    # UI properties, not used within this module but still useful to have.

    # to verify a valid import, in place of placeholder import
    self.show_popups = True  # UI uses to show popups or not.
    self.invalid_updater = False

    # pre-assign basic select-link function
    def select_link_function(self, tag):
      return tag["zipball_url"]

    self._select_link = select_link_function

  def print_trace(self):
    """Print handled exception details when use_print_traces is set"""
    if self._use_print_traces:
      traceback.print_exc()

  def print_verbose(self, msg):
    """Print out a verbose logging message if verbose is true."""
    if not self._verbose:
      return
    print("{} addon: ".format(self.addon) + msg)

  # -------------------------------------------------------------------------
  # Getters and setters
  # -------------------------------------------------------------------------
  @property
  def addon(self):
    return self._addon

  @addon.setter
  def addon(self, value):
    self._addon = str(value)

  @property
  def api_url(self):
    return self._engine.api_url

  @api_url.setter
  def api_url(self, value):
    if not self.check_is_url(value):
      raise ValueError("非法地址: " + value)
    self._engine.api_url = value

  @property
  def async_checking(self):
    return self._async_checking

  @property
  def auto_reload_post_update(self):
    return self._auto_reload_post_update

  @auto_reload_post_update.setter
  def auto_reload_post_update(self, value):
    try:
      self._auto_reload_post_update = bool(value)
    except:
      raise ValueError("auto_reload_post_update 必须是布尔值")

  @property
  def backup_current(self):
    return self._backup_current

  @backup_current.setter
  def backup_current(self, value):
    if value is None:
      self._backup_current = False
    else:
      self._backup_current = value

  @property
  def backup_ignore_patterns(self):
    return self._backup_ignore_patterns

  @backup_ignore_patterns.setter
  def backup_ignore_patterns(self, value):
    if value is None:
      self._backup_ignore_patterns = None
    elif not isinstance(value, list):
      raise ValueError("_backup_ignore_patterns 的类型必须是列表")
    else:
      self._backup_ignore_patterns = value

  @property
  def check_interval(self):
    return (self._check_interval_enabled, self._check_interval_months,
            self._check_interval_days, self._check_interval_hours,
            self._check_interval_minutes)

  @property
  def current_version(self):
    return self._current_version

  @current_version.setter
  def current_version(self, tuple_values):
    if tuple_values is None:
      self._current_version = None
      return
    elif type(tuple_values) is not tuple:
      try:
        tuple(tuple_values)
      except:
        raise ValueError("current_version 必须是个整型元组")
    for i in tuple_values:
      if type(i) is not int:
        raise ValueError("current_version 必须是个整型元组")
    self._current_version = tuple(tuple_values)

  @property
  def engine(self):
    return self._engine.name

  @engine.setter
  def engine(self, value):
    engine = value.lower()
    if engine == "github":
      self._engine = GithubEngine()
    elif engine == "gitlab":
      self._engine = GitlabEngine()
    elif engine == "bitbucket":
      self._engine = BitbucketEngine()
    else:
      raise ValueError("使用非法引擎")

  @property
  def error(self):
    return self._error

  @property
  def error_msg(self):
    return self._error_msg

  @property
  def fake_install(self):
    return self._fake_install

  @fake_install.setter
  def fake_install(self, value):
    if not isinstance(value, bool):
      raise ValueError("fake_install 必须是个布尔值")
    self._fake_install = bool(value)

  # not currently used
  @property
  def include_branch_auto_check(self):
    return self._include_branch_auto_check

  @include_branch_auto_check.setter
  def include_branch_auto_check(self, value):
    try:
      self._include_branch_auto_check = bool(value)
    except:
      raise ValueError("include_branch_autocheck 必须是个布尔值")

  @property
  def include_branch_list(self):
    return self._include_branch_list

  @include_branch_list.setter
  def include_branch_list(self, value):
    try:
      if value is None:
        self._include_branch_list = ['master']
      elif not isinstance(value, list) or len(value) == 0:
        raise ValueError("include_branch_list 应是个合法的分支列表")
      else:
        self._include_branch_list = value
    except:
      raise ValueError("include_branch_list 应是个合法的分支列表")

  @property
  def include_branches(self):
    return self._include_branches

  @include_branches.setter
  def include_branches(self, value):
    try:
      self._include_branches = bool(value)
    except:
      raise ValueError("include_branches 必须是个布尔值")

  @property
  def json(self):
    if len(self._json) == 0:
      self.set_updater_json()
    return self._json

  @property
  def latest_release(self):
    if self._latest_release is None:
      return None
    return self._latest_release

  @property
  def manual_only(self):
    return self._manual_only

  @manual_only.setter
  def manual_only(self, value):
    try:
      self._manual_only = bool(value)
    except:
      raise ValueError("manual_only 必须是个布尔值")

  @property
  def overwrite_patterns(self):
    return self._overwrite_patterns

  @overwrite_patterns.setter
  def overwrite_patterns(self, value):
    if value is None:
      self._overwrite_patterns = ["*.py", "*.pyc"]
    elif not isinstance(value, list):
      raise ValueError("overwrite_patterns 需要是列表格式")
    else:
      self._overwrite_patterns = value

  @property
  def private_token(self):
    return self._engine.token

  @private_token.setter
  def private_token(self, value):
    if value is None:
      self._engine.token = None
    else:
      self._engine.token = str(value)

  @property
  def remove_pre_update_patterns(self):
    return self._remove_pre_update_patterns

  @remove_pre_update_patterns.setter
  def remove_pre_update_patterns(self, value):
    if value is None:
      self._remove_pre_update_patterns = list()
    elif not isinstance(value, list):
      raise ValueError("remove_pre_update_patterns 需要是列表格式")
    else:
      self._remove_pre_update_patterns = value

  @property
  def repo(self):
    return self._repo

  @repo.setter
  def repo(self, value):
    try:
      self._repo = str(value)
    except:
      raise ValueError("User 必须是个字符串")

  @property
  def select_link(self):
    return self._select_link

  @select_link.setter
  def select_link(self, value):
    # ensure it is a function assignment, with signature:
    # input self, tag; returns link name
    if not hasattr(value, "__call__"):
      raise ValueError("select_link 必须是个函数")
    self._select_link = value

  @property
  def stage_path(self):
    return self._updater_path

  @stage_path.setter
  def stage_path(self, value):
    if value is None:
      if self._verbose: print("终止赋值 stage_path, 它是 None")
      return
    elif value is not None and not os.path.exists(value):
      try:
        os.makedirs(value)
      except:
        if self._verbose: print("错误尝试 stage_path")
        self.print_trace()
        return
    self._updater_path = value

  @property
  def subfolder_path(self):
    return self._subfolder_path

  @subfolder_path.setter
  def subfolder_path(self, value):
    self._subfolder_path = value

  @property
  def tags(self):
    if len(self._tags) == 0:
      return list()
    tag_names = list()
    for tag in self._tags:
      tag_names.append(tag["name"])
    return tag_names

  @property
  def tag_latest(self):
    if self._tag_latest is None:
      return None
    return self._tag_latest["name"]

  @property
  def update_link(self):
    return self._update_link

  @property
  def update_ready(self):
    return self._update_ready

  @property
  def update_version(self):
    return self._update_version

  @property
  def use_releases(self):
    return self._use_releases

  @use_releases.setter
  def use_releases(self, value):
    try:
      self._use_releases = bool(value)
    except:
      raise ValueError("use_releases 必须是布尔值")

  @property
  def user(self):
    return self._user

  @user.setter
  def user(self, value):
    try:
      self._user = str(value)
    except:
      raise ValueError("User 必须是个字符串")

  @property
  def verbose(self):
    return self._verbose

  @verbose.setter
  def verbose(self, value):
    try:
      self._verbose = bool(value)
      self.print_verbose("Verbose 被启用")
    except:
      raise ValueError("Verbose 必须是布尔值")

  @property
  def use_print_traces(self):
    return self._use_print_traces

  @use_print_traces.setter
  def use_print_traces(self, value):
    try:
      self._use_print_traces = bool(value)
    except:
      raise ValueError("use_print_traces 必须是个布尔值")

  @property
  def version_max_update(self):
    return self._version_max_update

  @version_max_update.setter
  def version_max_update(self, value):
    if value is None:
      self._version_max_update = None
      return
    if not isinstance(value, tuple):
      raise ValueError("Version 必须是个元组")
    for subvalue in value:
      if type(subvalue) is not int:
        raise ValueError("Version 的元素必须是个整型")
    self._version_max_update = value

  @property
  def version_min_update(self):
    return self._version_min_update

  @version_min_update.setter
  def version_min_update(self, value):
    if value is None:
      self._version_min_update = None
      return
    if not isinstance(value, tuple):
      raise ValueError("Version 必须是个元组")
    for subvalue in value:
      if type(subvalue) != int:
        raise ValueError("Version 的元素必须是个整型")
    self._version_min_update = value

  @property
  def website(self):
    return self._website

  @website.setter
  def website(self, value):
    if not self.check_is_url(value):
      raise ValueError("非法 URL: " + value)
    self._website = value

  # -------------------------------------------------------------------------
  # Parameter validation related functions
  # -------------------------------------------------------------------------
  @staticmethod
  def check_is_url(url):
    if not ("http://" in url or "https://" in url):
      return False
    if "." not in url:
      return False
    return True

  def _get_tag_names(self):
    tag_names = list()
    self.get_tags()
    for tag in self._tags:
      tag_names.append(tag["name"])
    return tag_names

  def set_check_interval(self,
                         enabled=False,
                         months=0,
                         days=14,
                         hours=0,
                         minutes=0):
    """Set the time interval between automated checks, and if enabled.

        Has enabled = False as default to not check against frequency,
        if enabled, default is 2 weeks.
        """

    if type(enabled) is not bool:
      raise ValueError("Enable 必须是布尔值")
    if type(months) is not int:
      raise ValueError("Months 必须是整形值")
    if type(days) is not int:
      raise ValueError("Days 必须是整形值")
    if type(hours) is not int:
      raise ValueError("Hours 必须是整形值")
    if type(minutes) is not int:
      raise ValueError("Minutes 必须是整形值")

    if not enabled:
      self._check_interval_enabled = False
    else:
      self._check_interval_enabled = True

    self._check_interval_months = months
    self._check_interval_days = days
    self._check_interval_hours = hours
    self._check_interval_minutes = minutes

  def __repr__(self):
    return "<模块更新器 {a}>".format(a=__file__)

  def __str__(self):
    return "更新器, 用户: {a}, 仓库: {b}, 地址: {c}".format(a=self._user,
                                                   b=self._repo,
                                                   c=self.form_repo_url())

  # -------------------------------------------------------------------------
  # API-related functions
  # -------------------------------------------------------------------------
  def form_repo_url(self):
    return self._engine.form_repo_url(self)

  def form_tags_url(self):
    return self._engine.form_tags_url(self)

  def form_branch_url(self, branch):
    return self._engine.form_branch_url(branch, self)

  def get_tags(self):
    request = self.form_tags_url()
    self.print_verbose("从服务器获取标签")

    # get all tags, internet call
    all_tags = self._engine.parse_tags(self.get_api(request), self)
    if all_tags is not None:
      self._prefiltered_tag_count = len(all_tags)
    else:
      self._prefiltered_tag_count = 0
      all_tags = list()

    # pre-process to skip tags
    if self.skip_tag is not None:
      self._tags = [tg for tg in all_tags if not self.skip_tag(self, tg)]
    else:
      self._tags = all_tags

    # get additional branches too, if needed, and place in front
    # Does NO checking here whether branch is valid
    if self._include_branches:
      temp_branches = self._include_branch_list.copy()
      temp_branches.reverse()
      for branch in temp_branches:
        request = self.form_branch_url(branch)
        include = {"name": branch.title(), "zipball_url": request}
        self._tags = [include] + self._tags  # append to front

    if self._tags is None:
      # some error occurred
      self._tag_latest = None
      self._tags = list()

    elif self._prefiltered_tag_count == 0 and not self._include_branches:
      self._tag_latest = None
      if self._error is None:  # if not None, could have had no internet
        self._error = "没有发现发布版"
        self._error_msg = "没有在此仓库发现发布版或者标签"
      self.print_verbose("没有在此仓库发现发布版或者标签")

    elif self._prefiltered_tag_count == 0 and self._include_branches:
      if not self._error:
        self._tag_latest = self._tags[0]
        branch = self._include_branch_list[0]
      self.print_verbose("发现 {} 分支, 没有发布版: {}".format(branch, self._tags[0]))

    elif ((len(self._tags) - len(self._include_branch_list) == 0
           and self._include_branches)
          or (len(self._tags) == 0 and not self._include_branches)
          and self._prefiltered_tag_count > 0):
      self._tag_latest = None
      self._error = "无法获取发布版"
      self._error_msg = "在兼容的版本范围没有发现版本"
      self.print_verbose(self._error_msg)

    else:
      if not self._include_branches:
        self._tag_latest = self._tags[0]
        self.print_verbose("发现最近的标签:" + str(self._tags[0]['name']))
      else:
        # Don't return branch if in list.
        n = len(self._include_branch_list)
        self._tag_latest = self._tags[n]  # guaranteed at least len()=n+1
        self.print_verbose("发现最近的标签:" + str(self._tags[n]['name']))

  def get_raw(self, url):
    """All API calls to base url."""
    request = urllib.request.Request(url)
    try:
      context = ssl._create_unverified_context()
    except:
      # Some blender packaged python versions don't have this, largely
      # useful for local network setups otherwise minimal impact.
      context = None

    # Setup private request headers if appropriate.
    if self._engine.token is not None:
      if self._engine.name == "gitlab":
        request.add_header('PRIVATE-TOKEN', self._engine.token)
      else:
        self.print_verbose("引擎的 Tokens 还没有配置")

    # Always set user agent.
    request.add_header('User-Agent',
                       "Python/" + str(platform.python_version()))

    # Run the request.
    try:
      if context:
        result = urllib.request.urlopen(request, context=context)
      else:
        result = urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
      if str(e.code) == "403":
        self._error = "HTTP 错误 (拒绝访问)"
        self._error_msg = str(e.code) + " - 服务器错误响应"
        print(self._error, self._error_msg)
      else:
        self._error = "HTTP 错误"
        self._error_msg = str(e.code)
        print(self._error, self._error_msg)
      self.print_trace()
      self._update_ready = None
    except urllib.error.URLError as e:
      reason = str(e.reason)
      if "TLSV1_ALERT" in reason or "SSL" in reason.upper():
        self._error = "连接拒绝, 手动下载"
        self._error_msg = reason
        print(self._error, self._error_msg)
      else:
        self._error = "URL 错误, 检查网络连接"
        self._error_msg = reason
        print(self._error, self._error_msg)
      self.print_trace()
      self._update_ready = None
      return None
    else:
      result_string = result.read()
      result.close()
      return result_string.decode()

  def get_api(self, url):
    """Result of all api calls, decoded into json format."""
    get = None
    get = self.get_raw(url)
    if get is not None:
      try:
        return json.JSONDecoder().decode(get)
      except Exception as e:
        self._error = "API 响应为非法的 JSON 格式"
        self._error_msg = str(e.reason)
        self._update_ready = None
        print(self._error, self._error_msg)
        self.print_trace()
        return None
    else:
      return None

  def stage_repository(self, url):
    """Create a working directory and download the new files"""

    local = os.path.join(self._updater_path, "update_staging")
    error = None

    # Make/clear the staging folder, to ensure the folder is always clean.
    self.print_verbose("用于下载的暂存文件夹:\n" + str(local))
    if os.path.isdir(local):
      try:
        shutil.rmtree(local)
        os.makedirs(local)
      except:
        error = "移除存在的暂存文件夹失败"
        self.print_trace()
    else:
      try:
        os.makedirs(local)
      except:
        error = "创建暂存文件夹失败"
        self.print_trace()

    if error is not None:
      self.print_verbose("错误: 中止更新, " + error)
      self._error = "更新中止, 暂存文件夹错误"
      self._error_msg = "错误: {}".format(error)
      return False

    if self._backup_current:
      self.create_backup()

    self.print_verbose("现在取回新的源代码 zip 文件")
    self._source_zip = os.path.join(local, "source.zip")
    self.print_verbose("开始下载更新的 zip 文件")
    try:
      request = urllib.request.Request(url)
      context = ssl._create_unverified_context()

      # Setup private token if appropriate.
      if self._engine.token is not None:
        if self._engine.name == "gitlab":
          request.add_header('PRIVATE-TOKEN', self._engine.token)
        else:
          self.print_verbose("选中的引擎 Tokens 还没有配置")

      # Always set user agent
      request.add_header('User-Agent',
                         "Python/" + str(platform.python_version()))

      self.url_retrieve(urllib.request.urlopen(request, context=context),
                        self._source_zip)
      # Add additional checks on file size being non-zero.
      self.print_verbose("成功下载更新的 zip 文件")
      return True
    except Exception as e:
      self._error = "取回下载发生错误, 错误链接?"
      self._error_msg = "Error: {}".format(e)
      print("取回下载发生错误, 错误链接?")
      print("错误: {}".format(e))
      self.print_trace()
      return False

  def create_backup(self):
    """Save a backup of the current installed addon prior to an update."""
    self.print_verbose("备份当前的插件文件夹")
    local = os.path.join(self._updater_path, "backup")
    tempdest = os.path.join(self._addon_root, os.pardir,
                            self._addon + "_updater_backup_temp")

    self.print_verbose("备份目标路径: " + str(local))

    if os.path.isdir(local):
      try:
        shutil.rmtree(local)
      except:
        self.print_verbose("移除前备份文件夹失败, 继续")
        self.print_trace()

    # Remove the temp folder.
    # Shouldn't exist but could if previously interrupted.
    if os.path.isdir(tempdest):
      try:
        shutil.rmtree(tempdest)
      except:
        self.print_verbose("移除存在的临时文件夹失败, 继续")
        self.print_trace()

    # Make a full addon copy, temporarily placed outside the addon folder.
    if self._backup_ignore_patterns is not None:
      try:
        shutil.copytree(
            self._addon_root,
            tempdest,
            ignore=shutil.ignore_patterns(*self._backup_ignore_patterns))
      except:
        print("移除存在的临时文件夹失败, 仍尝试更新.")
        self.print_trace()
        return
    else:
      try:
        shutil.copytree(self._addon_root, tempdest)
      except:
        print("移除存在的临时文件夹失败, 仍尝试更新.")
        self.print_trace()
        return
    shutil.move(tempdest, local)

    # Save the date for future reference.
    now = datetime.now()
    self._json["backup_date"] = "{m}-{d}-{yr}".format(m=now.strftime("%B"),
                                                      d=now.day,
                                                      yr=now.year)
    self.save_updater_json()

  def restore_backup(self):
    """Restore the last backed up addon version, user initiated only"""
    self.print_verbose("恢复备份, 备份当前插件文件夹")
    backuploc = os.path.join(self._updater_path, "backup")
    tempdest = os.path.join(self._addon_root, os.pardir,
                            self._addon + "_updater_backup_temp")
    tempdest = os.path.abspath(tempdest)

    # Move instead contents back in place, instead of copy.
    shutil.move(backuploc, tempdest)
    shutil.rmtree(self._addon_root)
    os.rename(tempdest, self._addon_root)

    self._json["backup_date"] = ""
    self._json["just_restored"] = True
    self._json["just_updated"] = True
    self.save_updater_json()

    self.reload_addon()

  def unpack_staged_zip(self, clean=False):
    """Unzip the downloaded file, and validate contents"""
    if not os.path.isfile(self._source_zip):
      self.print_verbose("错误, 未发现更新的 zip 文件")
      self._error = "安装错误"
      self._error_msg = "未找到下载的 zip 文件"
      return -1

    # Clear the existing source folder in case previous files remain.
    outdir = os.path.join(self._updater_path, "source")
    try:
      shutil.rmtree(outdir)
      self.print_verbose("源文件夹已被清理")
    except:
      self.print_trace()

    # Create parent directories if needed, would not be relevant unless
    # installing addon into another location or via an addon manager.
    try:
      os.mkdir(outdir)
    except Exception as err:
      print("创建解压文件夹时发生错误:")
      print(str(err))
      self.print_trace()
      self._error = "安装失败"
      self._error_msg = "创建解压文件夹失败"
      return -1

    if not os.path.isdir(outdir):
      print("创建解压文件夹失败")
      self._error = "安装失败"
      self._error_msg = "创建解压文件夹失败"
      return -1

    self.print_verbose("开始从 zip 文件解压源代码:" + str(self._source_zip))
    zfile = zipfile.ZipFile(self._source_zip, "r")

    if not zfile:
      self._error = "安装失败"
      self._error_msg = "目标文件不是 zip 文件, 不能解压"
      self.print_verbose(self._error_msg)
      return -1

    # Now extract directly from the first subfolder (not root)
    # this avoids adding the first subfolder to the path length,
    # which can be too long if the download has the SHA in the name.
    zsep = '/'  # Not using os.sep, always the / value even on windows.
    for name in zfile.namelist():
      if zsep not in name:
        continue
      top_folder = name[:name.index(zsep) + 1]
      if name == top_folder + zsep:
        continue  # skip top level folder
      sub_path = name[name.index(zsep) + 1:]
      if name.endswith(zsep):
        try:
          os.mkdir(os.path.join(outdir, sub_path))
          self.print_verbose("解压 - mkdir: " + os.path.join(outdir, sub_path))
        except OSError as exc:
          if exc.errno != errno.EEXIST:
            self._error = "安装失败"
            self._error_msg = "不能根据 zip 文件创建文件夹"
            self.print_trace()
            return -1
      else:
        with open(os.path.join(outdir, sub_path), "wb") as outfile:
          data = zfile.read(name)
          outfile.write(data)
          self.print_verbose("解压 - create: " + os.path.join(outdir, sub_path))

    self.print_verbose("解压源代码")

    unpath = os.path.join(self._updater_path, "source")
    if not os.path.isdir(unpath):
      self._error = "安装失败"
      self._error_msg = "解压路径不存在"
      print("解压路径不存在 ", unpath)
      return -1

    if self._subfolder_path:
      self._subfolder_path.replace('/', os.path.sep)
      self._subfolder_path.replace('\\', os.path.sep)

    # Either directly in root of zip/one subfolder, or use specified path.
    if not os.path.isfile(os.path.join(unpath, "__init__.py")):
      dirlist = os.listdir(unpath)
      if len(dirlist) > 0:
        if self._subfolder_path == "" or self._subfolder_path is None:
          unpath = os.path.join(unpath, dirlist[0])
        else:
          unpath = os.path.join(unpath, self._subfolder_path)

      # Smarter check for additional sub folders for a single folder
      # containing the __init__.py file.
      if not os.path.isfile(os.path.join(unpath, "__init__.py")):
        print("发现非法插件")
        print("路径:")
        print(dirlist)
        self._error = "安装失败"
        self._error_msg = "没有在新的源代码中发现 __init__ 文件"
        return -1

    # Merge code with the addon directory, using blender default behavior,
    # plus any modifiers indicated by user (e.g. force remove/keep).
    self.deep_merge_directory(self._addon_root, unpath, clean)

    # Now save the json state.
    # Change to True to trigger the handler on other side if allowing
    # reloading within same blender session.
    self._json["just_updated"] = True
    self.save_updater_json()
    self.reload_addon()
    self._update_ready = False
    return 0

  def deep_merge_directory(self, base, merger, clean=False):
    """Merge folder 'merger' into 'base' without deleting existing"""
    if not os.path.exists(base):
      self.print_verbose("基础路径不存在:" + str(base))
      return -1
    elif not os.path.exists(merger):
      self.print_verbose("合并路径不存在")
      return -1

    # Path to be aware of and not overwrite/remove/etc.
    staging_path = os.path.join(self._updater_path, "update_staging")

    # If clean install is enabled, clear existing files ahead of time
    # note: will not delete the update.json, update folder, staging, or
    # staging but will delete all other folders/files in addon directory.
    error = None
    if clean:
      try:
        # Implement clearing of all folders/files, except the updater
        # folder and updater json.
        # Careful, this deletes entire subdirectories recursively...
        # Make sure that base is not a high level shared folder, but
        # is dedicated just to the addon itself.
        self.print_verbose("clean=True, 清理插件目录以刷新安装状态")

        # Remove root files and folders (except update folder).
        files = [
            f for f in os.listdir(base)
            if os.path.isfile(os.path.join(base, f))
        ]
        folders = [
            f for f in os.listdir(base) if os.path.isdir(os.path.join(base, f))
        ]

        for f in files:
          os.remove(os.path.join(base, f))
          self.print_verbose("清理移除的文件 {}".format(os.path.join(base, f)))
        for f in folders:
          if os.path.join(base, f) is self._updater_path:
            continue
          shutil.rmtree(os.path.join(base, f))
          self.print_verbose("清理移除的文件夹和内容 {}".format(os.path.join(base, f)))

      except Exception as err:
        error = "创建清理存在的插件文件夹失败"
        print(error, str(err))
        self.print_trace()

    # Walk through the base addon folder for rules on pre-removing
    # but avoid removing/altering backup and updater file.
    for path, dirs, files in os.walk(base):
      # Prune ie skip updater folder.
      dirs[:] = [
          d for d in dirs if os.path.join(path, d) not in [self._updater_path]
      ]
      for file in files:
        for pattern in self.remove_pre_update_patterns:
          if fnmatch.filter([file], pattern):
            try:
              fl = os.path.join(path, file)
              os.remove(fl)
              self.print_verbose("预删除文件 " + file)
            except OSError:
              print("预删除文件失败 " + file)
              self.print_trace()

    # Walk through the temp addon sub folder for replacements
    # this implements the overwrite rules, which apply after
    # the above pre-removal rules. This also performs the
    # actual file copying/replacements.
    for path, dirs, files in os.walk(merger):
      # Verify structure works to prune updater sub folder overwriting.
      dirs[:] = [
          d for d in dirs if os.path.join(path, d) not in [self._updater_path]
      ]
      rel_path = os.path.relpath(path, merger)
      dest_path = os.path.join(base, rel_path)
      if not os.path.exists(dest_path):
        os.makedirs(dest_path)
      for file in files:
        # Bring in additional logic around copying/replacing.
        # Blender default: overwrite .py's, don't overwrite the rest.
        dest_file = os.path.join(dest_path, file)
        srcFile = os.path.join(path, file)

        # Decide to replace if file already exists, and copy new over.
        if os.path.isfile(dest_file):
          # Otherwise, check each file for overwrite pattern match.
          replaced = False
          for pattern in self._overwrite_patterns:
            if fnmatch.filter([file], pattern):
              replaced = True
              break
          if replaced:
            os.remove(dest_file)
            os.rename(srcFile, dest_file)
            self.print_verbose("重写文件 " + os.path.basename(dest_file))
          else:
            self.print_verbose("格式与 {}, 不匹配, 不进行重写".format(
                os.path.basename(dest_file)))
        else:
          # File did not previously exist, simply move it over.
          os.rename(srcFile, dest_file)
          self.print_verbose("新文件 " + os.path.basename(dest_file))

    # now remove the temp staging folder and downloaded zip
    try:
      shutil.rmtree(staging_path)
    except:
      error = "错误: 移除存在的暂存文件夹失败, 请考虑手动删除 " + staging_path
      self.print_verbose(error)
      self.print_trace()

  def reload_addon(self):
    # if post_update false, skip this function
    # else, unload/reload addon & trigger popup
    if not self._auto_reload_post_update:
      print("启 Blender 以重新加载插件完成更新")
      return

    self.print_verbose("重新加载插件...")
    addon_utils.modules(refresh=True)
    bpy.utils.refresh_script_paths()

    # not allowed in restricted context, such as register module
    # toggle to refresh
    if "addon_disable" in dir(bpy.ops.wm):  # 2.7
      bpy.ops.wm.addon_disable(module=self._addon_package)
      bpy.ops.wm.addon_refresh()
      bpy.ops.wm.addon_enable(module=self._addon_package)
      print("2.7 重载完成")
    else:  # 2.8
      bpy.ops.preferences.addon_disable(module=self._addon_package)
      bpy.ops.preferences.addon_refresh()
      bpy.ops.preferences.addon_enable(module=self._addon_package)
      print("2.8 重载完成")

  # -------------------------------------------------------------------------
  # Other non-api functions and setups
  # -------------------------------------------------------------------------
  def clear_state(self):
    self._update_ready = None
    self._update_link = None
    self._update_version = None
    self._source_zip = None
    self._error = None
    self._error_msg = None

  def url_retrieve(self, url_file, filepath):
    """Custom urlretrieve implementation"""
    chunk = 1024 * 8
    f = open(filepath, "wb")
    while 1:
      data = url_file.read(chunk)
      if not data:
        # print("done.")
        break
      f.write(data)
      # print("Read %s bytes" % len(data))
    f.close()

  def version_tuple_from_text(self, text):
    """Convert text into a tuple of numbers (int).

        Should go through string and remove all non-integers, and for any
        given break split into a different section.
        """
    if text is None:
      return ()

    segments = list()
    tmp = ''
    for char in str(text):
      if not char.isdigit():
        if len(tmp) > 0:
          segments.append(int(tmp))
          tmp = ''
      else:
        tmp += char
    if len(tmp) > 0:
      segments.append(int(tmp))

    if len(segments) == 0:
      self.print_verbose("没有发现的版本字符串文字: " + str(text))
      if not self._include_branches:
        return ()
      else:
        return (text)
    return tuple(segments)

  def check_for_update_async(self, callback=None):
    """Called for running check in a background thread"""
    is_ready = (self._json is not None and "update_ready" in self._json
                and self._json["version_text"] != dict()
                and self._json["update_ready"])

    if is_ready:
      self._update_ready = True
      self._update_link = self._json["version_text"]["link"]
      self._update_version = str(self._json["version_text"]["version"])
      # Cached update.
      callback(True)
      return

    # do the check
    if not self._check_interval_enabled:
      return
    elif self._async_checking:
      self.print_verbose("跳过同步检查, 已经开始")
      # already running the bg thread
    elif self._update_ready is None:
      print("{} 更新器: 运行后台更新检查".format(self.addon))
      self.start_async_check_update(False, callback)

  def check_for_update_now(self, callback=None):
    self._error = None
    self._error_msg = None
    self.print_verbose("已按下 '检查更新', 首先获取当前状态")
    if self._async_checking:
      self.print_verbose("跳过同步检查, 已经开始")
      return  # already running the bg thread
    elif self._update_ready is None:
      self.start_async_check_update(True, callback)
    else:
      self._update_ready = None
      self.start_async_check_update(True, callback)

  def check_for_update(self, now=False):
    """Check for update not in a syncrhonous manner.

        This function is not async, will always return in sequential fashion
        but should have a parent which calls it in another thread.
        """
    self.print_verbose("检查更新函数")

    # clear the errors if any
    self._error = None
    self._error_msg = None

    # avoid running again in, just return past result if found
    # but if force now check, then still do it
    if self._update_ready is not None and not now:
      return (self._update_ready, self._update_version, self._update_link)

    if self._current_version is None:
      raise ValueError("current_version 未定义")

    if self._repo is None:
      raise ValueError("repo 未定义")

    if self._user is None:
      raise ValueError("username 未定义")

    self.set_updater_json()  # self._json

    if not now and not self.past_interval_timestamp():
      self.print_verbose("检查更新中止, 未达到检查更新的间隔")
      return (False, None, None)

    # check if using tags or releases
    # note that if called the first time, this will pull tags from online
    if self._fake_install:
      self.print_verbose("fake_install = True, 设置假版本作为准备")
      self._update_ready = True
      self._update_version = "(999,999,999)"
      self._update_link = "http://127.0.0.1"

      return (self._update_ready, self._update_version, self._update_link)

    # Primary internet call, sets self._tags and self._tag_latest.
    self.get_tags()

    self._json["last_check"] = str(datetime.now())
    self.save_updater_json()

    # Can be () or ('master') in addition to branches, and version tag.
    new_version = self.version_tuple_from_text(self.tag_latest)

    if len(self._tags) == 0:
      self._update_ready = False
      self._update_version = None
      self._update_link = None
      return (False, None, None)

    if not self._include_branches:
      link = self.select_link(self, self._tags[0])
    else:
      n = len(self._include_branch_list)
      if len(self._tags) == n:
        # effectively means no tags found on repo
        # so provide the first one as default
        link = self.select_link(self, self._tags[0])
      else:
        link = self.select_link(self, self._tags[n])

    if new_version == ():
      self._update_ready = False
      self._update_version = None
      self._update_link = None
      return (False, None, None)
    elif str(new_version).lower() in self._include_branch_list:
      # Handle situation where master/whichever branch is included
      # however, this code effectively is not triggered now
      # as new_version will only be tag names, not branch names.
      if not self._include_branch_auto_check:
        # Don't offer update as ready, but set the link for the
        # default branch for installing.
        self._update_ready = False
        self._update_version = new_version
        self._update_link = link
        self.save_updater_json()
        return (True, new_version, link)
      else:
        # Bypass releases and look at timestamp of last update from a
        # branch compared to now, see if commit values match or not.
        raise ValueError("include_branch_autocheck: 未完成部署")

    else:
      # Situation where branches not included.
      if new_version > self._current_version:

        self._update_ready = True
        self._update_version = new_version
        self._update_link = link
        self.save_updater_json()
        return (True, new_version, link)

    # If no update, set ready to False from None to show it was checked.
    self._update_ready = False
    self._update_version = None
    self._update_link = None
    return (False, None, None)

  def set_tag(self, name):
    """Assign the tag name and url to update to"""
    tg = None
    for tag in self._tags:
      if name == tag["name"]:
        tg = tag
        break
    if tg:
      new_version = self.version_tuple_from_text(self.tag_latest)
      self._update_version = new_version
      self._update_link = self.select_link(self, tg)
    elif self._include_branches and name in self._include_branch_list:
      # scenario if reverting to a specific branch name instead of tag
      tg = name
      link = self.form_branch_url(tg)
      self._update_version = name  # this will break things
      self._update_link = link
    if not tg:
      raise ValueError("未发现的版本标签: " + name)

  def run_update(self,
                 force=False,
                 revert_tag=None,
                 clean=False,
                 callback=None):
    """Runs an install, update, or reversion of an addon from online source

        Arguments:
            force: Install assigned link, even if self.update_ready is False
            revert_tag: Version to install, if none uses detected update link
            clean: not used, but in future could use to totally refresh addon
            callback: used to run function on update completion
        """
    self._json["update_ready"] = False
    self._json["ignore"] = False  # clear ignore flag
    self._json["version_text"] = dict()

    if revert_tag is not None:
      self.set_tag(revert_tag)
      self._update_ready = True

    # clear the errors if any
    self._error = None
    self._error_msg = None

    self.print_verbose("运行更新中")

    if self._fake_install:
      # Change to True, to trigger the reload/"update installed" handler.
      self.print_verbose("fake_install=True")
      self.print_verbose("仅重新加载和运行任意句柄触发器")
      self._json["just_updated"] = True
      self.save_updater_json()
      if self._backup_current is True:
        self.create_backup()
      self.reload_addon()
      self._update_ready = False
      res = True  # fake "success" zip download flag

    elif not force:
      if not self._update_ready:
        self.print_verbose("更新停止, 新版本未准备")
        if callback:
          callback(self._addon_package, "更新停止, 新版本未准备")
        return "更新停止, 新版本未准备"
      elif self._update_link is None:
        # this shouldn't happen if update is ready
        self.print_verbose("更新停止, 更新链接不可达")
        if callback:
          callback(self._addon_package, "更新停止, 更新链接不可达")
        return "更新停止, 更新链接不可达"

      if revert_tag is None:
        self.print_verbose("暂存更新")
      else:
        self.print_verbose("暂存安装")

      res = self.stage_repository(self._update_link)
      if not res:
        print("暂存库发生错误: " + str(res))
        if callback is not None:
          callback(self._addon_package, self._error_msg)
        return self._error_msg
      res = self.unpack_staged_zip(clean)
      if res < 0:
        if callback:
          callback(self._addon_package, self._error_msg)
        return res

    else:
      if self._update_link is None:
        self.print_verbose("更新停止, 无法获取链接")
        return "更新停止, 无法获取链接"
      self.print_verbose("强行更新")

      res = self.stage_repository(self._update_link)
      if not res:
        print("暂存库发生错误: " + str(res))
        if callback:
          callback(self._addon_package, self._error_msg)
        return self._error_msg
      res = self.unpack_staged_zip(clean)
      if res < 0:
        return res
      # would need to compare against other versions held in tags

    # run the front-end's callback if provided
    if callback:
      callback(self._addon_package)

    # return something meaningful, 0 means it worked
    return 0

  def past_interval_timestamp(self):
    if not self._check_interval_enabled:
      return True  # ie this exact feature is disabled

    if "last_check" not in self._json or self._json["last_check"] == "":
      return True

    now = datetime.now()
    last_check = datetime.strptime(self._json["last_check"],
                                   "%Y-%m-%d %H:%M:%S.%f")
    offset = timedelta(days=self._check_interval_days +
                       30 * self._check_interval_months,
                       hours=self._check_interval_hours,
                       minutes=self._check_interval_minutes)

    delta = (now - offset) - last_check
    if delta.total_seconds() > 0:
      self.print_verbose("检查更新的时间已到!")
      return True

    self.print_verbose("确认没有到检查更新的时间")
    return False

  def get_json_path(self):
    """Returns the full path to the JSON state file used by this updater.

        Will also rename old file paths to addon-specific path if found.
        """
    json_path = os.path.join(
        self._updater_path,
        "{}_updater_status.json".format(self._addon_package))
    old_json_path = os.path.join(self._updater_path, "updater_status.json")

    # Rename old file if it exists.
    try:
      os.rename(old_json_path, json_path)
    except FileNotFoundError:
      pass
    except Exception as err:
      print("当尝试重命名旧的 JSON 文件发生其他系统错误")
      print(err)
      self.print_trace()
    return json_path

  def set_updater_json(self):
    """Load or initialize JSON dictionary data for updater state"""
    if self._updater_path is None:
      raise ValueError("updater_path 未定义")
    elif not os.path.isdir(self._updater_path):
      os.makedirs(self._updater_path)

    jpath = self.get_json_path()
    if os.path.isfile(jpath):
      with open(jpath) as data_file:
        self._json = json.load(data_file)
        self.print_verbose("从 JSON 文件读取设置")
    else:
      self._json = {
          "last_check": "",
          "backup_date": "",
          "update_ready": False,
          "ignore": False,
          "just_restored": False,
          "just_updated": False,
          "version_text": dict()
      }
      self.save_updater_json()

  def save_updater_json(self):
    """Trigger save of current json structure into file within addon"""
    if self._update_ready:
      if isinstance(self._update_version, tuple):
        self._json["update_ready"] = True
        self._json["version_text"]["link"] = self._update_link
        self._json["version_text"]["version"] = self._update_version
      else:
        self._json["update_ready"] = False
        self._json["version_text"] = dict()
    else:
      self._json["update_ready"] = False
      self._json["version_text"] = dict()

    jpath = self.get_json_path()
    if not os.path.isdir(os.path.dirname(jpath)):
      print("状态错误: 目录不存在, 不能保存 JSON: ", os.path.basename(jpath))
      return
    try:
      with open(jpath, 'w') as outf:
        data_out = json.dumps(self._json, indent=4)
        outf.write(data_out)
    except:
      print("打开/保存 JSON 文件失败: ", jpath)
      self.print_trace()
    self.print_verbose("写入更新器设置到 JSON 文件, 包含内容:")
    self.print_verbose(str(self._json))

  def json_reset_postupdate(self):
    self._json["just_updated"] = False
    self._json["update_ready"] = False
    self._json["version_text"] = dict()
    self.save_updater_json()

  def json_reset_restore(self):
    self._json["just_restored"] = False
    self._json["update_ready"] = False
    self._json["version_text"] = dict()
    self.save_updater_json()
    self._update_ready = None  # Reset so you could check update again.

  def ignore_update(self):
    self._json["ignore"] = True
    self.save_updater_json()

  # -------------------------------------------------------------------------
  # ASYNC related methods
  # -------------------------------------------------------------------------
  def start_async_check_update(self, now=False, callback=None):
    """Start a background thread which will check for updates"""
    if self._async_checking:
      return
    self.print_verbose("开始后台检查线程")
    check_thread = threading.Thread(target=self.async_check_update,
                                    args=(
                                        now,
                                        callback,
                                    ))
    check_thread.daemon = True
    self._check_thread = check_thread
    check_thread.start()

  def async_check_update(self, now, callback=None):
    """Perform update check, run as target of background thread"""
    self._async_checking = True
    self.print_verbose("现在后台检查更新")

    try:
      self.check_for_update(now=now)
    except Exception as exception:
      print("检查更新错误:")
      print(exception)
      self.print_trace()
      if not self._error:
        self._update_ready = False
        self._update_version = None
        self._update_link = None
        self._error = "发生错误"
        self._error_msg = "当检查更新时发生错误"

    self._async_checking = False
    self._check_thread = None

    if callback:
      self.print_verbose("完成更新检查, 回调")
      callback(self._update_ready)
    self.print_verbose("后台线程: 完成更新检查, 不回调")

  def stop_async_check_update(self):
    """Method to give impression of stopping check for update.

        Currently does nothing but allows user to retry/stop blocking UI from
        hitting a refresh button. This does not actually stop the thread, as it
        will complete after the connection timeout regardless. If the thread
        does complete with a successful response, this will be still displayed
        on next UI refresh (ie no update, or update available).
        """
    if self._check_thread is not None:
      self.print_verbose("线程正常结束.")
      # however, "There is no direct kill method on a thread object."
      # better to let it run its course
      # self._check_thread.stop()
    self._async_checking = False
    self._error = None
    self._error_msg = None


# -----------------------------------------------------------------------------
# Updater Engines
# -----------------------------------------------------------------------------


class BitbucketEngine:
  """Integration to Bitbucket API for git-formatted repositories"""
  def __init__(self):
    self.api_url = 'https://api.bitbucket.org'
    self.token = None
    self.name = "bitbucket"

  def form_repo_url(self, updater):
    return "{}/2.0/repositories/{}/{}".format(self.api_url, updater.user,
                                              updater.repo)

  def form_tags_url(self, updater):
    return self.form_repo_url(updater) + "/refs/tags?sort=-name"

  def form_branch_url(self, branch, updater):
    return self.get_zip_url(branch, updater)

  def get_zip_url(self, name, updater):
    return "https://bitbucket.org/{user}/{repo}/get/{name}.zip".format(
        user=updater.user, repo=updater.repo, name=name)

  def parse_tags(self, response, updater):
    if response is None:
      return list()
    return [{
        "name": tag["name"],
        "zipball_url": self.get_zip_url(tag["name"], updater)
    } for tag in response["values"]]


class GithubEngine:
  """Integration to Github API"""
  def __init__(self):
    self.api_url = 'https://api.github.com'
    self.token = None
    self.name = "github"

  def form_repo_url(self, updater):
    return "{}/repos/{}/{}".format(self.api_url, updater.user, updater.repo)

  def form_tags_url(self, updater):
    if updater.use_releases:
      return "{}/releases".format(self.form_repo_url(updater))
    else:
      return "{}/tags".format(self.form_repo_url(updater))

  def form_branch_list_url(self, updater):
    return "{}/branches".format(self.form_repo_url(updater))

  def form_branch_url(self, branch, updater):
    return "{}/zipball/{}".format(self.form_repo_url(updater), branch)

  def parse_tags(self, response, updater):
    if response is None:
      return list()
    return response


class GitlabEngine:
  """Integration to GitLab API"""
  def __init__(self):
    self.api_url = 'https://gitlab.com'
    self.token = None
    self.name = "gitlab"

  def form_repo_url(self, updater):
    return "{}/api/v4/projects/{}".format(self.api_url, updater.repo)

  def form_tags_url(self, updater):
    return "{}/repository/tags".format(self.form_repo_url(updater))

  def form_branch_list_url(self, updater):
    # does not validate branch name.
    return "{}/repository/branches".format(self.form_repo_url(updater))

  def form_branch_url(self, branch, updater):
    # Could clash with tag names and if it does, it will download TAG zip
    # instead of branch zip to get direct path, would need.
    return "{}/repository/archive.zip?sha={}".format(
        self.form_repo_url(updater), branch)

  def get_zip_url(self, sha, updater):
    return "{base}/repository/archive.zip?sha={sha}".format(
        base=self.form_repo_url(updater), sha=sha)

  # def get_commit_zip(self, id, updater):
  # 	return self.form_repo_url(updater)+"/repository/archive.zip?sha:"+id

  def parse_tags(self, response, updater):
    if response is None:
      return list()
    return [{
        "name": tag["name"],
        "zipball_url": self.get_zip_url(tag["commit"]["id"], updater)
    } for tag in response]


# -----------------------------------------------------------------------------
# The module-shared class instance,
# should be what's imported to other files
# -----------------------------------------------------------------------------

Updater = SingletonUpdater()
