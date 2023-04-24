from bson import BSON
from functools import wraps
import inspect
import requests

from superduperdb import cf
from superduperdb.cluster.annotations import encode_args, encode_kwargs


def use_vector_search(database_type, database_name, table_name, method, args, kwargs):
    bson_ = {
        'database': database_name,
        'database_type': database_type,
        'table': table_name,
        'method': method,
        'args': args,
        'kwargs': {
            **kwargs,
            'remote': False,
        },
    }
    body = BSON.encode(bson_)
    response = requests.post(
        f'http://{cf["model_server"]["host"]}:{cf["model_server"]["port"]}/',
        data=body,
    )
    out = BSON.decode(response.content)
    return out


def vector_search(f):
    sig = inspect.signature(f)
    @wraps(f)
    def vector_search_wrapper(table, *args, remote=None, **kwargs):
        if remote is None:
            remote = table.remote
        if remote:
            args = encode_args(table.database, sig, args)
            kwargs = encode_kwargs(table.database, sig, kwargs)
            out = use_vector_search(
                table.database._database_type,
                table.database.name,
                table.name,
                f.__name__,
                args,
                kwargs,
            )
            return out
        else:
            return f(table, *args, **kwargs, remote=False)
    vector_search_wrapper.signature = sig
    return vector_search_wrapper


def model_server(f):
    """
    Method decorator to posit that function is called on the remote, not on the client.

    :param f: method object
    """

    sig = inspect.signature(f)
    @wraps(f)
    def model_server_wrapper(database, *args, remote=None, **kwargs):
        if remote is None:
            remote = database.remote
        if remote:
            args = encode_args(database, sig, args)
            kwargs = encode_kwargs(database, sig, kwargs)
            out = use_model_server(
                database._database_type,
                database.name,
                f.__name__,
                args,
                kwargs,
            )
            if f.return_convertible:
                out = database.convert_from_bytes_to_types(out)
            return out
        else:
            return f(database, *args, **kwargs, remote=False)
    return model_server_wrapper


def use_model_server(database_type, database_name, method, args, kwargs):
    bson_ = {
        'database_type': database_type,
        'database_name': database_name,
        'method': method,
        'args': args,
        'kwargs': {
            **kwargs,
            'remote': False,
        },
    }
    body = BSON.encode(bson_)
    response = requests.post(
        f'http://{cf["model_server"]["host"]}:{cf["model_server"]["port"]}/',
        data=body,
    )
    out = BSON.decode(response.content)
    return out
