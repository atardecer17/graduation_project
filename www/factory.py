import logging
import async
import json
from aiohttp import web
from cookie_handler import cookie_to_user

# middleware改变URL的输入、输出，甚至可以决定不继续处理而直接返回。
# middleware的用处就在于把通用的功能从每个URL处理函数中拿出来，集中放到一个地方。
# 还没搞懂middleware是如何调用的, middleware 即从一开始从前往后调用 相当于装饰器对handler进行装饰

# 记录URL日志
async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' %(request.method, request.path))
        return await handler(request)
    return logger

# 处理post数据
async def postdata_factory(app, handler):
    async def parse_data(request):
        if request.method == "POST":
            if request.content_type.startswith("application/json"):
                request.__data__ = await request.json()
                logging.info("request json: %s " % str(request.__data__))
            if request.content_type.startswith("application/x-www-form-urlencoded"):
                data = await request.post()
                request.__data__ = dict(**data)
                logging.info("request form: %s" % str(request.__data__))
        return await handler(request)
    return parse_data

# 先调用handler 再将结果进行处理后返回response对象
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler......')
        # 目前只用模板作为返回对象 先只用字典
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        template = r.get('__template__')
        # 关于body中模板的调用有点不理解！！
        if template:
            resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        # 如果没有template json.dumps()中各参数的意义不太明确！！！
        else:
            resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
            resp.content_type = 'application/json;charset=utf-8'
            return resp
    return response

COOKIE_NAME = "nwcookie"
# 验证cookie
async def auth_factory(app, handler):
    async def auth(request):
        logging.info("check user: %s %s" % request.method, request.path)
        request.__user__ = None
        cookie_str = request.cookie.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie_to_user(cookie_str)
            if user:
                logging.info("set current user: " % user.username)
                request.__user__ = user
        return await handler(request)
    return auth
