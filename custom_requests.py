from dataclasses import dataclass
from functools import cache
import json
from typing import Mapping, MutableMapping
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from oauth_token import Token


class CaseInsensitiveDict(MutableMapping[str, str]):
    def __init__(self, data=None, **kwargs):
        self._store = {}
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key, value):
        # Use the lowercased key for lookups, but store the actual
        # key alongside the value.
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __iter__(self):
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def __len__(self):
        return len(self._store)

    def lower_items(self):
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other):
        if isinstance(other, Mapping):
            return dict(self.lower_items()) == dict(CaseInsensitiveDict(other).lower_items())
        return NotImplemented

    def copy(self):
        return CaseInsensitiveDict(self._store.values())

    def __repr__(self):
        return str(dict(self.items()))

    def __hash__(self):
        return hash(self.lower_items())


@dataclass(unsafe_hash=True)
class Response:
    content: bytes
    status_code: int
    headers: CaseInsensitiveDict
    _text = None

    @property
    def text(self):
        if self._text is None:
            self._text = self.content.decode()
        return self._text

    @cache
    def json(self):
        return json.loads(self.text)


def request(method, url, params=None, data=None, headers=None, token: Token | None = None):
    if method == "GET" and data:
        params = data
        data = None
    if headers is None:
        headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token.access_token}"
    req = Request(
        url + ("?" + urlencode(params) if params else ""),
        data=None if data is None else urlencode(data).encode(),
        headers=headers,
        method=method,
    )
    with urlopen(req) as resp:
        return Response(resp.read(), resp.code, CaseInsensitiveDict(resp.headers))


def get(*args, **kwargs):
    return request("GET", *args, **kwargs)


def post(*args, **kwargs):
    return request("POST", *args, **kwargs)
