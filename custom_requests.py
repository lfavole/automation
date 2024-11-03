"""A tiny implementation of the core functionalities of the `requests` library."""

import json
import typing
from dataclasses import dataclass
from typing import Mapping, MutableMapping, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if typing.TYPE_CHECKING:
    from oauth_token import Token


class CaseInsensitiveDict(MutableMapping[str, str]):
    """Dict that doesn't matter about the case of the keys."""

    def __init__(self, data=None, **kwargs):
        self._store = {}
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key, value):
        # Use the lowercased key for lookups, but store the actual key alongside the value.
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __iter__(self):
        return (casedkey for casedkey, _ in self._store.values())

    def __len__(self):
        """Length of the dict."""
        return len(self._store)

    def lower_items(self):
        """The dict items with lowercased keys."""
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other):
        if isinstance(other, Mapping):
            return dict(self.lower_items()) == dict(CaseInsensitiveDict(other).lower_items())
        return NotImplemented

    def copy(self):
        """Return a copy of this dict."""
        return CaseInsensitiveDict(self._store.values())

    def __repr__(self):
        return str(dict(self.items()))

    def __hash__(self):
        return hash(self.lower_items())


@dataclass(unsafe_hash=True)
class Response:
    """The response of a request."""

    content: bytes
    status_code: int
    headers: CaseInsensitiveDict
    _text = None
    _json = None

    @property
    def text(self):
        """The text content of the response."""
        if self._text is None:
            self._text = self.content.decode()
        return self._text

    def json(self):
        """Return the JSON-encoded content of the response."""
        if self._json is None:
            self._json = json.loads(self.text)
        return self._json


# Save a reference to json.dumps for the request function (because json is shadowed by a parameter)
dumps = json.dumps


def request(
    method,
    url,
    params=None,
    data=None,
    headers=None,
    token: Optional["Token | str"] = None,
    json=None,  # pylint: disable=W0621
):
    """Make a request."""
    # For GET requests, if data is provided, use it instead of params
    if method == "GET" and data:
        params = data
        data = None
    if headers is None:
        headers = {}
    if token:
        from oauth_token import Token

        headers["Authorization"] = f"Bearer {token.access_token if isinstance(token, Token) else token}"
    if json:
        headers["Content-Type"] = "application/json"
        data = dumps(json)
    req = Request(
        url + ("?" + urlencode(params) if params else ""),
        data=None if data is None else data.encode() if isinstance(data, str) else urlencode(data).encode(),
        headers=headers,
        method=method,
    )
    try:
        with urlopen(req) as resp:
            return Response(resp.read(), resp.code, CaseInsensitiveDict(resp.headers))
    except HTTPError as err:
        # Attach the response to the error (we might need it)
        err.response = Response(err.fp.read(), err.code, err.headers)  # type: ignore
        raise


def get(*args, **kwargs):
    """Make a GET request."""
    return request("GET", *args, **kwargs)


def post(*args, **kwargs):
    """Make a POST request."""
    return request("POST", *args, **kwargs)


def put(*args, **kwargs):
    """Make a PUT request."""
    return request("PUT", *args, **kwargs)


def delete(*args, **kwargs):
    """Make a DELETE request."""
    return request("DELETE", *args, **kwargs)


def get_with_pages(url, params=None, *args, **kwargs):  # pylint: disable=W1113
    """Return paginated data from a Google API."""
    if params is None:
        params = {}

    next_page_token = None
    while True:
        data = get(
            url,
            params={
                **params,
                **({"pageToken": next_page_token} if next_page_token else {}),
            },
            *args,
            **kwargs,
        ).json()

        for value in data.values():
            if isinstance(value, list):
                yield from value

        next_page_token = data.get("nextPageToken")
        if next_page_token is None:
            break
