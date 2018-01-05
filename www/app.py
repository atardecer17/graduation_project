import logging; logging.basicConfig(level=logging.INFO)
import asyncio
import os
from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from config import configs
import orm
from coroweb import add_routes, add_static
from factory import logger_factory, postdata_factory, response_factory


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


async def init(loop):
    await orm.create_pool(loop=loop, **configs['db'])
    app = web.Application(loop=loop, middlewares=[
        logger_factory, postdata_factory, response_factory
    ])
    init_jinja2(app)
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9002)
    logging.info('server started at http://127.0.0.1:9000')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()