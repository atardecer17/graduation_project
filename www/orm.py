'''
包含 连接池，数据库execute函数Select，insert, delete, update
orm映射的基类Model 各种Field如stringfield， floatfield, booleanfield, integerfield, textfield
modelmetaclass
'''

import asyncio, aiomysql
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
    log(sql, args)
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args)
            if size:
                result = await cur.fetchmany(size)
            else:
                result = await cur.fetchall()
        logging.info('rows returned: %s' %len(result))
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
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>'%(self.__class__.__name__, self.column_type, self.name)


# 定义StringField
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, column_type='varchar(100)'):
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

# 定义modelmetaclass 扫描继承自model的类 并对其类属性进行收集，整理，检查，
# 并添加额外的一些额外的属性到类属性中以便于类中各种数据库操作函数的书写
class Modelmetaclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
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
        attrs['__select__'] = 'SELEC * FROM `%s`' %(tablename)
        attrs['__insert__'] = 'INSERT INTO `%s` (%s) VALUES (%s)' %(tablename, ','.join(['`%s`'%x for x in fields]), ','.join(['?' for i in range(len(fields)+1)]))
        attrs['__update__'] = 'UPDTE `%s` SET '
        attrs['__delete__'] = 'DELETE FROM `%s` WHERE `%s`=?'%(tablename, primary_key)


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
    async def find(cls, where=None, args=None, **kw):
        sql = [cls.__select__]
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
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    def save(self):
        pass
    def update(self):
        pass
    def remove(self):
        pass




