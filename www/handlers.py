
from coroweb import get, post
from models import Content
import logging
import asyncio
import pickle


def findResult_factory(data):
    """
    对SELECT到的数据进行处理

    将字典中的数据搞成三个三个分组有点蠢 直接在模板中用两个for循环嵌套不就好了  jinja2中也支持 for i in range(val)

    :param data: 通过SELECT获取到的数据 列表中嵌套字典的形式
    :return: 返回找到的数据数目以及数据的详细信息 将品种名称和学名单独从字典拿出来 然后和其他数据共同组成一个列表，然后将字典中的数据三个三个分组
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
    logging.info(data_result)
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