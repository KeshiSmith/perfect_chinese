from ..types import PC_Registerable
from ..utils import load_config


class PC_Config(PC_Registerable):
    @classmethod
    def pc_register(cls):
        # 加载配置文件
        load_config()

    @classmethod
    def pc_unregister(cls):
        pass
