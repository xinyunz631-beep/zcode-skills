#!/usr/bin/env python3
"""Trigger and wait for a HelloKitty Jenkins deployment job.

The old UAT runtime is no longer the default target. Do not use this helper
unless the user explicitly asks this window to publish through Jenkins and the
target Jenkins URL has been confirmed for the current production release.
"""

from __future__ import annotations

import argparse
import base64
import http.cookiejar
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_JENKINS_URL = ""
DEFAULT_JOB = "hellokitty-park-deploy"
KNOWN_MODULE_PARAMS = {
    "menu": "DEPLOY_MENU",
    "member": "DEPLOY_MEMBER",
    "admin-config": "DEPLOY_ADMIN_CONFIG",
    "admin_config": "DEPLOY_ADMIN_CONFIG",
    "bff": "DEPLOY_BFF",
    "order": "DEPLOY_ORDER",
    "promotion": "DEPLOY_PROMOTION",
    "pay": "DEPLOY_PAY",
    "thirdparty": "DEPLOY_THIRDPARTY",
    "third-party": "DEPLOY_THIRDPARTY",
    "xxl-job": "DEPLOY_XXL_JOB",
    "xxl_job": "DEPLOY_XXL_JOB",
    "xxljob": "DEPLOY_XXL_JOB",
}


class JenkinsError(RuntimeError):
    pass


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_credentials(args: argparse.Namespace) -> tuple[str | None, str | None]:
    file_values: dict[str, str] = {}
    if args.credentials_file:
        cred_path = Path(args.credentials_file).expanduser()
        if not cred_path.exists():
            raise JenkinsError(f"Credentials file not found: {cred_path}")
        file_values = load_env_file(cred_path)

    user = args.user or os.getenv("JENKINS_USER") or file_values.get("JENKINS_USER") or file_values.get("username")
    password = os.getenv(args.password_env) if args.password_env else None
    password = (
        password
        or os.getenv("JENKINS_PASSWORD")
        or os.getenv("JENKINS_API_TOKEN")
        or file_values.get("JENKINS_PASSWORD")
        or file_values.get("JENKINS_API_TOKEN")
        or file_values.get("apiToken")
        or file_values.get("api_token")
        or file_values.get("token")
        or file_values.get("password")
    )
    return user, password


def request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    basic_auth: tuple[str, str] | None = None,
    method: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
    req_headers = dict(headers or {})
    if data is not None:
        req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    if basic_auth:
        token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode("utf-8")).decode("ascii")
        req_headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with opener.open(req, timeout=30) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def json_request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    basic_auth: tuple[str, str] | None = None,
) -> tuple[int, dict[str, str], dict]:
    status, headers, body = request(opener, url, basic_auth=basic_auth)
    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except json.JSONDecodeError as exc:
        raise JenkinsError(f"Expected JSON from {url}, got HTTP {status}") from exc
    return status, headers, payload


def login_form(opener: urllib.request.OpenerDirector, base_url: str, user: str, password: str) -> None:
    login_url = f"{base_url}/j_spring_security_check"
    status, _, _ = request(
        opener,
        login_url,
        data={
            "j_username": user,
            "j_password": password,
            "from": f"{base_url}/",
            "Submit": "Sign in",
        },
    )
    if status not in {200, 302, 303}:
        raise JenkinsError(f"Jenkins form login failed with HTTP {status}")


def get_crumb(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    basic_auth: tuple[str, str] | None,
) -> dict[str, str]:
    status, _, payload = json_request(opener, f"{base_url}/crumbIssuer/api/json", basic_auth=basic_auth)
    if status == 404:
        return {}
    if status != 200:
        raise JenkinsError(f"Could not fetch Jenkins crumb: HTTP {status}")
    field = payload.get("crumbRequestField")
    crumb = payload.get("crumb")
    return {str(field): str(crumb)} if field and crumb else {}


def build_params(args: argparse.Namespace) -> dict[str, str]:
    params = {"GIT_BRANCH": args.branch}
    selected = {KNOWN_MODULE_PARAMS[module] for module in args.module}
    for param in sorted(set(KNOWN_MODULE_PARAMS.values())):
        params[param] = "true" if param in selected else "false"
    for extra in args.extra_param:
        if "=" not in extra:
            raise JenkinsError(f"--extra-param must be KEY=VALUE, got: {extra}")
        key, value = extra.split("=", 1)
        params[key] = value
    return params


def trigger_build(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    job: str,
    params: dict[str, str],
    headers: dict[str, str],
    basic_auth: tuple[str, str] | None,
) -> str:
    url = f"{base_url}/job/{urllib.parse.quote(job)}/buildWithParameters"
    status, response_headers, body = request(opener, url, data=params, headers=headers, basic_auth=basic_auth, method="POST")
    if status not in {200, 201, 202, 302, 303}:
        detail = body.decode("utf-8", errors="replace")[:300].replace("\n", " ")
        raise JenkinsError(f"Build trigger failed with HTTP {status}: {detail}")
    queue_url = response_headers.get("Location") or response_headers.get("location")
    if not queue_url:
        raise JenkinsError("Build trigger did not return a Jenkins queue URL")
    return queue_url.rstrip("/")


def wait_for_build(
    opener: urllib.request.OpenerDirector,
    queue_url: str,
    basic_auth: tuple[str, str] | None,
    timeout_seconds: int,
) -> tuple[str, int, str]:
    deadline = time.time() + timeout_seconds
    executable_url = None
    while time.time() < deadline:
        status, _, payload = json_request(opener, f"{queue_url}/api/json", basic_auth=basic_auth)
        if status != 200:
            raise JenkinsError(f"Queue polling failed with HTTP {status}")
        executable = payload.get("executable")
        if executable and executable.get("url") and executable.get("number"):
            executable_url = str(executable["url"]).rstrip("/")
            build_number = int(executable["number"])
            break
        why = payload.get("why") or "waiting for executor"
        print(f"queue: {why}")
        time.sleep(5)
    else:
        raise JenkinsError("Timed out waiting for Jenkins queue to start a build")

    while time.time() < deadline:
        status, _, payload = json_request(opener, f"{executable_url}/api/json", basic_auth=basic_auth)
        if status != 200:
            raise JenkinsError(f"Build polling failed with HTTP {status}")
        if not payload.get("building"):
            result = str(payload.get("result") or "UNKNOWN")
            return executable_url, build_number, result
        print(f"build #{build_number}: running")
        time.sleep(10)

    raise JenkinsError("Timed out waiting for Jenkins build to finish")


def verify_url(url: str, insecure: bool) -> None:
    handlers: list[urllib.request.BaseHandler] = []
    if insecure:
        context = ssl._create_unverified_context()
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    status, _, body = request(opener, url)
    snippet = body.decode("utf-8", errors="replace")[:200].replace("\n", " ")
    print(f"verify: {url} -> HTTP {status} {snippet}")
    if status >= 500:
        raise JenkinsError(f"Verification URL returned HTTP {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default="/Users/zhangxinyun/Documents/HelloKitty乐园后端项目")
    parser.add_argument("--jenkins-url", default=DEFAULT_JENKINS_URL, required=True)
    parser.add_argument("--job", default=DEFAULT_JOB)
    parser.add_argument("--branch", default="uat")
    parser.add_argument("--module", action="append", required=True, choices=sorted(KNOWN_MODULE_PARAMS))
    parser.add_argument("--extra-param", action="append", default=[])
    parser.add_argument("--credentials-file")
    parser.add_argument("--user")
    parser.add_argument("--password-env")
    parser.add_argument("--basic-auth", action="store_true", help="Use HTTP Basic auth instead of Jenkins form login")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification for Jenkins")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--verify-url", action="append", default=[])
    args = parser.parse_args()

    project_root = Path(args.project_root)
    if not project_root.exists():
        raise JenkinsError(f"Project root not found: {project_root}")

    user, password = read_credentials(args)
    if not user or not password:
        raise JenkinsError("Missing Jenkins credentials. Set JENKINS_USER/JENKINS_PASSWORD or pass --credentials-file.")

    base_url = args.jenkins_url.rstrip("/")
    cookie_jar = http.cookiejar.CookieJar()
    handlers: list[urllib.request.BaseHandler] = [urllib.request.HTTPCookieProcessor(cookie_jar)]
    if args.insecure:
        context = ssl._create_unverified_context()
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    basic_auth = (user, password) if args.basic_auth else None

    if not args.basic_auth:
        login_form(opener, base_url, user, password)

    status, _, _ = json_request(opener, f"{base_url}/job/{urllib.parse.quote(args.job)}/api/json", basic_auth=basic_auth)
    if status != 200:
        raise JenkinsError(f"Jenkins job API not accessible after login: HTTP {status}")

    headers = get_crumb(opener, base_url, basic_auth)
    params = build_params(args)
    print(f"trigger: job={args.job} branch={args.branch} modules={','.join(args.module)}")
    queue_url = trigger_build(opener, base_url, args.job, params, headers, basic_auth)
    print(f"queue: {queue_url}")

    build_url, build_number, result = wait_for_build(opener, queue_url, basic_auth, args.timeout_seconds)
    print(f"build: #{build_number} {result} {build_url}")
    if result != "SUCCESS":
        return 2

    for url in args.verify_url:
        verify_url(url, args.insecure)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JenkinsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
