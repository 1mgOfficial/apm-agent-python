#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE

from typing import Dict, Iterable, List, Tuple, Union

from sanic import __version__ as version
from sanic.request import Request
from sanic.response import HTTPResponse

from elasticapm.base import Client
from elasticapm.conf import Config, constants
from elasticapm.utils import compat, get_url_dict


def get_env(request: Request) -> Iterable[Tuple[str, str]]:
    for _attr in ("server_name", "server_port", "version"):
        if hasattr(request, _attr):
            yield _attr, getattr(request, _attr)


def extract_header(entity: Union[Request, HTTPResponse], skip_headers: Union[None, List[str]]) -> Dict[str, str]:
    header = dict(entity.headers)
    if skip_headers:
        for _header in skip_headers:
            _ = header.pop(_header, None)
    return header


# noinspection PyBroadException
async def get_request_info(
    config: Config, request: Request, skip_headers: Union[None, List[str]] = None
) -> Dict[str, str]:
    env = dict(get_env(request=request))
    env.update(dict(request.app.config))
    result = {
        "env": env,
        "method": request.method,
        "socket": {
            "remote_address": _get_client_ip(request=request),
            "encrypted": request.scheme in ["https", "wss"],
        },
        "cookies": request.cookies,
    }
    if config.capture_headers:
        result["headers"] = extract_header(entity=request, skip_headers=skip_headers)

    if request.method in constants.HTTP_WITH_BODY and config.capture_body:
        if request.content_type.startswith("multipart") or "octet-stream" in request.content_type:
            result["body"] = "[DISCARDED]"
        try:
            result["body"] = request.body.decode("utf-8")
        except Exception:
            pass

    if "body" not in result:
        result["body"] = "[REDACTED]"
    result["url"] = get_url_dict(request.url)
    return result


async def get_response_info(
    config: Config,
    response: HTTPResponse,
    skip_headers: Union[None, List[str]] = None,
) -> Dict[str, str]:
    result = {
        "cookies": response.cookies,
    }
    if isinstance(response.status, compat.integer_types):
        result["status_code"] = response.status

    if config.capture_headers:
        result["headers"] = extract_header(entity=response, skip_headers=skip_headers)

    if config.capture_body and "octet-stream" not in response.content_type:
        result["body"] = response.body.decode("utf-8")
    else:
        result["body"] = "[REDACTED]"

    return result


def _get_client_ip(request: Request) -> str:
    x_forwarded_for = request.forwarded
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    else:
        if request.socket != (None, None):
            return f"{request.socket[0]}:{request.socket[1]}"
        elif request.ip and request.port:
            return f"{request.ip}:{request.port}"
        return request.remote_addr


def make_client(config: dict, client_cls=Client, **defaults) -> Client:
    if "framework_name" not in defaults:
        defaults["framework_name"] = "sanic"
        defaults["framework_version"] = version

    return client_cls(config, **defaults)
