from cookie_handler import user_to_cookie
from coroweb import get, post
from models import Content, User
from aiohttp import web
from apis import *
import hashlib
import logging
import asyncio
import pickle

COOKIE_NAME = "nwcookie"
COOKIE_SERC = "nwsuaf"

def findResult_factory(data):
    """
    对SELECT到的数据进行处理
    :param data:
    :return:
    """
    f = open('./required_data/fields.pkl', 'rb')
    db_fields = pickle.load(f)
    data_result = []
    for d in data:
        lis = []
        cul_name = []
        page = d.pop("id")
        for i in range(len(db_fields)):
            col = "col_%s" % str(i+1)
            val = d.get(col, "出错啦")
            lis.append([db_fields[i], val])
        cul_name.append(lis.pop(0)[1])
        cul_name.append(lis.pop(0)[1])
        data_result.append([cul_name, lis, page])
    num = len(data)
    return num, data_result

@get("/")
def homepage():
    return {
        "__template__": "homepage.html"
    }


@get("/detailed/{i}")
async def detailed_page(i):
    data = await Content.find(where="`id`=%s" % i)
    num, result = findResult_factory(data)
    return {
        "__template__": "detailed.html",
        "content": result[0][1],
        "page": result[0][2],
        "cul_name": result[0][0]
    }


@get("/all_cul/{i}")
async def all_cul_page(i, jump=None):
    """
    这个函数里面的一些也可以封装起来 用来后面和高级检索功能的视图函数相复用
    添加where like 之类的应该在orm中的方法中进行改进  以利于代码的复用 这样每个函数都要自己写太麻烦 想一下应该怎么能够适用所有的方法
    :param i:
    :param jump:
    :return:
    """
    if jump:
        i = jump
    i = int(i)
    upbond = i*20
    downbond = upbond-20
    where = "id>%s and id<%s" % (downbond, upbond)
    fields = pickle.load(open('./required_data/all_cul_fields.pkl', 'rb'))
    fields.insert(0, "id")
    field = ', '.join(fields)
    sample_data = await Content.find(fields=field, where=where)
    result_data = []
    for s in sample_data:
        key = fields
        data = []
        for j in range(len(key)):
            data.append([key[j], s[key[j]]])
        result_data.append(data)
    cul_num = await Content.find_max(field='id')
    cul_num = cul_num[0]['id']
    page_num = cul_num//20
    if (cul_num % 20):
        page_num += 1
    return {
        "__template__": "all_cul_page.html",
        'sample_data': result_data,
        'page': i,
        'cul_num': cul_num,
        'page_num': page_num
    }

@post('/')
async def search_name(cul_name):
    where = "`col_1`"
    like = "\'%{}%\'" .format(cul_name)
    data = await Content.find(where=where, like=like)
    if not data:
        no_result = "对不起，未找到和%s有关的数据" % (cul_name)
        return {
            "__template__": "homepage.html",
            "no_result": no_result
        }
    print(data)
    num, result = findResult_factory(data)
    return{
        "__template__": "search_result.html",
        "result": result,
        "num": num
    }

@post("/api/user/login")
async def login(username, passwd):
    if not username or not passwd:
        raise APIValueError("username or passwd", "Invalid username or Invalid passwd")
    wh = "`username`=`%s`" % username
    user = await User.find(where=wh)
    if not user:
        raise APIValueError("username", "username not exist")
    user = user[0]
    # check passwd
    sha1 = hashlib.sha1()
    sha1.update(passwd)
    if user.passwd != sha1.hexdigest():
        raise APIValueError("passwd", "Invalid passwd")
    # set cookie
    r = web.Response()
    cookie_str = user_to_cookie(user, max_age=54000)
    r.set_cookie(COOKIE_NAME, cookie_str, max_age=54000, httponly=True)
    user.passwd = "*******"
    r.content_type = "application/json"
    r.body = json.dump(user, ensure_ascii=False).encode("utf-8")
    return r


