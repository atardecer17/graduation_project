'''
web框架 便于handler函数的编写 将request集中处理 构建response对象 对handlers统一添加
'''

import asyncio, os, inspect, logging, functools
from aiohttp import web
from apis import APIError
from urllib import parse


# 定义handler的装饰器，将方法和路径写入函数属性中 便于后面的调用等 这里直接运用偏函数 将method固定即可
def handler(path, method):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = method
        wrapper.__route__ = path
        return wrapper
    return decorator

get = functools.partial(handler, method='GET')
post = functools.partial(handler, method='POST')


# 下面是对request进行处理 (原逻辑巨绕！ 巨绕！ 巨绕！先对视图函数设定的参数进行判断 再对request中的数据进行处理， 下为改后的简易版 逻辑不够之前严谨）
# 从url函数分析其需要接收的函数，从request中获取必要的参数
# 将url函数封装成一个协程
class RequestHandler:
    def __init__(self, func):
        self._func = asyncio.coroutine(func)

    async def __call__(self, request):
        # 获取函数的参数表
        required_args = inspect.signature(self._func).parameters
        logging.info('required args: %s' % required_args)

        # 获取request中的参数值
        kw = {arg: value for arg, value in request.items() if arg in required_args}

        # 获取('/blog/{id}')中的参数值 若无则不添加
        kw.update(request.match_info)

        # 获取get的参数值
        qs = request.query_string
        if qs:
            for k, v in parse.parse_qs(qs, True).items():
                kw.update({k: v[0]})
        # 若有request参数的话将request也加入
        if 'request' in required_args:
            kw['request'] = request
        if hasattr(request, '__data__'):
            kw.update(request.__data__)

        # 检查参数表中的数据
        for key, arg in required_args.items():
            # request 不能为可变长参数
            if key == 'request' and arg.kind in (arg.VAR_POSITIONAL, arg.VAR_KEYWORD):
                return web.HTTPBadRequest(text='request parameter cannot be the var argument')
            if arg.kind not in (arg.VAR_POSITIONAL, arg.VAR_KEYWORD):
                if arg.default == arg.empty and arg.name not in kw:
                    return web.HTTPBadRequest(text='Missing argument %s' % arg.name)

        logging.info('call with args: %s' %kw)
        try:
            return await self._func(**kw)
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


# 添加一个模块的所有路由
def add_routes(app, module_name):
    try:
        mod = __import__(module_name, fromlist=['get_submodule'])
    except ImportError as e:
        raise e
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        func = getattr(mod, attr)
        if callable(func) and hasattr(func, '__method__') and hasattr(func, '__route__'):
            args = ', '.join(inspect.signature(func).parameters.keys())
            logging.info('add route %s %s => %s(%s)'%(func.__method__, func.__route__, func.__name__, args))
            app.router.add_route(func.__method__, func.__route__, RequestHandler(func))


# 添加静态文件路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s==>%s' %('/static/', path))
