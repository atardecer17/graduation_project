'''
将web中所需的表用model表示出来并一一对应
'''

from orm import Model, StringField, BooleanField, FloatField, IntegerField


class Test(Model):
    __table__ = "test"
    id = IntegerField(name='id', primary_key=True)
    user = StringField(name='user', primary_key=False, default=None)


class Content(Model):
    __table__ = "main"

