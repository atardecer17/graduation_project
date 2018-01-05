'''
包含 连接池，数据库execute函数Select，insert, delete, update
orm映射的基类Model 各种Field如stringfield， floatfield, booleanfield, integerfield, textfield
modelmetaclass
'''

import aiomysql
import asyncio
import logging


def log(sql, args=None):
    logging.info('SQL: [%s] args: %s'%(sql, args or []))

async def create_pool(loop, **kw):
    logging.info('create database connection pool')
    global __pool
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )

# 对数据库进行查询 并根据size返回查询结果
async def select(sql, args, size=None):
    """
    之前用args传入参数始终失败 回头记得再研究一下 args的参数形式到底是怎样的
    :param sql:
    :param args:
    :param size:
    :return:result
    """
    log(sql, args)
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args)
            if size:
                result = await cur.fetchmany(size)
            else:
                result = await cur.fetchall()
        logging.info('rows returned: %s' % len(result))
        return result

# 对数据库进行删除，插入，更新，并返回影响结果行数并自动提交
async def execute(sql, args, autocommit=True):
    log(sql, args)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise e
        return affected


# 定义Field基类
class Field:
    """
    Field 中定义的功能太少了  回头还要再去学学数据库
    """
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


# 定义StringField
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, column_type='varchar(50)'):
        super().__init__(name, column_type, primary_key, default)


# 定义BooleanField
class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


# d定义IntegerField
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


# 定义FloatField
class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


# 定义TextField
class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


def bigdata_handler(attrs, f):
    """用于有大量中文字段时"""
    # 存成映射的字段名 原数据过于杂乱 数据类型全部存为了varchar(50)
    # name 中可以存储其中文字段名, 建立个映射表col
    for i in f:
        if i == 'id':
            attrs[i] = IntegerField(primary_key=True)
            continue
        attrs[i] = StringField()


# 定义modelmetaclass 扫描继承自model的类 并对其类属性进行收集，整理，检查，
# 并添加额外的一些额外的属性到类属性中以便于类中各种数据库操作函数的书写
class Modelmetaclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # 如果创建的类的字段很多则就如此添加
        if name == 'Content':
            bigdata_handler(attrs, db_fields)
        # 在服务器上循环完之后attrs中建的顺序乱掉了？？？？
        tablename = attrs.get('__table__', None)
        logging.info('found model: %s(table: %s)'%(name, tablename))

        mappings = {}         #保存映射关系
        fields = []            #保存所有字段名
        primary_key = None    #保存主键

        for k, v in attrs.copy().items():
            if isinstance(v, Field):
                mappings[k] = attrs.pop(k)
                logging.info('found mapping: %s==>%s'%(k, v))
                if v.primary_key:
                    if primary_key:
                        raise KeyError('Duplicate primary key for field: %s' %k)
                    primary_key = k
                else:
                    fields.append(k)
        if not primary_key:
            raise KeyError('Primary key not found')

        # 类的属性
        fields.insert(0, primary_key)
        attrs['__table__'] = tablename
        attrs['__mappings__'] = mappings
        attrs['__fields__'] = fields
        attrs['__primary_key__'] = primary_key
        # 默认的sql语句
        attrs['__select__'] = 'SELECT * FROM `%s`' %(tablename)
        attrs['__insert__'] = 'INSERT INTO `%s` (%s) VALUES (%s)' %(tablename, ','.join(['`%s`'%x for x in fields]), ','.join(['?' for i in range(len(fields)+1)]))
        attrs['__update__'] = 'UPDTE `%s` SET '
        attrs['__delete__'] = 'DELETE FROM `%s` WHERE `%s`=?'%(tablename, primary_key)
        return type.__new__(cls, name, bases, attrs)


# 所有orm的基类，包含数据库操作的具体函数,
# 查找方法为类方法， 存储更新等为一般的方法
class Model(dict, metaclass=Modelmetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError("'Model' object has no attribute '%s'" % attr)

    def __setattr__(self, attr, value):
        self[attr] = value

    def getValueorDefault(self, k):
        v = getattr(self, k, None)
        if not v:
            field = self.__mappings__[k]
            if field.default:
                v = field.defautl() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s'%(k, v))
                setattr(self, k, v)
        return v

    @classmethod
    async def find(cls, fields=None, where=None, args=None, **kw):
        sql = [cls.__select__]
        if fields:
            sql[0] = sql[0].replace('*', fields)
        if where:
            sql.append('WHERE %s' % where)
        orderby = kw.get('orderby', None)
        if orderby:
            sql.append('ORDERBY %s' % orderby)
        limit = kw.get('limit', None)
        if limit:
            if isinstance(limit, int):
                sql.append('LIMIT ?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('LIMIT ? ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' %str(limit))
        like = kw.get("like", None)
        if like:
            sql.append('LIKE %s' % like)
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    async def find_max(cls, field):
        sql = [cls.__select__]
        sql[0] = sql[0].replace('*', 'MAX(`%s`) as %s' % (field, field))
        rs = await select(' '.join(sql), args=None)
        return [cls(**r) for r in rs]

    def save(self):
        pass
    def update(self):
        pass
    def remove(self):
        pass

# 非动态的后面要出问题 后面要改成动态的  这样的一种生成映射关系的方法感觉还是有点问题 要改
db_fields = ['id'] + ['col_%s' % i for i in range(1, 101)]


