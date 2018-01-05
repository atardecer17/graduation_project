import time
import hashlib
import logging
from models import User
import async

_COOKIE_SECR = "nwsuaf"


def user_to_cookie(user, max_age):
    '''
    build cookie string by: id-expires-shal
    :param user:
    :param max_age:
    :return: cookie_str
    '''
    expires = str(int(time.time() + max_age))
    s = "%s-%s-%s-%s" % (user.id, user.passwd, expires, _COOKIE_SECR)
    lis = [user.id, expires, hashlib.sha1(s.encode("utf-8")).hexdigest()]
    cookie_str = "-".join(lis)
    return cookie_str

async def cookie_to_user(cookie_str):
    '''
    parse cookie and load user if cookie is valid
    :param cookie_str:
    :return:user
    '''
    if not cookie_str:
        return None
    try:
        lis = cookie_str.split("-")
        if len(lis) < 3:
            return None
        uid, expires, sha1 = lis
        wh = "`id`=" % uid
        user = await User.find(where=wh)
        if not user:
            return None
        s = "%s-%s-%s-%s" % (user.id, user.passwd, expires, _COOKIE_SECR)
        if sha1 != hashlib.sha1(s.encode("utf-8")).hexdigest():
            logging.info("invalid sha1")
            return None
        user.passwd = "*******"
        return user
    except Exception as e:
        logging.exception(e)
        return None
