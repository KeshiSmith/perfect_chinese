class PC_ModuleInfo:
    def __init__(
        self,
        name="Unkown",
        name_cn = "未命名",
        catagory="未分类",
        author="佚名"
        ):
        self.name = name
        self.name_cn = name_cn
        self.catagory = catagory
        self.author = author

class PC_ModuleInfos:
    def __init__(self):
        self.__data = {}

    def add( self, name):
        self.__data[name] = PC_ModuleInfo(name)
        return self.__data[name]
    
    def remove(self, name):
        del self.__data[name]

    def names(self):
        return self.__data.keys()

    def clear(self):
        self.__data.clear()

    def __getitem__(self, name):
        return self.__data[name]

