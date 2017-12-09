import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from aiohttp import web
from jinja2 import Environment, FileSystemLoader

from config import configs

import orm
from coroweb import add_routes, add_static


# jinja2初始化
def init_jinja2(app, **kw):
    logging.info('init jinja2.....')
    options = {
        'autoescape': kw.get('autoescape', True),
        'block_start_string': kw.get('block_start_string', '{%'),
        'block_end_string': kw.get('block_end_string', '%}'),
        'variable_start_string': kw.get('variable_start_string', '{{'),
        'variable_end_string': kw.get('variable_end_string', '}}'),
        'auto_reload': kw.get('auto_reload', True)
    }
    path = kw.get('path', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters:
        for name, ftr in filters.items():
            env.filters[name] = ftr
    app['__templating__'] = env

# middleware改变URL的输入、输出，甚至可以决定不继续处理而直接返回。
# middleware的用处就在于把通用的功能从每个URL处理函数中拿出来，集中放到一个地方。
# 还没搞懂middleware是如何调用的, middleware 即从一开始从后往前调用 相当于装饰器对handler进行装饰

# 记录URL日志
async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' %(request.method, request.path))
        return await handler(request)
    return logger

# 先调用handler 再将结果进行处理后返回response对象
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler......')
        # 规定将handler的返回值确定为字典类 不行！
        r = await handler(request)
        template = r.get('__template__')
        # 关于body中模板的调用有点不理解！！
        if template:
            resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        # 如果没有template json.dumps()中各参数的意义不太明确！！！
        else:
            resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o:o.__dict__).encode('utf-8'))
            resp.content_type = 'application/json;charset=utf-8'
            return resp
    return response


# 对post的不同数据格式进行处理
async def data_factory(app, handler):
    pass


async def init(loop):
    await orm.create_pool(loop=loop, **configs['db'])
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app)
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()


