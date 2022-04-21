import re
import json

__escape_pattern = re.compile(r'(\\u.{4}|\\.)')


# 替换转义字符
def __replace_escape_character(text):
  text = text.replace("\\\\u", "\\u")
  return __escape_pattern.sub(
      lambda x: x.group(1).encode("utf-8").decode("unicode-escape"), text)


__quote_pattern = re.compile('"(.*)"', re.S)


# 从 PO 文件加载词典
def load_l10n_dict(popath):
  l10n_dict_zh_CN = {}
  l10n_dict = {"zh_CN": l10n_dict_zh_CN}
  with open(popath, 'r', encoding='utf-8') as file:
    # mode = ('DEFAULT', 'MSGCTXT', 'MSGID' 'MSGSTR')
    mode = 'DEFAULT'
    msgctxt = None
    msgid = ""
    msgstr = ""
    for raw_line in file:
      strip_line = raw_line.strip()
      line = __replace_escape_character(strip_line)
      if line.startswith("msgctxt"):
        mode = 'MSGCTXT'
        msgctxt = __quote_pattern.findall(line)[0]
      elif line.startswith("msgid"):
        mode = 'MSGID'
        msgid = __quote_pattern.findall(line)[0]
      elif line.startswith("msgstr"):
        mode = "MSGSTR"
        msgstr = __quote_pattern.findall(line)[0]
      elif line.startswith("\""):
        text = __quote_pattern.findall(line)[0]
        if mode == 'MSGID':
          msgid = "".join([msgid, text])
        elif mode == 'MSGSTR':
          msgstr = "".join([msgstr, text])
        elif mode == 'MSGCTXT':
          msgctxt = "".join([msgctxt, text])
      elif mode == "MSGSTR":
        mode = 'DEFAULT'
        l10n_dict_zh_CN[(msgctxt, msgid)] = msgstr
        msgctxt = None
    if mode == "MSGSTR":
      mode = 'DEFAULT'
      l10n_dict_zh_CN[(msgctxt, msgid)] = msgstr
      msgctxt = None
  return l10n_dict
