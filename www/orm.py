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


# 1	string
# 2	integer
# 3	float
# 4	bool
# 5	text

def bigdata_handler(attrs, f, t):
    """用于有大量中文字段时"""
    for i in range(len(f)):
        if f[i] == 'ID':
            attrs[f[i]] = IntegerField(name=f[i], primary_key=True)
            continue
        if t[i] == 1:
            attrs[f[i]] = StringField(name=f[i])
        if t[i] == 2:
            attrs[f[i]] = IntegerField(name=f[i], default=None)
        if t[i] == 3:
            attrs[f[i]] = FloatField(name=f[i], default=None)
        if t[i] == 4:
            attrs[f[i]] = BooleanField(name=f[i])


# 定义modelmetaclass 扫描继承自model的类 并对其类属性进行收集，整理，检查，
# 并添加额外的一些额外的属性到类属性中以便于类中各种数据库操作函数的书写
class Modelmetaclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # 如果创建的类的字段很多则就如此添加
        if name == 'Content':
            bigdata_handler(attrs, db_fields, db_types)
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


db_fields = ['ID', '品种名称', '学名', '原产地', '保存地', '品种类型',
             '繁殖方式', '染色体倍数', '树型', '树姿', '树高（cm）',
             '树幅（cm）', '最低分枝高度（cm）', '分枝密度', '新梢长度（cm）',
             '节间长（cm）', '着叶数（片）', '叶片着生状态', '新梢生长势',
             '新梢密度', '一芽三叶长（cm）', '一芽三叶百枚重（g）', '芽叶开张状态',
             '芽叶颜色', '芽叶茸毛', '芽叶光泽', '持嫩性', '发芽密度', '发芽整齐度',
             '叶长（cm）', '叶宽（cm）', '叶形指数', '叶片大小', '叶形', '叶色',
             '叶面隆起性', '光泽性', '叶缘', '叶齿锐度', '叶齿密度', '叶齿深度',
             '叶身', '叶片厚度', '叶质', '叶脉粗细', '叶脉对数', '叶尖', '春季萌芽期',
             '春季真叶开展期', '春茶开采期', '年终休止期（月/日）', '花序',
             '始花期（月/日）', '盛花期（月/日）', '终花期（月/日）', '花粉形状',
             '花粉发芽率（%）', '花粉萌发孔数目', '花粉萌发孔类型', '花粉粒表面纹饰',
             '萼片数（片）', '萼片茸毛', '花瓣数目（片）', '花瓣颜色', '花冠大小',
             '花柱长度（mm）', '花柱分裂部位', '花柱分裂数', '子房茸毛', '雌/雄蕊比高',
             '雄蕊数（个）', '花丝长度（mm）', '结实力', '果实室数', '种子成熟期（月/日）',
             '种子形状', '种子色泽', '种子大小', '百粒种子重量（g）', '种子发芽率（%）',
             '扦插发根率（%）', '扦插成活率（%）', '成苗率（%）', '轮产量（kg/轮）',
             '单株产量（kg/株）', '单位面积产量（kg/公顷）', '丰产性', '化学成分（%）',
             '萜烯指数（TI）', '适制性', '制茶品质', '成茶香气', '成茶滋味', '抗寒性',
             '抗旱性', '抗病性', '抗虫性', '中国茶树']

# 1	string
# 2	integer
# 3	float
# 4	bool
# 5	text

db_types = [2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 3, 3, 3, 1, 3, 3, 2, 1, 1, 1, 3, 3, 1, 1, 1, 1, 1,
         1, 1, 3, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1,
         1, 1, 3, 2, 1, 1, 2, 4, 2, 1, 1, 3, 1, 2, 4, 3, 2, 3, 1, 2, 1, 1, 1, 1, 3, 3, 3,
         3, 3, 3, 3, 3, 1, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 4]
