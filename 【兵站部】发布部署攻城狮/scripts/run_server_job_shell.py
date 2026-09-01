#!/usr/bin/env python3
"""Run a legacy HelloKitty Jenkins job shell on the Jenkins host via SSH.

This is a historical fallback for the old UAT environment. Do not use it as a
default path. Current default is to report the module/job and let the user
manually click Jenkins; use this script only when the user explicitly asks this
window to publish and the target Jenkins host/job has been confirmed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone


MODULE_FLAGS = {
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

ALL_FLAGS = [
    "DEPLOY_MENU",
    "DEPLOY_MEMBER",
    "DEPLOY_ADMIN_CONFIG",
    "DEPLOY_BFF",
    "DEPLOY_ORDER",
    "DEPLOY_PROMOTION",
    "DEPLOY_PAY",
    "DEPLOY_THIRDPARTY",
    "DEPLOY_XXL_JOB",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="uat")
    parser.add_argument("--module", action="append", required=True, choices=sorted(MODULE_FLAGS))
    parser.add_argument("--ssh-host", default="ubuntu@111.229.234.62")
    parser.add_argument("--ssh-key", default="/Users/zhangxinyun/.ssh/hellokitty_test_env_ed25519")
    parser.add_argument("--jenkins-home", default="/opt/hellokitty-park/jenkins_home")
    parser.add_argument("--job", default="hellokitty-park-deploy")
    parser.add_argument("--health-timeout", default="240")
    parser.add_argument("--build-number", default=None)
    parser.add_argument(
        "--build-url",
        default="",
    )
    parser.add_argument("--allow-legacy-uat", action="store_true")
    return parser.parse_args()


def build_remote_env(args: argparse.Namespace) -> dict[str, str]:
    selected = {MODULE_FLAGS[module] for module in args.module}
    build_number = args.build_number
    if not build_number:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        build_number = "codex-" + "-".join(module.replace("_", "-") for module in args.module) + "-" + timestamp

    env = {
        "GIT_BRANCH": args.branch,
        "DEPLOY_ENV": "UAT",
        "APP_HEALTH_WAIT_TIMEOUT": args.health_timeout,
        "BUILD_NUMBER": build_number,
        "BUILD_URL": args.build_url,
    }
    for flag in ALL_FLAGS:
        env[flag] = "true" if flag in selected else "false"
    return env


def main() -> int:
    args = parse_args()
    if not args.allow_legacy_uat:
        raise SystemExit("legacy UAT Jenkins shell is disabled; pass --allow-legacy-uat only for an explicitly confirmed legacy target")
    remote_env = build_remote_env(args)
    remote_payload = {
        "env": remote_env,
        "jenkins_home": args.jenkins_home,
        "job": args.job,
    }
    payload_json = json.dumps(remote_payload)
    remote_code = r'''
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

payload = json.loads(PAYLOAD_JSON)
config = Path(payload["jenkins_home"]) / "jobs" / payload["job"] / "config.xml"
root = ET.fromstring(config.read_text())
command = None
for node in root.iter():
    if node.tag.endswith("command") and node.text:
        command = node.text
        break
if not command:
    raise SystemExit("no Jenkins shell command found in " + str(config))

script_path = Path("/tmp") / (payload["job"] + "-codex-command.sh")
script_path.write_text(command)
script_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

env = os.environ.copy()
env.update(payload["env"])
enabled = sorted(k for k, v in payload["env"].items() if k.startswith("DEPLOY_") and v == "true")
print("Running Jenkins job shell:", payload["job"], "branch=", payload["env"]["GIT_BRANCH"], "enabled=", ",".join(enabled), flush=True)
print("script:", script_path, flush=True)
raise SystemExit(subprocess.run(["bash", str(script_path)], env=env).returncode)
'''.replace("PAYLOAD_JSON", repr(payload_json))
    ssh_command = [
        "ssh",
        "-i",
        args.ssh_key,
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        args.ssh_host,
        "python3",
        "-",
    ]
    result = subprocess.run(ssh_command, input=remote_code, text=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
