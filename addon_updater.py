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

import errno
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

# blender imports, used in limited cases
import bpy
import addon_utils

# -----------------------------------------------------------------------------
# Define error messages/notices & hard coded globals
# -----------------------------------------------------------------------------

# currently not used
DEFAULT_TIMEOUT = 10
DEFAULT_PER_PAGE = 30


# -----------------------------------------------------------------------------
# The main class
# -----------------------------------------------------------------------------

class Singleton_updater(object):
    """
    This is the singleton class to reference a copy from,
    it is the shared module level class
    """
    def __init__(self):

        self._engine = GithubEngine()
        self._user = None
        self._repo = None
        self._website = None
        self._current_version = None
        self._subfolder_path = None
        self._tags = []
        self._tag_latest = None
        self._tag_names = []
        self._latest_release = None
        self._use_releases = False
        self._include_branches = False
        self._include_branch_list = ['master']
        self._include_branch_autocheck = False
        self._manual_only = False
        self._version_min_update = None
        self._version_max_update = None

        # by default, backup current addon if new is being loaded
        self._backup_current = True
        self._backup_ignore_patterns = None

        # set patterns for what files to overwrite on update
        self._overwrite_patterns = ["*.py","*.pyc"]
        self._remove_pre_update_patterns = []

        # by default, don't auto enable/disable the addon on update
        # as it is slightly less stable/won't always fully reload module
        self._auto_reload_post_update = False

        # settings relating to frequency and whether to enable auto background check
        self._check_interval_enable = False
        self._check_interval_months = 0
        self._check_interval_days = 7
        self._check_interval_hours = 0
        self._check_interval_minutes = 0

        # runtime variables, initial conditions
        self._verbose = False
        self._fake_install = False
        self._async_checking = False  # only true when async daemon started
        self._update_ready = None
        self._update_link = None
        self._update_version = None
        self._source_zip = None
        self._check_thread = None
        self._select_link = None
        self.skip_tag = None

        # get from module data
        self._addon = __package__.lower()
        self._addon_package = __package__  # must not change
        self._updater_path = os.path.join(os.path.dirname(__file__),
                                        self._addon+"_updater")
        self._addon_root = os.path.dirname(__file__)
        self._json = {}
        self._error = None
        self._error_msg = None
        self._prefiltered_tag_count = 0

        # UI code only, ie not used within this module but still useful
        # properties to have

        # to verify a valid import, in place of placeholder import
        self.showpopups = True # used in UI to show or not show update popups
        self.invalidupdater = False

        # pre-assign basic select-link function
        def select_link_function(self, tag):
            return tag["zipball_url"]

        self._select_link = select_link_function


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
        if self.check_is_url(value) == False:
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
            raise ValueError("必须是布尔值")

    @property
    def backup_current(self):
        return self._backup_current
    @backup_current.setter
    def backup_current(self, value):
        if value == None:
            self._backup_current = False
            return
        else:
            self._backup_current = value

    @property
    def backup_ignore_patterns(self):
        return self._backup_ignore_patterns
    @backup_ignore_patterns.setter
    def backup_ignore_patterns(self, value):
        if value == None:
            self._backup_ignore_patterns = None
            return
        elif type(value) != type(['list']):
            raise ValueError("_backup_ignore_patterns 的类型必须是列表")
        else:
            self._backup_ignore_patterns = value

    @property
    def check_interval(self):
        return (self._check_interval_enable,
                self._check_interval_months,
                self._check_interval_days,
                self._check_interval_hours,
                self._check_interval_minutes)

    @property
    def current_version(self):
        return self._current_version
    @current_version.setter
    def current_version(self, tuple_values):
        if tuple_values==None:
            self._current_version = None
            return
        elif type(tuple_values) is not tuple:
            try:
                tuple(tuple_values)
            except:
                raise ValueError(
                "不是元组! current_version 必须是个整形元组")
        for i in tuple_values:
            if type(i) is not int:
                raise ValueError(
                "不是整形! current_version 必须是个整形元组")
        self._current_version = tuple(tuple_values)

    @property
    def engine(self):
        return self._engine.name
    @engine.setter
    def engine(self, value):
        if value.lower()=="github":
            self._engine = GithubEngine()
        elif value.lower()=="gitlab":
            self._engine = GitlabEngine()
        elif value.lower()=="bitbucket":
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
        if type(value) != type(False):
            raise ValueError("fake_install 必须是个布尔值")
        self._fake_install = bool(value)

    # not currently used
    @property
    def include_branch_autocheck(self):
        return self._include_branch_autocheck
    @include_branch_autocheck.setter
    def include_branch_autocheck(self, value):
        try:
            self._include_branch_autocheck = bool(value)
        except:
            raise ValueError("include_branch_autocheck 必须是个布尔值")

    @property
    def include_branch_list(self):
        return self._include_branch_list
    @include_branch_list.setter
    def include_branch_list(self, value):
        try:
            if value == None:
                self._include_branch_list = ['master']
            elif type(value) != type(['master']) or value==[]:
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
        if self._json == {}:
            self.set_updater_json()
        return self._json

    @property
    def latest_release(self):
        if self._latest_release == None:
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
        if value == None:
            self._overwrite_patterns = ["*.py","*.pyc"]
        elif type(value) != type(['']):
            raise ValueError("overwrite_patterns 需要是列表格式")
        else:
            self._overwrite_patterns = value

    @property
    def private_token(self):
        return self._engine.token
    @private_token.setter
    def private_token(self, value):
        if value==None:
            self._engine.token = None
        else:
            self._engine.token = str(value)

    @property
    def remove_pre_update_patterns(self):
        return self._remove_pre_update_patterns
    @remove_pre_update_patterns.setter
    def remove_pre_update_patterns(self, value):
        if value == None:
            self._remove_pre_update_patterns = []
        elif type(value) != type(['']):
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
        if value == None:
            if self._verbose: print("终止赋值 stage_path, 它是 None")
            return
        elif value != None and not os.path.exists(value):
            try:
                os.makedirs(value)
            except:
                if self._verbose: print("错误尝试 stage_path")
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
        if self._tags == []:
            return []
        tag_names = []
        for tag in self._tags:
            tag_names.append(tag["name"])
        return tag_names

    @property
    def tag_latest(self):
        if self._tag_latest == None:
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
            if self._verbose == True:
                print(self._addon+" 更新器详细信息被启用")
        except:
            raise ValueError("Verbose 必须是布尔值")

    @property
    def version_max_update(self):
        return self._version_max_update
    @version_max_update.setter
    def version_max_update(self, value):
        if value == None:
            self._version_max_update = None
            return
        if type(value) != type((1,2,3)):
            raise ValueError("Version 必须是个元组")
        for subvalue in value:
            if type(subvalue) != int:
                raise ValueError("Version 的元素必须是个整形")
        self._version_max_update = value

    @property
    def version_min_update(self):
        return self._version_min_update
    @version_min_update.setter
    def version_min_update(self, value):
        if value == None:
            self._version_min_update = None
            return
        if type(value) != type((1,2,3)):
            raise ValueError("Version 必须是个元组")
        for subvalue in value:
            if type(subvalue) != int:
                raise ValueError("Version 的元素必须是个整形")
        self._version_min_update = value

    @property
    def website(self):
        return self._website
    @website.setter
    def website(self, value):
        if self.check_is_url(value) == False:
            raise ValueError("非法 URL: " + value)
        self._website = value


    # -------------------------------------------------------------------------
    # Parameter validation related functions
    # -------------------------------------------------------------------------


    def check_is_url(self, url):
        if not ("http://" in url or "https://" in url):
            return False
        if "." not in url:
            return False
        return True

    def get_tag_names(self):
        tag_names = []
        self.get_tags()
        for tag in self._tags:
            tag_names.append(tag["name"])
        return tag_names

    def set_check_interval(self,enable=False,months=0,days=14,hours=0,minutes=0):
        # enabled = False, default initially will not check against frequency
        # if enabled, default is then 2 weeks

        if type(enable) is not bool:
            raise ValueError("Enable 必须是布尔值")
        if type(months) is not int:
            raise ValueError("Months 必须是整形值")
        if type(days) is not int:
            raise ValueError("Days 必须是整形值")
        if type(hours) is not int:
            raise ValueError("Hours 必须是整形值")
        if type(minutes) is not int:
            raise ValueError("Minutes 必须是整形值")

        if enable==False:
            self._check_interval_enable = False
        else:
            self._check_interval_enable = True

        self._check_interval_months = months
        self._check_interval_days = days
        self._check_interval_hours = hours
        self._check_interval_minutes = minutes

    # declare how the class gets printed

    def __repr__(self):
        return "<Module updater from {a}>".format(a=__file__)

    def __str__(self):
        return "Updater, with user: {a}, repository: {b}, url: {c}".format(
                        a=self._user,
                        b=self._repo, c=self.form_repo_url())


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
        if self._verbose: print("从服务器获取标签")

        # get all tags, internet call
        all_tags = self._engine.parse_tags(self.get_api(request), self)
        if all_tags is not None:
            self._prefiltered_tag_count = len(all_tags)
        else:
            self._prefiltered_tag_count = 0
            all_tags = []

        # pre-process to skip tags
        if self.skip_tag != None:
            self._tags = [tg for tg in all_tags if self.skip_tag(self, tg)==False]
        else:
            self._tags = all_tags

        # get additional branches too, if needed, and place in front
        # Does NO checking here whether branch is valid
        if self._include_branches == True:
            temp_branches = self._include_branch_list.copy()
            temp_branches.reverse()
            for branch in temp_branches:
                request = self.form_branch_url(branch)
                include = {
                    "name":branch.title(),
                    "zipball_url":request
                }
                self._tags = [include] + self._tags  # append to front

        if self._tags == None:
            # some error occurred
            self._tag_latest = None
            self._tags = []
            return
        elif self._prefiltered_tag_count == 0 and self._include_branches == False:
            self._tag_latest = None
            if self._error == None: # if not None, could have had no internet
                self._error = "没有发现发布版"
                self._error_msg = "没有在此仓库发现发布版或者标签"
            if self._verbose: print("没有在此仓库发现发布版或者标签")
        elif self._prefiltered_tag_count == 0 and self._include_branches == True:
            if not self._error: self._tag_latest = self._tags[0]
            if self._verbose:
                branch = self._include_branch_list[0]
                print("发现 {} 分支, 没有发布版".format(branch), self._tags[0])
        elif (len(self._tags)-len(self._include_branch_list)==0 and self._include_branches==True) \
                or (len(self._tags)==0 and self._include_branches==False) \
                and self._prefiltered_tag_count > 0:
            self._tag_latest = None
            self._error = "无法获取发布版"
            self._error_msg = "在兼容的版本范围没有发现版本"
            if self._verbose: print("在兼容的版本范围没有发现版本")
        else:
            if self._include_branches == False:
                self._tag_latest = self._tags[0]
                if self._verbose: print("发现最近的标签:",self._tags[0]['name'])
            else:
                # don't return branch if in list
                n = len(self._include_branch_list)
                self._tag_latest = self._tags[n]  # guaranteed at least len()=n+1
                if self._verbose: print("发现最近的标签:",self._tags[n]['name'])


    # all API calls to base url
    def get_raw(self, url):
        # print("Raw request:", url)
        request = urllib.request.Request(url)
        try:
            context = ssl._create_unverified_context()
        except:
            # some blender packaged python versions don't have this, largely
            # useful for local network setups otherwise minimal impact
            context = None

        # setup private request headers if appropriate
        if self._engine.token != None:
            if self._engine.name == "gitlab":
                request.add_header('PRIVATE-TOKEN',self._engine.token)
            else:
                if self._verbose: print("引擎的 Tokens 还没有配置")

        # run the request
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
            self._update_ready = None
            return None
        else:
            result_string = result.read()
            result.close()
            return result_string.decode()


    # result of all api calls, decoded into json format
    def get_api(self, url):
        # return the json version
        get = None
        get = self.get_raw(url)
        if get != None:
            try:
                return json.JSONDecoder().decode(get)
            except Exception as e:
                self._error = "API 响应为非法的 JSON 格式"
                self._error_msg = str(e.reason)
                self._update_ready = None
                print(self._error, self._error_msg)
                return None
        else:
            return None


    # create a working directory and download the new files
    def stage_repository(self, url):

        local = os.path.join(self._updater_path,"update_staging")
        error = None

        # make/clear the staging folder
        # ensure the folder is always "clean"
        if self._verbose: print("用于下载的暂存文件夹:\n",local)
        if os.path.isdir(local) == True:
            try:
                shutil.rmtree(local)
                os.makedirs(local)
            except:
                error = "移除存在的暂存文件夹失败"
        else:
            try:
                os.makedirs(local)
            except:
                error = "创建暂存文件夹失败"

        if error != None:
            if self._verbose: print("错误: 中止更新, "+error)
            self._error = "更新中止, 暂存文件夹错误"
            self._error_msg = "错误: {}".format(error)
            return False

        if self._backup_current==True:
            self.create_backup()
        if self._verbose: print("现在取回新的源代码 zip 文件")

        self._source_zip = os.path.join(local,"source.zip")

        if self._verbose: print("开始下载更新的 zip 文件")
        try:
            request = urllib.request.Request(url)
            context = ssl._create_unverified_context()

            # setup private token if appropriate
            if self._engine.token != None:
                if self._engine.name == "gitlab":
                    request.add_header('PRIVATE-TOKEN',self._engine.token)
                else:
                    if self._verbose: print("选中的引擎 Tokens 还没有配置")
            self.urlretrieve(urllib.request.urlopen(request,context=context), self._source_zip)
            # add additional checks on file size being non-zero
            if self._verbose: print("成功下载更新的 zip 文件")
            return True
        except Exception as e:
            self._error = "取回下载发生错误, 错误链接?"
            self._error_msg = "错误: {}".format(e)
            if self._verbose:
                print("取回下载发生错误, 错误链接?")
                print("错误: {}".format(e))
            return False


    def create_backup(self):
        if self._verbose: print("备份当前的插件文件夹")
        local = os.path.join(self._updater_path,"backup")
        tempdest = os.path.join(self._addon_root,
                        os.pardir,
                        self._addon+"_updater_backup_temp")

        if self._verbose: print("备份目标路径: ",local)

        if os.path.isdir(local):
            try:
                shutil.rmtree(local)
            except:
                if self._verbose:print("移除前备份文件夹失败, 继续")

        # remove the temp folder; shouldn't exist but could if previously interrupted
        if os.path.isdir(tempdest):
            try:
                shutil.rmtree(tempdest)
            except:
                if self._verbose:print("移除存在的临时文件夹失败, 继续")
        # make the full addon copy, which temporarily places outside the addon folder
        if self._backup_ignore_patterns != None:
            shutil.copytree(
                self._addon_root,tempdest,
                ignore=shutil.ignore_patterns(*self._backup_ignore_patterns))
        else:
            shutil.copytree(self._addon_root,tempdest)
        shutil.move(tempdest,local)

        # save the date for future ref
        now = datetime.now()
        self._json["backup_date"] = "{m}-{d}-{yr}".format(
                m=now.strftime("%B"),d=now.day,yr=now.year)
        self.save_updater_json()

    def restore_backup(self):
        if self._verbose: print("恢复备份")

        if self._verbose: print("备份当前插件文件夹")
        backuploc = os.path.join(self._updater_path,"backup")
        tempdest = os.path.join(self._addon_root,
                        os.pardir,
                        self._addon+"_updater_backup_temp")
        tempdest = os.path.abspath(tempdest)

        # make the copy
        shutil.move(backuploc,tempdest)
        shutil.rmtree(self._addon_root)
        os.rename(tempdest,self._addon_root)

        self._json["backup_date"] = ""
        self._json["just_restored"] = True
        self._json["just_updated"] = True
        self.save_updater_json()

        self.reload_addon()

    def unpack_staged_zip(self,clean=False):
        """Unzip the downloaded file, and validate contents"""
        if os.path.isfile(self._source_zip) == False:
            if self._verbose: print("错误, 未发现更新的 zip 文件")
            self._error = "安装错误"
            self._error_msg = "未找到下载的 zip 文件"
            return -1

        # clear the existing source folder in case previous files remain
        outdir = os.path.join(self._updater_path, "source")
        try:
            shutil.rmtree(outdir)
            if self._verbose:
                print("源文件夹已被清理")
        except:
            pass

        # Create parent directories if needed, would not be relevant unless
        # installing addon into another location or via an addon manager
        try:
            os.mkdir(outdir)
        except Exception as err:
            print("创建解压文件夹时发生错误:")
            print(str(err))
            self._error = "安装失败"
            self._error_msg = "创建解压文件夹失败"
            return -1

        if not os.path.isdir(outdir):
            print("创建解压文件夹失败")
            self._error = "安装失败"
            self._error_msg = "创建解压文件夹失败"
            return -1

        if self._verbose:
            print("开始从 zip 文件解压源代码:", self._source_zip)
        zfile = zipfile.ZipFile(self._source_zip, "r")

        if not zfile:
            if self._verbose:
                print("目标文件不是 zip 文件, 不能解压")
            self._error = "安装失败"
            self._error_msg = "目标文件不是 zip 文件, 不能解压"
            return -1

        # Now extract directly from the first subfolder (not root)
        # this avoids adding the first subfolder to the path length,
        # which can be too long if the download has the SHA in the name
        zsep = '/'  #os.sep  # might just always be / even on windows
        for name in zfile.namelist():
            if zsep not in name:
                continue
            top_folder = name[:name.index(zsep)+1]
            if name == top_folder + zsep:
                continue  # skip top level folder
            subpath = name[name.index(zsep)+1:]
            if name.endswith(zsep):
                try:
                    os.mkdir(os.path.join(outdir, subpath))
                    if self._verbose:
                        print("解压 - mkdir: ", os.path.join(outdir, subpath))
                except OSError as exc:
                    if exc.errno != errno.EEXIST:
                        self._error = "安装失败"
                        self._error_msg = "不能根据 zip 文件创建文件夹"
                        return -1
            else:
                with open(os.path.join(outdir, subpath), "wb") as outfile:
                    data = zfile.read(name)
                    outfile.write(data)
                    if self._verbose:
                        print("解压 - create:", os.path.join(outdir, subpath))

        if self._verbose:
            print("解压源代码")

        unpath = os.path.join(self._updater_path, "source")
        if not os.path.isdir(unpath):
            self._error = "安装失败"
            self._error_msg = "解压路径不存在"
            print("解压路径不存在: ", unpath)
            return -1

        if self._subfolder_path:
            self._subfolder_path.replace('/', os.path.sep)
            self._subfolder_path.replace('\\', os.path.sep)

        # either directly in root of zip/one subfolder, or use specified path
        if os.path.isfile(os.path.join(unpath,"__init__.py")) == False:
            dirlist = os.listdir(unpath)
            if len(dirlist)>0:
                if self._subfolder_path == "" or self._subfolder_path == None:
                    unpath = os.path.join(unpath, dirlist[0])
                else:
                    unpath = os.path.join(unpath, self._subfolder_path)

            # smarter check for additional sub folders for a single folder
            # containing __init__.py
            if os.path.isfile(os.path.join(unpath,"__init__.py")) == False:
                if self._verbose:
                    print("发现非法插件")
                    print("路径:")
                    print(dirlist)
                self._error = "安装失败"
                self._error_msg = "没有在新的源代码中发现 __init__ 文件"
                return -1

        # merge code with running addon directory, using blender default behavior
        # plus any modifiers indicated by user (e.g. force remove/keep)
        self.deepMergeDirectory(self._addon_root, unpath, clean)

        # Now save the json state
        #  Change to True, to trigger the handler on other side
        #  if allowing reloading within same blender instance
        self._json["just_updated"] = True
        self.save_updater_json()
        self.reload_addon()
        self._update_ready = False
        return 0


    def deepMergeDirectory(self,base,merger,clean=False):
        """Merge folder 'merger' into folder 'base' without deleting existing"""
        if not os.path.exists(base):
            if self._verbose:
                print("基础路径不存在:", base)
            return -1
        elif not os.path.exists(merger):
            if self._verbose:
                print("合并路径不存在")
            return -1

        # paths to be aware of and not overwrite/remove/etc
        staging_path = os.path.join(self._updater_path,"update_staging")
        backup_path = os.path.join(self._updater_path,"backup")

        # If clean install is enabled, clear existing files ahead of time
        # note: will not delete the update.json, update folder, staging, or staging
        # but will delete all other folders/files in addon directory
        error = None
        if clean==True:
            try:
                # implement clearing of all folders/files, except the
                # updater folder and updater json
                # Careful, this deletes entire subdirectories recursively...
                # make sure that base is not a high level shared folder, but
                # is dedicated just to the addon itself
                if self._verbose: print("clean=True, 清理插件目录以刷新安装状态")

                # remove root files and folders (except update folder)
                files = [f for f in os.listdir(base) if os.path.isfile(os.path.join(base,f))]
                folders = [f for f in os.listdir(base) if os.path.isdir(os.path.join(base,f))]

                for f in files:
                    os.remove(os.path.join(base,f))
                    print("清理移除的文件 {}".format(os.path.join(base,f)))
                for f in folders:
                    if os.path.join(base,f)==self._updater_path: continue
                    shutil.rmtree(os.path.join(base,f))
                    print("清理移除的文件夹和内容 {}".format(os.path.join(base,f)))

            except Exception as err:
                error = "创建清理存在的插件文件夹失败"
                print(error, str(err))

        # Walk through the base addon folder for rules on pre-removing
        # but avoid removing/altering backup and updater file
        for path, dirs, files in os.walk(base):
            # prune ie skip updater folder
            dirs[:] = [d for d in dirs if os.path.join(path,d) not in [self._updater_path]]
            for file in files:
                for ptrn in self.remove_pre_update_patterns:
                    if fnmatch.filter([file],ptrn):
                        try:
                            fl = os.path.join(path,file)
                            os.remove(fl)
                            if self._verbose: print("预删除文件 "+file)
                        except OSError:
                            print("预删除文件失败 "+file)

        # Walk through the temp addon sub folder for replacements
        # this implements the overwrite rules, which apply after
        # the above pre-removal rules. This also performs the
        # actual file copying/replacements
        for path, dirs, files in os.walk(merger):
            # verify this structure works to prune updater sub folder overwriting
            dirs[:] = [d for d in dirs if os.path.join(path,d) not in [self._updater_path]]
            relPath = os.path.relpath(path, merger)
            destPath = os.path.join(base, relPath)
            if not os.path.exists(destPath):
                os.makedirs(destPath)
            for file in files:
                # bring in additional logic around copying/replacing
                # Blender default: overwrite .py's, don't overwrite the rest
                destFile = os.path.join(destPath, file)
                srcFile = os.path.join(path, file)

                # decide whether to replace if file already exists, and copy new over
                if os.path.isfile(destFile):
                    # otherwise, check each file to see if matches an overwrite pattern
                    replaced=False
                    for ptrn in self._overwrite_patterns:
                        if fnmatch.filter([file],ptrn):
                            replaced=True
                            break
                    if replaced:
                        os.remove(destFile)
                        os.rename(srcFile, destFile)
                        if self._verbose: print("重写文件 "+os.path.basename(destFile))
                    else:
                        if self._verbose: print("格式与 "+os.path.basename(destFile)+" 不匹配, 不进行重写")
                else:
                    # file did not previously exist, simply move it over
                    os.rename(srcFile, destFile)
                    if self._verbose: print("新文件 "+os.path.basename(destFile))

        # now remove the temp staging folder and downloaded zip
        try:
            shutil.rmtree(staging_path)
        except:
            error = "错误: 移除存在的暂存文件夹失败, 请考虑手动删除 "+staging_path
            if self._verbose: print(error)


    def reload_addon(self):
        # if post_update false, skip this function
        # else, unload/reload addon & trigger popup
        if self._auto_reload_post_update == False:
            print("重启 Blender 以重新加载插件完成更新")
            return

        if self._verbose: print("重新加载插件...")
        addon_utils.modules(refresh=True)
        bpy.utils.refresh_script_paths()

        # not allowed in restricted context, such as register module
        # toggle to refresh
        bpy.ops.wm.addon_disable(module=self._addon_package)
        bpy.ops.wm.addon_refresh()
        bpy.ops.wm.addon_enable(module=self._addon_package)


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

    # custom urlretrieve implementation
    def urlretrieve(self, urlfile, filepath):
        chunk = 1024*8
        f = open(filepath, "wb")
        while 1:
            data = urlfile.read(chunk)
            if not data:
                #print("done.")
                break
            f.write(data)
            #print("Read %s bytes"%len(data))
        f.close()


    def version_tuple_from_text(self,text):
        if text == None: return ()

        # should go through string and remove all non-integers,
        # and for any given break split into a different section
        segments = []
        tmp = ''
        for l in str(text):
            if l.isdigit()==False:
                if len(tmp)>0:
                    segments.append(int(tmp))
                    tmp = ''
            else:
                tmp+=l
        if len(tmp)>0:
            segments.append(int(tmp))

        if len(segments)==0:
            if self._verbose: print("没有发现的版本字符串文字: ",text)
            if self._include_branches == False:
                return ()
            else:
                return (text)
        return tuple(segments)

    # called for running check in a background thread
    def check_for_update_async(self, callback=None):

        if self._json != None and "update_ready" in self._json and self._json["version_text"]!={}:
            if self._json["update_ready"] == True:
                self._update_ready = True
                self._update_link = self._json["version_text"]["link"]
                self._update_version = str(self._json["version_text"]["version"])
                # cached update
                callback(True)
                return

        # do the check
        if self._check_interval_enable == False:
            return
        elif self._async_checking == True:
            if self._verbose: print("跳过同步检查, 已经开始")
            return  # already running the bg thread
        elif self._update_ready == None:
            self.start_async_check_update(False, callback)


    def check_for_update_now(self, callback=None):

        self._error = None
        self._error_msg = None

        if self._verbose:
            print("已按下 '检查更新', 首先获取当前状态")
        if self._async_checking == True:
            if self._verbose: print("跳过同步检查, 已经开始")
            return  # already running the bg thread
        elif self._update_ready == None:
            self.start_async_check_update(True, callback)
        else:
            self._update_ready = None
            self.start_async_check_update(True, callback)


    # this function is not async, will always return in sequential fashion
    # but should have a parent which calls it in another thread
    def check_for_update(self, now=False):
        if self._verbose: print("检查更新函数")

        # clear the errors if any
        self._error = None
        self._error_msg = None

        # avoid running again in, just return past result if found
        # but if force now check, then still do it
        if self._update_ready != None and now == False:
            return (self._update_ready,self._update_version,self._update_link)

        if self._current_version == None:
            raise ValueError("current_version 未定义")
        if self._repo == None:
            raise ValueError("repo 未定义")
        if self._user == None:
            raise ValueError("username 未定义")

        self.set_updater_json()  # self._json

        if now == False and self.past_interval_timestamp()==False:
            if self._verbose:
                print("检查更新中止, 未达到检查更新的间隔")
            return (False, None, None)

        # check if using tags or releases
        # note that if called the first time, this will pull tags from online
        if self._fake_install == True:
            if self._verbose:
                print("fake_install = True, 设置假版本作为准备")
            self._update_ready = True
            self._update_version = "(999,999,999)"
            self._update_link = "http://127.0.0.1"

            return (self._update_ready, self._update_version, self._update_link)

        # primary internet call
        self.get_tags()  # sets self._tags and self._tag_latest

        self._json["last_check"] = str(datetime.now())
        self.save_updater_json()

        # can be () or ('master') in addition to branches, and version tag
        new_version = self.version_tuple_from_text(self.tag_latest)

        if len(self._tags)==0:
            self._update_ready = False
            self._update_version = None
            self._update_link = None
            return (False, None, None)
        if self._include_branches == False:
            link = self.select_link(self, self._tags[0])
        else:
            n = len(self._include_branch_list)
            if len(self._tags)==n:
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
            # handle situation where master/whichever branch is included
            # however, this code effectively is not triggered now
            # as new_version will only be tag names, not branch names
            if self._include_branch_autocheck == False:
                # don't offer update as ready,
                # but set the link for the default
                # branch for installing
                self._update_ready = False
                self._update_version = new_version
                self._update_link = link
                self.save_updater_json()
                return (True, new_version, link)
            else:
                raise ValueError("include_branch_autocheck: 未完成部署")
                # bypass releases and look at timestamp of last update
                # from a branch compared to now, see if commit values
                # match or not.

        else:
            # situation where branches not included

            if new_version > self._current_version:

                self._update_ready = True
                self._update_version = new_version
                self._update_link = link
                self.save_updater_json()
                return (True, new_version, link)

        # elif new_version != self._current_version:
        #     self._update_ready = False
        #     self._update_version = new_version
        #     self._update_link = link
        #     self.save_updater_json()
        #     return (True, new_version, link)

        # if no update, set ready to False from None
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
            raise ValueError("未发现的版本标签: "+name)


    def run_update(self,force=False,revert_tag=None,clean=False,callback=None):
        """Runs an install, update, or reversion of an addon from online source

        Arguments:
            force: Install assigned link, even if self.update_ready is False
            revert_tag: Version to install, if none uses detected update link
            clean: not used, but in future could use to totally refresh addon
            callback: used to run function on update completion
        """
        self._json["update_ready"] = False
        self._json["ignore"] = False  # clear ignore flag
        self._json["version_text"] = {}

        if revert_tag != None:
            self.set_tag(revert_tag)
            self._update_ready = True

        # clear the errors if any
        self._error = None
        self._error_msg = None

        if self._verbose: print("运行更新中")

        if self._fake_install == True:
            # change to True, to trigger the reload/"update installed" handler
            if self._verbose:
                print("fake_install=True")
                print("仅重新加载和运行任意句柄触发器")
            self._json["just_updated"] = True
            self.save_updater_json()
            if self._backup_current == True:
                self.create_backup()
            self.reload_addon()
            self._update_ready = False
            res = True  # fake "success" zip download flag

        elif force==False:
            if self._update_ready != True:
                if self._verbose:
                    print("更新停止, 新版本未准备")
                if callback:
                    callback(
                        self._addon_package,
                        "更新停止, 新版本未准备")
                return "更新停止, 新版本未准备"
            elif self._update_link == None:
                # this shouldn't happen if update is ready
                if self._verbose:
                    print("更新停止, 更新链接不可达")
                if callback:
                    callback(
                        self._addon_package,
                        "更新停止, 更新链接不可达")
                return "更新停止, 更新链接不可达"

            if self._verbose and revert_tag==None:
                print("暂存更新")
            elif self._verbose:
                print("暂存安装")

            res = self.stage_repository(self._update_link)
            if res !=True:
                print("暂存库发生错误: "+str(res))
                if callback != None:
                    callback(self._addon_package, self._error_msg)
                return self._error_msg
            res = self.unpack_staged_zip(clean)
            if res<0:
                if callback:
                    callback(self._addon_package, self._error_msg)
                return res

        else:
            if self._update_link == None:
                if self._verbose:
                    print("更新停止, 无法获取链接")
                return "更新停止, 无法获取链接"
            if self._verbose:
                print("强行更新")

            res = self.stage_repository(self._update_link)
            if res !=True:
                print("暂存库发生错误: "+str(res))
                if callback:
                    callback(self._addon_package, self._error_msg)
                return self._error_msg
            res = self.unpack_staged_zip(clean)
            if res<0:
                return res
            # would need to compare against other versions held in tags

        # run the front-end's callback if provided
        if callback:
            callback(self._addon_package)

        # return something meaningful, 0 means it worked
        return 0


    def past_interval_timestamp(self):
        if self._check_interval_enable == False:
            return True  # ie this exact feature is disabled

        if "last_check" not in self._json or self._json["last_check"] == "":
            return True
        else:
            now = datetime.now()
            last_check = datetime.strptime(self._json["last_check"],
                                        "%Y-%m-%d %H:%M:%S.%f")
            next_check = last_check
            offset = timedelta(
                days=self._check_interval_days + 30*self._check_interval_months,
                hours=self._check_interval_hours,
                minutes=self._check_interval_minutes
                )

            delta = (now - offset) - last_check
            if delta.total_seconds() > 0:
                if self._verbose:
                    print("{} 更新器: 检查更新时间!".format(self._addon))
                return True
            else:
                if self._verbose:
                    print("{} 更新器: 确认没有到检查更新的时间".format(self._addon))
                return False

    def get_json_path(self):
        """Returns the full path to the JSON state file used by this updater.

        Will also rename old file paths to addon-specific path if found
        """
        json_path = os.path.join(self._updater_path,
            "{}_updater_status.json".format(self._addon_package))
        old_json_path = os.path.join(self._updater_path, "updater_status.json")

        # rename old file if it exists
        try:
            os.rename(old_json_path, json_path)
        except FileNotFoundError:
            pass
        except Exception as err:
            print("当尝试重命名旧的 JSON 文件发生其他系统错误")
            print(err)
        return json_path

    def set_updater_json(self):
        """Load or initialize JSON dictionary data for updater state"""
        if self._updater_path == None:
            raise ValueError("updater_path 未定义")
        elif os.path.isdir(self._updater_path) == False:
            os.makedirs(self._updater_path)

        jpath = self.get_json_path()
        if os.path.isfile(jpath):
            with open(jpath) as data_file:
                self._json = json.load(data_file)
                if self._verbose:
                    print("{} 更新器: 从 JSON 文件读取设置".format(
                        self._addon))
        else:
            # set data structure
            self._json = {
                "last_check":"",
                "backup_date":"",
                "update_ready":False,
                "ignore":False,
                "just_restored":False,
                "just_updated":False,
                "version_text":{}
            }
            self.save_updater_json()


    def save_updater_json(self):
        # first save the state
        if self._update_ready == True:
            if type(self._update_version) == type((0,0,0)):
                self._json["update_ready"] = True
                self._json["version_text"]["link"]=self._update_link
                self._json["version_text"]["version"]=self._update_version
            else:
                self._json["update_ready"] = False
                self._json["version_text"] = {}
        else:
            self._json["update_ready"] = False
            self._json["version_text"] = {}

        jpath = self.get_json_path()
        outf = open(jpath,'w')
        data_out = json.dumps(self._json, indent=4)
        outf.write(data_out)
        outf.close()
        if self._verbose:
            print(self._addon+": 写入更新器设置到 JSON 文件, 包含内容:")
            print(self._json)

    def json_reset_postupdate(self):
        self._json["just_updated"] = False
        self._json["update_ready"] = False
        self._json["version_text"] = {}
        self.save_updater_json()

    def json_reset_restore(self):
        self._json["just_restored"] = False
        self._json["update_ready"] = False
        self._json["version_text"] = {}
        self.save_updater_json()
        self._update_ready = None  # reset so you could check update again

    def ignore_update(self):
        self._json["ignore"] = True
        self.save_updater_json()


    # -------------------------------------------------------------------------
    # ASYNC stuff
    # -------------------------------------------------------------------------

    def start_async_check_update(self, now=False, callback=None):
        """Start a background thread which will check for updates"""
        if self._async_checking is True:
            return
        if self._verbose:
            print("{} 更新器: 开始后台检查线程".format(
                self._addon))
        check_thread = threading.Thread(target=self.async_check_update,
                                        args=(now,callback,))
        check_thread.daemon = True
        self._check_thread = check_thread
        check_thread.start()

    def async_check_update(self, now, callback=None):
        """Perform update check, run as target of background thread"""
        self._async_checking = True
        if self._verbose:
            print("{} 后台线程: 现在后台检查更新".format(
                self._addon))

        try:
            self.check_for_update(now=now)
        except Exception as exception:
            print("检查更新错误:")
            print(exception)
            if not self._error:
                self._update_ready = False
                self._update_version = None
                self._update_link = None
                self._error = "发生错误"
                self._error_msg = "当检查更新时发生错误"

        self._async_checking = False
        self._check_thread = None

        if self._verbose:
            print("{} 后台线程: 完成更新检查, 回调".format(self._addon))
        if callback:
            callback(self._update_ready)

    def stop_async_check_update(self):
        """Method to give impression of stopping check for update.

        Currently does nothing but allows user to retry/stop blocking UI from
        hitting a refresh button. This does not actually stop the thread, as it
        will complete after the connection timeout regardless. If the thread
        does complete with a successful response, this will be still displayed
        on next UI refresh (ie no update, or update available).
        """
        if self._check_thread != None:
            if self._verbose: print("线程正常结束.")
            # however, "There is no direct kill method on a thread object."
            # better to let it run its course
            #self._check_thread.stop()
        self._async_checking = False
        self._error = None
        self._error_msg = None


# -----------------------------------------------------------------------------
# Updater Engines
# -----------------------------------------------------------------------------


class BitbucketEngine(object):
    """Integration to Bitbucket API for git-formatted repositories"""

    def __init__(self):
        self.api_url = 'https://api.bitbucket.org'
        self.token = None
        self.name = "bitbucket"

    def form_repo_url(self, updater):
        return self.api_url+"/2.0/repositories/"+updater.user+"/"+updater.repo

    def form_tags_url(self, updater):
        return self.form_repo_url(updater) + "/refs/tags?sort=-name"

    def form_branch_url(self, branch, updater):
        return self.get_zip_url(branch, updater)

    def get_zip_url(self, name, updater):
        return "https://bitbucket.org/{user}/{repo}/get/{name}.zip".format(
            user=updater.user,
            repo=updater.repo,
            name=name)

    def parse_tags(self, response, updater):
        if response == None:
            return []
        return [{"name": tag["name"], "zipball_url": self.get_zip_url(tag["name"], updater)} for tag in response["values"]]


class GithubEngine(object):
    """Integration to Github API"""

    def __init__(self):
        self.api_url = 'https://api.github.com'
        self.token = None
        self.name = "github"

    def form_repo_url(self, updater):
        return "{}{}{}{}{}".format(self.api_url,"/repos/",updater.user,
                                "/",updater.repo)

    def form_tags_url(self, updater):
        if updater.use_releases:
            return "{}{}".format(self.form_repo_url(updater),"/releases")
        else:
            return "{}{}".format(self.form_repo_url(updater),"/tags")

    def form_branch_list_url(self, updater):
        return "{}{}".format(self.form_repo_url(updater),"/branches")

    def form_branch_url(self, branch, updater):
        return "{}{}{}".format(self.form_repo_url(updater),
                            "/zipball/",branch)

    def parse_tags(self, response, updater):
        if response == None:
            return []
        return response


class GitlabEngine(object):
    """Integration to GitLab API"""

    def __init__(self):
        self.api_url = 'https://gitlab.com'
        self.token = None
        self.name = "gitlab"

    def form_repo_url(self, updater):
        return "{}{}{}".format(self.api_url,"/api/v4/projects/",updater.repo)

    def form_tags_url(self, updater):
        return "{}{}".format(self.form_repo_url(updater),"/repository/tags")

    def form_branch_list_url(self, updater):
        # does not validate branch name.
        return "{}{}".format(
            self.form_repo_url(updater),
            "/repository/branches")

    def form_branch_url(self, branch, updater):
        # Could clash with tag names and if it does, it will
        # download TAG zip instead of branch zip to get
        # direct path, would need.
        return "{}{}{}".format(
            self.form_repo_url(updater),
            "/repository/archive.zip?sha=",
            branch)

    def get_zip_url(self, sha, updater):
        return "{base}/repository/archive.zip?sha={sha}".format(
            base=self.form_repo_url(updater),
            sha=sha)

    # def get_commit_zip(self, id, updater):
    #     return self.form_repo_url(updater)+"/repository/archive.zip?sha:"+id

    def parse_tags(self, response, updater):
        if response == None:
            return []
        return [{"name": tag["name"], "zipball_url": self.get_zip_url(tag["commit"]["id"], updater)} for tag in response]


# -----------------------------------------------------------------------------
# The module-shared class instance,
# should be what's imported to other files
# -----------------------------------------------------------------------------

Updater = Singleton_updater()
