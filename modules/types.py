from bpy.utils import register_class, unregister_class

# 自定义注册类
class PC_Registrable():

    @classmethod
    def pc_register(cls):
        register_class(cls)
        
    @classmethod
    def pc_unregister(cls):
        unregister_class(cls)
