
from coroweb import get, post


@get("/")
def index(request,v_name=None):
    return {
        "__template__": "index.html"
    }