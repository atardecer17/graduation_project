'''
将web中所需的表用model表示出来并一一对应
'''

from orm import Model, StringField, BooleanField, FloatField, IntegerField


class Test(Model):
    __table__ = "test"
    id = IntegerField(name='id', primary_key=True)
    user = StringField(name='user', primary_key=False, default=None)


# 因为表中的字段太多且为中文字段 因此将映射关系放在 '__new__' 中进行读取输入
class Content(Model):
    __table__ = "main"

