
from coroweb import get, post
from models import Content
import logging
import asyncio
import pickle


def findResult_factory(data):
    f = open('./required_data/fields.pkl', 'rb')
    db_fields = pickle.load(f)
    data_result = []
    for d in data:
        d = list(d.values())
        page = d.pop(0)
        content = dict(zip(db_fields, d))
        cul_name = list()
        cul_name.append(content.pop('品种名称'))
        cul_name.append(content.pop('学名'))
        count = 0
        lis = []
        dic = {}
        for k, v in content.items():
            dic.update({k: v})
            count += 1
            if count == 3:
                lis.append(dic)
                dic = {}
                count = 0

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
    if jump:
        i = jump
    i = int(i)
    upbond = i*20
    downbond = upbond-20
    where = "id>%s and id<%s" % (downbond, upbond)
    fields = pickle.load(open('./required_data/all_cul_fields.pkl', 'rb'))
    fields = ', '.join(fields)
    fields = 'id, ' + fields
    sample_data = await Content.find(fields=fields, where=where)
    cul_num = await Content.find_max(field='id')
    cul_num = cul_num[0]['id']
    page_num = cul_num//20
    if (cul_num % 20):
        page_num += 1
    print(sample_data)
    return {
        "__template__": "all_cul_page.html",
        'sample_data': sample_data,
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