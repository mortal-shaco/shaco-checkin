#!/usr/bin/env python3
# coding: utf-8
# name: 青龙备份与阿里云盘签到
# cron: 11 1 * * *
# SPDX-License-Identifier: MIT
"""
项目名称: AKA-Cigma / qinglong-backup
Author: AKA-Cigma
原项目功能：自动备份青龙基本文件至阿里云盘并执行阿里云盘签到。

维护说明：本文件基于原项目的 MIT 许可维护，保留原作者署名与项目归属。
维护版不依赖 aligo 或其他仓库，使用 Python 标准库直接访问阿里云盘接口。
"""

from __future__ import annotations
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('75d5dd21e205ec36', 'scripts/qinglong_backup.py', 'qinglong_backup.py', 'qinglong_backup')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


TASK_NAME = "青龙备份与阿里云盘签到"
CATALOG_ID = "75d5dd21e205ec36"
SCRIPT_NAME = "candidate.py"
ARCHIVE_RE = re.compile(r"^qinglong_\d{8}_\d{6}(?:_\d+| \(\d+\))?\.tar\.gz$")
DEFAULT_EXCLUDES = ["log", "syslog", ".git", ".github", "node_modules", "backups", ".pnpm-store"]
DEFAULT_TIMEOUT = 20
MAX_JSON_BYTES = 2 * 1024 * 1024
PART_SIZE = 64 * 1024 * 1024


class ConfigError(Exception):
    pass


class TaskError(Exception):
    pass


class ApiError(TaskError):
    pass


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def clock_text() -> str:
    return datetime.now().strftime("%H:%M:%S")


def elapsed_text(started: float) -> str:
    return f"{time.monotonic() - started:.2f}s"


def json_line(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def looks_like_phone_number(value: str) -> bool:
    digits = re.sub(r"[^0-9]", "", value)
    compact = re.sub(r"[\s()+.-]", "", value)
    return compact.isdigit() and 7 <= len(digits) <= 15


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} 只能使用 1/0、true/false、yes/no 或 on/off")


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是整数") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def split_values(raw: str) -> List[str]:
    return [item.strip() for item in re.split(r"[,;\s]+", raw) if item.strip()]


def parse_excludes(raw: Optional[str]) -> List[str]:
    if not raw or not raw.strip():
        return list(DEFAULT_EXCLUDES)
    text = raw.strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError("QLBK_EXCLUDE_NAMES 的 JSON 格式无效") from exc
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ConfigError("QLBK_EXCLUDE_NAMES 的 JSON 值必须是字符串数组")
        values = [item.strip() for item in parsed if item.strip()]
    else:
        values = split_values(text)
    for value in values:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ConfigError("QLBK_EXCLUDE_NAMES 只能包含顶层目录名")
    return values


def parse_remote_path(raw: str) -> List[str]:
    normalized = raw.strip().strip("/")
    if not normalized:
        return []
    parts = [part.strip() for part in normalized.split("/")]
    if any(not part or part in {".", ".."} for part in parts):
        raise ConfigError("QLBK_UPLOAD_PATH 必须是安全的云盘相对目录")
    return parts


def resolve_backup_dir(source_dir: Path, raw: str, allow_external: bool) -> Path:
    if source_dir == Path(source_dir.anchor):
        raise ConfigError("QLBK_SOURCE_PATH 不得指向文件系统根目录")
    configured = Path(raw).expanduser()
    target = configured.resolve() if configured.is_absolute() else (source_dir / configured).resolve()
    if target == source_dir:
        raise ConfigError("QLBK_BACKUPS_PATH 不能等于备份源目录")
    if not allow_external:
        try:
            target.relative_to(source_dir)
        except ValueError as exc:
            raise ConfigError(
                "QLBK_BACKUPS_PATH 默认必须位于备份源目录内；如确需外部路径，请显式设置 QLBK_ALLOW_EXTERNAL_BACKUP_PATH=1"
            ) from exc
    return target


def load_tokens() -> Tuple[List[str], str]:
    aliases = ["ALIYUNDRIVE_REFRESH_TOKEN", "ALI_REFRESH_TOKEN", "ALIYUN_TOKEN"]
    selected = next(((name, os.getenv(name, "")) for name in aliases if os.getenv(name, "").strip()), None)
    if selected is None:
        raise ConfigError("缺少必需变量 ALIYUNDRIVE_REFRESH_TOKEN（每行填写一个账号的 refresh_token）")
    name, raw = selected
    tokens: List[str] = []
    seen = set()
    for line in raw.splitlines():
        token = line.strip()
        if not token or token in seen:
            continue
        if any(character.isspace() for character in token):
            raise ConfigError(f"{name} 的每个非空行必须只包含一个 refresh_token")
        seen.add(token)
        tokens.append(token)
    if not tokens:
        raise ConfigError(f"{name} 未包含有效账号")
    return tokens, name


def parse_actions() -> List[str]:
    raw = os.getenv("QLBK_ACTIONS")
    if raw and raw.strip():
        actions = split_values(raw.lower())
    else:
        actions = ["backup"]
        if env_bool("EXEC_SIGN_IN", True):
            actions.append("sign_in")
    allowed = {"backup", "sign_in"}
    unknown = sorted(set(actions) - allowed)
    if unknown:
        raise ConfigError(f"QLBK_ACTIONS 含不支持的动作：{', '.join(unknown)}")
    unique = [name for name in ("sign_in", "backup") if name in actions]
    if not unique:
        raise ConfigError("QLBK_ACTIONS 至少需要包含 backup 或 sign_in")
    return unique


@dataclass
class Settings:
    dry_run: bool
    timeout: int
    source_dir: Path
    backup_dir: Path
    remote_parts: List[str]
    local_max: int
    cloud_max: int
    excludes: List[str]
    actions: List[str]
    tokens: List[str]
    credential_env: str

    @classmethod
    def from_env(cls) -> "Settings":
        dry_run = env_bool("QLBK_DRY_RUN", False)
        timeout = env_int("QLBK_HTTP_TIMEOUT", DEFAULT_TIMEOUT, 3, 120)
        source_default = "/ql/data" if Path("/ql/data").is_dir() else "/ql"
        source_dir = Path(os.getenv("QLBK_SOURCE_PATH", source_default)).expanduser().resolve()
        if not dry_run and (not source_dir.exists() or not source_dir.is_dir()):
            raise ConfigError(f"备份源目录不存在或不是目录：{source_dir}")
        allow_external = env_bool("QLBK_ALLOW_EXTERNAL_BACKUP_PATH", False)
        backup_dir = resolve_backup_dir(source_dir, os.getenv("QLBK_BACKUPS_PATH", "backups"), allow_external)
        remote_parts = parse_remote_path(os.getenv("QLBK_UPLOAD_PATH", "backups"))
        local_max = env_int("QLBK_MAX_FLIES", 5, 1, 10000)
        cloud_max = env_int("QLBK_CLOUD_MAX_FLIES", 100, 1, 10000)
        if cloud_max < local_max:
            raise ConfigError("QLBK_CLOUD_MAX_FLIES 必须大于或等于 QLBK_MAX_FLIES，维护版不会静默改写配置")
        tokens, credential_env = load_tokens()
        return cls(
            dry_run=dry_run,
            timeout=timeout,
            source_dir=source_dir,
            backup_dir=backup_dir,
            remote_parts=remote_parts,
            local_max=local_max,
            cloud_max=cloud_max,
            excludes=parse_excludes(os.getenv("QLBK_EXCLUDE_NAMES")),
            actions=parse_actions(),
            tokens=tokens,
            credential_env=credential_env,
        )


@dataclass
class Counters:
    total: int = 0
    success: int = 0
    already: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "total": self.total,
            "success": self.success,
            "alreadyComplete": self.already,
            "skipped": self.skipped,
            "failed": self.failed,
        }


@dataclass
class AccountResult:
    index: int
    identity: str
    ok: bool
    counters: Counters
    duration_seconds: float
    messages: List[str] = field(default_factory=list)


class Timeline:
    def banner(self, mode: str, account_count: int) -> None:
        print("=" * 60)
        print(f"{TASK_NAME}")
        print(f"开始时间: {now_text()}")
        print(f"运行模式: {mode}")
        print(f"账号数量: {account_count}")
        print("=" * 60)

    def stage(self, account: str, number: int, title: str, message: str, icon: str = "⏭️") -> None:
        print(f"[{clock_text()}] [{account}] 阶段 {number} - {title}: {icon} {message}")

    def account_stats(self, result: AccountResult) -> None:
        values = result.counters
        print(
            f"[{clock_text()}] [账号{result.index}] 统计: 总任务={values.total} 成功={values.success} "
            f"已完成={values.already} 跳过={values.skipped} 失败={values.failed} 耗时={result.duration_seconds:.2f}s"
        )


class AliyunDriveClient:
    AUTH_URL = "https://auth.aliyundrive.com/v2/account/token"
    API_ROOT = "https://api.aliyundrive.com"
    MEMBER_ROOT = "https://member.aliyundrive.com"

    def __init__(self, refresh_token: str, timeout: int):
        self._refresh_token = refresh_token
        self.timeout = timeout
        self.access_token = ""
        self.drive_id = ""
        self.identity = ""

    def _json_request(
        self,
        url: str,
        body: Optional[Dict[str, Any]] = None,
        method: str = "POST",
        authenticated: bool = True,
    ) -> Dict[str, Any]:
        headers = {"Accept": "application/json", "User-Agent": "qinglong-backup-maintained/1.0"}
        if authenticated:
            if not self.access_token:
                raise ApiError("认证状态无效")
            headers["Authorization"] = f"Bearer {self.access_token}"
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_JSON_BYTES + 1)
                status = response.status
        except urllib.error.HTTPError as exc:
            raise ApiError(f"HTTP 请求失败（状态码 {exc.code}）") from None
        except urllib.error.URLError as exc:
            reason = exc.reason.__class__.__name__ if getattr(exc, "reason", None) is not None else "网络错误"
            raise ApiError(f"网络请求失败（{reason}）") from None
        except TimeoutError:
            raise ApiError("网络请求超时") from None
        if not 200 <= status < 300:
            raise ApiError(f"HTTP 请求失败（状态码 {status}）")
        if len(raw) > MAX_JSON_BYTES:
            raise ApiError("接口响应超过安全大小限制")
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError("接口返回了无效 JSON") from None
        if not isinstance(value, dict):
            raise ApiError("接口返回格式不符合预期")
        if value.get("success") is False or value.get("code") not in (None, "", "Success"):
            code = str(value.get("code") or "business-error")[:80]
            raise ApiError(f"接口业务校验失败（{code}）")
        return value

    def authenticate(self) -> str:
        response = self._json_request(
            self.AUTH_URL,
            {"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            authenticated=False,
        )
        access_token = response.get("access_token")
        drive_id = response.get("default_drive_id") or response.get("resource_drive_id")
        if not isinstance(access_token, str) or not access_token or not isinstance(drive_id, str) or not drive_id:
            raise ApiError("登录响应缺少 access_token 或 drive_id")
        self.access_token = access_token
        self.drive_id = drive_id
        for key in ("nick_name", "user_name", "display_name", "user_id"):
            value = response.get(key)
            if isinstance(value, str) and value.strip() and not looks_like_phone_number(value.strip()):
                self.identity = value.strip()
                break
        return self.identity

    def sign_in(self) -> int:
        query = urllib.parse.urlencode({"_rx-s": "mobile"})
        response = self._json_request(
            f"{self.MEMBER_ROOT}/v1/activity/sign_in_list?{query}",
            {"isReward": True},
        )
        result = response.get("result")
        count = result.get("signInCount") if isinstance(result, dict) else None
        if not isinstance(count, int) or count < 0:
            raise ApiError("签到响应缺少有效的 signInCount，无法确认业务成功")
        return count

    def list_files(self, parent_file_id: str) -> List[Dict[str, Any]]:
        marker = ""
        items: List[Dict[str, Any]] = []
        while True:
            body: Dict[str, Any] = {
                "drive_id": self.drive_id,
                "parent_file_id": parent_file_id,
                "limit": 100,
                "all": False,
                "order_by": "name",
                "order_direction": "DESC",
            }
            if marker:
                body["marker"] = marker
            response = self._json_request(f"{self.API_ROOT}/adrive/v3/file/list", body)
            page = response.get("items")
            if not isinstance(page, list):
                raise ApiError("文件列表响应缺少 items")
            items.extend(item for item in page if isinstance(item, dict))
            next_marker = response.get("next_marker")
            if not isinstance(next_marker, str) or not next_marker:
                break
            marker = next_marker
        return items

    def ensure_folder(self, parts: Iterable[str]) -> str:
        parent = "root"
        for name in parts:
            matches = [item for item in self.list_files(parent) if item.get("name") == name]
            folder = next((item for item in matches if item.get("type") == "folder"), None)
            if folder is None and matches:
                raise ApiError(f"云盘路径节点“{name}”已被同名文件占用")
            if folder is None:
                folder = self._json_request(
                    f"{self.API_ROOT}/adrive/v2/file/createWithFolders",
                    {
                        "drive_id": self.drive_id,
                        "parent_file_id": parent,
                        "name": name,
                        "type": "folder",
                        "check_name_mode": "refuse",
                    },
                )
            file_id = folder.get("file_id")
            if not isinstance(file_id, str) or not file_id:
                raise ApiError("创建或读取云盘目录后未获得 file_id")
            parent = file_id
        return parent

    def upload_file(self, source: Path, parent_file_id: str) -> Tuple[str, int]:
        size = source.stat().st_size
        if size <= 0:
            raise TaskError("备份文件为空，拒绝上传")
        part_count = (size + PART_SIZE - 1) // PART_SIZE
        part_info = [{"part_number": number} for number in range(1, part_count + 1)]
        created = self._json_request(
            f"{self.API_ROOT}/adrive/v2/file/createWithFolders",
            {
                "drive_id": self.drive_id,
                "parent_file_id": parent_file_id,
                "name": source.name,
                "type": "file",
                "check_name_mode": "auto_rename",
                "size": size,
                "part_info_list": part_info,
            },
        )
        file_id = created.get("file_id")
        upload_id = created.get("upload_id")
        rapid_upload = created.get("rapid_upload") is True
        returned_parts = created.get("part_info_list")
        if not isinstance(file_id, str) or not file_id:
            raise ApiError("创建云盘上传任务后未获得 file_id")
        if not rapid_upload:
            if not isinstance(upload_id, str) or not upload_id or not isinstance(returned_parts, list):
                raise ApiError("创建云盘上传任务后未获得 upload_id 或分片地址")
            ordered = sorted(
                (part for part in returned_parts if isinstance(part, dict)),
                key=lambda part: part.get("part_number", 0),
            )
            if len(ordered) != part_count:
                raise ApiError("云盘返回的上传分片数量不完整")
            with source.open("rb") as handle:
                for expected, part in enumerate(ordered, start=1):
                    upload_url = part.get("upload_url")
                    if part.get("part_number") != expected or not isinstance(upload_url, str) or not upload_url.startswith("https://"):
                        raise ApiError("云盘返回了无效的上传分片信息")
                    chunk = handle.read(PART_SIZE)
                    request = urllib.request.Request(
                        upload_url,
                        data=chunk,
                        headers={"Content-Type": "application/octet-stream"},
                        method="PUT",
                    )
                    try:
                        with urllib.request.urlopen(request, timeout=self.timeout) as response:
                            response.read(1024)
                            status = response.status
                    except urllib.error.HTTPError as exc:
                        raise ApiError(f"上传分片失败（状态码 {exc.code}）") from None
                    except urllib.error.URLError as exc:
                        reason = exc.reason.__class__.__name__ if getattr(exc, "reason", None) is not None else "网络错误"
                        raise ApiError(f"上传分片网络失败（{reason}）") from None
                    except TimeoutError:
                        raise ApiError("上传分片超时") from None
                    if not 200 <= status < 300:
                        raise ApiError(f"上传分片失败（状态码 {status}）")
            completed = self._json_request(
                f"{self.API_ROOT}/v2/file/complete",
                {"drive_id": self.drive_id, "file_id": file_id, "upload_id": upload_id},
            )
        else:
            completed = created
        completed_id = completed.get("file_id")
        completed_name = completed.get("name")
        completed_size = completed.get("size", size)
        if completed_id != file_id or not isinstance(completed_name, str) or not completed_name:
            raise ApiError("上传完成响应缺少可验证的文件标识或名称")
        if isinstance(completed_size, int) and completed_size != size:
            raise ApiError("上传完成响应中的文件大小与本地备份不一致")
        return completed_name, size

    def trash_file(self, file_id: str) -> None:
        if not file_id:
            raise ApiError("待清理云盘文件缺少 file_id")
        self._json_request(
            f"{self.API_ROOT}/v2/recyclebin/trash",
            {"drive_id": self.drive_id, "file_id": file_id},
        )


def archive_candidates(directory: Path) -> List[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.iterdir() if path.is_file() and ARCHIVE_RE.fullmatch(path.name)),
        key=lambda path: (path.stat().st_mtime, path.name),
    )


def make_archive(settings: Settings) -> Path:
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = settings.backup_dir / f"qinglong_{stamp}.tar.gz"
    suffix = 1
    while destination.exists():
        destination = settings.backup_dir / f"qinglong_{stamp}_{suffix}.tar.gz"
        suffix += 1
    temporary = destination.with_name(destination.name + ".part")
    excludes = set(settings.excludes)
    try:
        try:
            relative_backup = settings.backup_dir.relative_to(settings.source_dir)
            if relative_backup.parts:
                excludes.add(relative_backup.parts[0])
        except ValueError:
            pass
        with tarfile.open(temporary, "w:gz", dereference=False) as archive:
            for child in sorted(settings.source_dir.iterdir(), key=lambda path: path.name):
                if child.name in excludes or not child.is_dir():
                    continue
                archive.add(child, arcname=child.name, recursive=True)
        if temporary.stat().st_size <= 0:
            raise TaskError("生成的备份文件为空")
        temporary.replace(destination)
        return destination
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def prune_local(directory: Path, maximum: int) -> int:
    candidates = archive_candidates(directory)
    remove_count = max(0, len(candidates) - maximum)
    for path in candidates[:remove_count]:
        path.unlink()
    return remove_count


def cloud_archives(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matches = [
        item
        for item in items
        if item.get("type") == "file" and isinstance(item.get("name"), str) and ARCHIVE_RE.fullmatch(item["name"])
    ]
    return sorted(matches, key=lambda item: (str(item.get("created_at") or item.get("updated_at") or ""), item["name"]))


def notify_selection_enabled() -> Tuple[bool, str]:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in {"0", "false", "no", "off"}:
        return False, "QINGLONG_NOTIFY 已关闭"
    if switch not in {"", "auto", "1", "true", "yes", "on"}:
        return False, "QINGLONG_NOTIFY 值无效"
    selectors_raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selectors_raw is None:
        return True, "默认通知列表"
    selectors = split_values(selectors_raw)
    if not selectors:
        return False, "QINGLONG_NOTIFY_SCRIPTS 为空，按策略关闭全部通知"
    names = [CATALOG_ID, SCRIPT_NAME, "output/candidate.py"]
    matched = any(selector == "*" or any(fnmatch.fnmatch(name, selector) for name in names) for selector in selectors)
    return matched, "脚本选择器匹配" if matched else "脚本选择器未匹配"


def load_notify_path(path: Path):
    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
    if spec is None or spec.loader is None:
        raise ImportError("无法加载通知模块")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "send")


def send_notification(title: str, body: str, dry_run: bool) -> Tuple[str, str]:
    enabled, reason = notify_selection_enabled()
    if not enabled:
        return "disabled", reason
    if dry_run:
        return "skipped", "dry-run 为保证完全断网未调用通知通道"
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send")
        sender(title, body)
        return "sent", "已通过 notify.send 发送"
    except Exception:
        pass
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    python_paths = []
    javascript_paths = []
    if notify_dir:
        python_paths.append(Path(notify_dir) / "notify.py")
        javascript_paths.append(Path(notify_dir) / "sendNotify.js")
    python_paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    javascript_paths.extend([Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")])
    for path in python_paths:
        if not path.is_file():
            continue
        try:
            sender = load_notify_path(path)
            sender(title, body)
            return "sent", f"已通过 {path.name} 发送"
        except Exception:
            continue
    node = shutil.which("node")
    if node:
        javascript = (
            "const m=require(process.argv[1]);const f=m.sendNotify||m;"
            "Promise.resolve(f(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
        )
        for path in javascript_paths:
            if not path.is_file():
                continue
            try:
                result = subprocess.run(
                    [node, "-e", javascript, str(path), title, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    return "sent", f"已通过 {path.name} 发送"
            except (OSError, subprocess.SubprocessError):
                continue
    return "unavailable", "未找到可用通知模块或通知发送失败"


def account_label(index: int, identity: str = "") -> str:
    return f"账号{index}" + (f"（{identity}）" if identity else "")


def run_dry_account(index: int, settings: Settings, timeline: Timeline) -> AccountResult:
    started = time.monotonic()
    counters = Counters()
    label = account_label(index)
    stage_number = 1
    counters.total += 1
    counters.skipped += 1
    timeline.stage(label, stage_number, "认证检查", "已校验凭据占位格式；断网预演不发起认证", "⏭️")
    stage_number += 1
    if "sign_in" in settings.actions:
        counters.total += 1
        counters.skipped += 1
        timeline.stage(label, stage_number, "阿里云盘签到", "计划调用签到接口并校验 signInCount", "⏭️")
        stage_number += 1
    if "backup" in settings.actions:
        counters.total += 1
        counters.skipped += 1
        timeline.stage(label, stage_number, "备份上传", f"计划上传到 /{'/'.join(settings.remote_parts) or ''}", "⏭️")
        stage_number += 1
        counters.total += 1
        counters.skipped += 1
        timeline.stage(label, stage_number, "云端保留数清理", f"仅计划保留最新 {settings.cloud_max} 个规范备份", "⏭️")
    result = AccountResult(index, "", True, counters, time.monotonic() - started, ["断网预演通过"])
    timeline.account_stats(result)
    return result


def run_live_account(
    index: int,
    token: str,
    settings: Settings,
    archive_path: Optional[Path],
    timeline: Timeline,
) -> AccountResult:
    started = time.monotonic()
    counters = Counters()
    messages: List[str] = []
    client = AliyunDriveClient(token, settings.timeout)
    identity = ""
    label = account_label(index)
    stage_number = 1
    counters.total += 1
    try:
        identity = client.authenticate()
        label = account_label(index, identity)
        counters.success += 1
        timeline.stage(label, stage_number, "账号认证", "认证成功" + (f"，官方身份：{identity}" if identity else ""), "✅")
    except Exception as exc:
        counters.failed += 1
        message = str(exc) if isinstance(exc, (ApiError, TaskError)) else exc.__class__.__name__
        messages.append(f"账号认证失败：{message}")
        timeline.stage(label, stage_number, "账号认证", message, "❌")
        stage_number += 1
        if "sign_in" in settings.actions:
            counters.total += 1
            counters.skipped += 1
            timeline.stage(label, stage_number, "阿里云盘签到", "账号认证失败，安全跳过", "⏭️")
            stage_number += 1
        if "backup" in settings.actions:
            counters.total += 2
            counters.skipped += 2
            timeline.stage(label, stage_number, "备份上传", "账号认证失败，安全跳过", "⏭️")
            stage_number += 1
            timeline.stage(label, stage_number, "云端保留数清理", "账号认证失败，安全跳过", "⏭️")
        result = AccountResult(index, identity, False, counters, time.monotonic() - started, messages)
        timeline.account_stats(result)
        return result
    stage_number += 1

    if "sign_in" in settings.actions:
        counters.total += 1
        stage_started = time.monotonic()
        try:
            count = client.sign_in()
            counters.success += 1
            messages.append(f"本月签到次数 {count}")
            timeline.stage(label, stage_number, "阿里云盘签到", f"业务校验成功，本月签到次数 {count}，耗时 {elapsed_text(stage_started)}", "✅")
        except Exception as exc:
            counters.failed += 1
            message = str(exc) if isinstance(exc, (ApiError, TaskError)) else exc.__class__.__name__
            messages.append(f"签到失败：{message}")
            timeline.stage(label, stage_number, "阿里云盘签到", f"{message}，耗时 {elapsed_text(stage_started)}", "❌")
        stage_number += 1

    if "backup" in settings.actions:
        counters.total += 1
        stage_started = time.monotonic()
        remote_folder_id = ""
        if archive_path is None:
            counters.failed += 1
            messages.append("本地备份未生成，未执行上传")
            timeline.stage(label, stage_number, "备份上传", "本地备份未生成，未执行上传", "❌")
        else:
            try:
                remote_folder_id = client.ensure_folder(settings.remote_parts)
                uploaded_name, uploaded_size = client.upload_file(archive_path, remote_folder_id)
                counters.success += 1
                messages.append(f"已上传 {uploaded_name}（{uploaded_size} 字节）")
                timeline.stage(
                    label,
                    stage_number,
                    "备份上传",
                    f"已验证上传 {uploaded_name}（{uploaded_size} 字节），耗时 {elapsed_text(stage_started)}",
                    "✅",
                )
            except Exception as exc:
                counters.failed += 1
                message = str(exc) if isinstance(exc, (ApiError, TaskError, OSError)) else exc.__class__.__name__
                messages.append(f"上传失败：{message}")
                timeline.stage(label, stage_number, "备份上传", f"{message}，耗时 {elapsed_text(stage_started)}", "❌")
        stage_number += 1
        counters.total += 1
        stage_started = time.monotonic()
        if not remote_folder_id:
            counters.skipped += 1
            timeline.stage(label, stage_number, "云端保留数清理", "上传未成功，安全跳过云端清理", "⏭️")
        else:
            try:
                candidates = cloud_archives(client.list_files(remote_folder_id))
                remove_count = max(0, len(candidates) - settings.cloud_max)
                for item in candidates[:remove_count]:
                    client.trash_file(str(item.get("file_id") or ""))
                if remove_count:
                    counters.success += 1
                    timeline.stage(label, stage_number, "云端保留数清理", f"已移入回收站 {remove_count} 个旧备份，耗时 {elapsed_text(stage_started)}", "✅")
                else:
                    counters.already += 1
                    timeline.stage(label, stage_number, "云端保留数清理", f"当前无需清理，耗时 {elapsed_text(stage_started)}", "☑️")
            except Exception as exc:
                counters.failed += 1
                message = str(exc) if isinstance(exc, (ApiError, TaskError)) else exc.__class__.__name__
                messages.append(f"云端清理失败：{message}")
                timeline.stage(label, stage_number, "云端保留数清理", f"{message}，耗时 {elapsed_text(stage_started)}", "❌")

    result = AccountResult(index, identity, counters.failed == 0, counters, time.monotonic() - started, messages)
    timeline.account_stats(result)
    return result


def emit_final(
    started: float,
    mode: str,
    results: List[AccountResult],
    business_code: int,
    notification_status: str,
    notification_detail: str,
    configuration_error: str = "",
) -> None:
    successful_accounts = sum(1 for result in results if result.ok)
    failed_accounts = len(results) - successful_accounts
    aggregate = Counters()
    for result in results:
        aggregate.total += result.counters.total
        aggregate.success += result.counters.success
        aggregate.already += result.counters.already
        aggregate.skipped += result.counters.skipped
        aggregate.failed += result.counters.failed
    status = "dry-run" if mode == "dry-run" and business_code == 0 else "success" if business_code == 0 else "failure"
    print("-" * 60)
    print(f"账号结果: 总数={len(results)} 成功={successful_accounts} 失败={failed_accounts}")
    print(
        f"子任务结果: 总数={aggregate.total} 成功={aggregate.success} 已完成={aggregate.already} "
        f"跳过={aggregate.skipped} 失败={aggregate.failed}"
    )
    print(f"总耗时: {time.monotonic() - started:.2f}s")
    print(f"完成时间: {now_text()}")
    print(f"通知状态: {notification_status}（{notification_detail}）")
    final_display = "DRY_RUN_SUCCESS" if status == "dry-run" else "SUCCESS" if status == "success" else "FAILURE"
    print(f"最终状态: {final_display}")
    summary: Dict[str, Any] = {
        "accountFailed": failed_accounts,
        "accountSuccess": successful_accounts,
        "accountTotal": len(results),
        "businessExitCode": business_code,
        "durationSeconds": round(time.monotonic() - started, 3),
        "finishTime": now_text(),
        "mode": mode,
        "notification": notification_status,
        "status": status,
        "subtasks": aggregate.as_dict(),
        "task": TASK_NAME,
    }
    if configuration_error:
        summary["configurationError"] = configuration_error
    print("TASK_SUMMARY=" + json_line(summary))


def main() -> int:
    started = time.monotonic()
    timeline = Timeline()
    settings: Optional[Settings] = None
    results: List[AccountResult] = []
    business_code = 1
    configuration_error = ""
    archive_path: Optional[Path] = None
    try:
        settings = Settings.from_env()
        mode = "dry-run" if settings.dry_run else "live"
        timeline.banner(mode, len(settings.tokens))
        print(f"[{clock_text()}] [任务] 阶段 1 - 配置检查: ✅ 参数有效，凭据来源 {settings.credential_env}（值已隐藏）")
        if settings.dry_run:
            print(f"[{clock_text()}] [任务] 阶段 2 - 本地备份: ⏭️ 断网预演不读取或修改备份源")
            results = [run_dry_account(index, settings, timeline) for index in range(1, len(settings.tokens) + 1)]
            business_code = 0
        else:
            if "backup" in settings.actions:
                stage_started = time.monotonic()
                try:
                    archive_path = make_archive(settings)
                    print(
                        f"[{clock_text()}] [任务] 阶段 2 - 本地备份: ✅ 已创建 {archive_path.name} "
                        f"（{archive_path.stat().st_size} 字节），耗时 {elapsed_text(stage_started)}"
                    )
                except Exception as exc:
                    message = str(exc) if isinstance(exc, (TaskError, OSError, tarfile.TarError)) else exc.__class__.__name__
                    print(f"[{clock_text()}] [任务] 阶段 2 - 本地备份: ❌ {message}，耗时 {elapsed_text(stage_started)}")
            else:
                print(f"[{clock_text()}] [任务] 阶段 2 - 本地备份: ⏭️ QLBK_ACTIONS 未启用 backup")
            for index, token in enumerate(settings.tokens, start=1):
                results.append(run_live_account(index, token, settings, archive_path, timeline))
            if "backup" in settings.actions and archive_path is not None:
                stage_started = time.monotonic()
                try:
                    removed = prune_local(settings.backup_dir, settings.local_max)
                    icon = "✅" if removed else "☑️"
                    message = f"已删除 {removed} 个旧备份" if removed else "当前无需清理"
                    print(f"[{clock_text()}] [任务] 阶段 3 - 本地保留数清理: {icon} {message}，耗时 {elapsed_text(stage_started)}")
                except OSError as exc:
                    print(f"[{clock_text()}] [任务] 阶段 3 - 本地保留数清理: ❌ {exc.__class__.__name__}，耗时 {elapsed_text(stage_started)}")
                    for result in results:
                        result.ok = False
                        result.counters.total += 1
                        result.counters.failed += 1
                        result.messages.append("本地保留数清理失败")
                        timeline.stage(account_label(result.index, result.identity), 5, "本地保留数清理", "共享清理阶段失败", "❌")
                        timeline.account_stats(result)
            business_code = 0 if results and all(result.ok for result in results) else 1
    except ConfigError as exc:
        configuration_error = str(exc)
        mode = "dry-run" if os.getenv("QLBK_DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"} else "live"
        timeline.banner(mode, 0)
        print(f"[{clock_text()}] [任务] 阶段 1 - 配置检查: ❌ {configuration_error}")
        business_code = 2
    except Exception as exc:
        mode = "live"
        configuration_error = f"未预期错误：{exc.__class__.__name__}"
        timeline.banner(mode, 0)
        print(f"[{clock_text()}] [任务] 阶段 1 - 运行检查: ❌ {configuration_error}")
        business_code = 1

    mode = "dry-run" if settings is not None and settings.dry_run else locals().get("mode", "live")
    success_count = sum(1 for result in results if result.ok)
    failure_count = len(results) - success_count
    body = f"账号总数：{len(results)}\n成功数：{success_count}\n失败数：{failure_count}\n状态：{'成功' if business_code == 0 else '失败'}"
    if configuration_error:
        body += "\n配置检查：失败"
    notification_status, notification_detail = send_notification(TASK_NAME, body, mode == "dry-run")
    emit_final(
        started,
        mode,
        results,
        business_code,
        notification_status,
        notification_detail,
        configuration_error,
    )
    return business_code


if __name__ == "__main__":
    sys.exit(main())
