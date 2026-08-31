#!/usr/bin/env python3
"""Monitor Facebook Page reaction abuse and apply configured moderation actions."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import logging
import math
import os
import re
import stat
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from browser_moderator import (
    BrowserAutomationError,
    BrowserModerator,
    BrowserPageBudgetExceeded,
    ReactionCollectionError,
)

MAX_CONFIG_BYTES = 65_536
MAX_RESPONSE_BYTES = 1_000_000
MAX_STATE_BYTES = 16_777_216
MAX_STORAGE_STATE_BYTES = 5_000_000
GRAPH_ID = re.compile(r"[A-Za-z0-9_:-]{1,200}\Z")
NUMERIC_ID = re.compile(r"[0-9]{1,64}\Z")
GRAPH_VERSION = re.compile(r"v[0-9]{1,2}\.[0-9]{1,2}\Z")
GRAPH_EDGE = re.compile(r"[A-Za-z0-9_:-]{1,200}/(?:posts|comments|ratings)\Z")
TELEGRAM_TOKEN = re.compile(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,}\Z")
TELEGRAM_CHAT_ID = re.compile(r"-?[0-9]{1,24}\Z")
ALLOWED_REACTIONS = frozenset({"ANGRY", "HAHA"})
DEFAULT_REVIEW_KEYWORDS = ("نصاب", "نصابين", "لا انصح", "حرامي", "حرامية", "نصب")


class ConfigurationError(ValueError):
    """Configuration is missing or unsafe."""


class IntegrationError(RuntimeError):
    """An external integration failed without exposing its response body."""


class RequestBudgetExceeded(IntegrationError):
    """The configured Graph request budget was exhausted."""


class NoRedirects(HTTPRedirectHandler):
    """Prevent credentials from following redirects away from a fixed origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class PageConfig:
    id: str
    name: str
    url: str
    access_token: str = field(repr=False)


@dataclass(frozen=True)
class Settings:
    pages: tuple[PageConfig, ...]
    graph_version: str
    reactions: tuple[str, ...]
    reaction_labels: tuple[tuple[str, str], ...]
    reaction_icon_markers: tuple[tuple[str, str], ...]
    reaction_more_text: str
    monitor_comments: bool
    monitor_ratings: bool
    review_keywords: tuple[str, ...]
    poll_interval: float
    graph_timeout: float
    max_edge_pages: int
    max_graph_requests: int
    max_browser_pages: int
    max_reaction_actors: int
    max_moderation_actions: int
    state_path: Path
    log_path: Path
    storage_state: Path | None
    browser_headless: bool
    switch_text: str
    profile_menu_text: str
    block_text: str
    confirm_text: str
    telegram_token: str | None = field(repr=False)
    telegram_chat_ids: tuple[str, ...] = field(repr=False)


def strict_json_loads(value: str | bytes) -> object:
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = item
        return result

    try:
        return json.loads(value, object_pairs_hook=unique_object)
    except RecursionError as error:
        raise ValueError("JSON nesting is too deep") from error


def require_text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(f"{name} must be a string")
    result = unicodedata.normalize("NFKC", value.strip())
    if not result or len(result) > maximum:
        raise ConfigurationError(f"{name} must contain 1-{maximum} characters")
    if any(ord(character) < 32 for character in result):
        raise ConfigurationError(f"{name} contains control characters")
    return result


def parse_path(value: str | None, name: str, default: str | None = None) -> Path | None:
    raw = default if value is None else value
    if raw is None:
        return None
    if not raw or raw != raw.strip() or len(raw) > 4_096 or any(ord(character) < 32 for character in raw):
        raise ConfigurationError(f"{name} must be a bounded path without control characters")
    return Path(raw)


def parse_bool(value: str | None, name: str, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ConfigurationError(f"{name} must be true or false")


def parse_number(
    value: str | None,
    name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        result = default if value is None else float(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number") from error
    if not minimum <= result <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum:g} and {maximum:g}")
    return result


def parse_integer(value: str | None, name: str, default: int, minimum: int, maximum: int) -> int:
    result = parse_number(value, name, default, minimum, maximum)
    if not result.is_integer():
        raise ConfigurationError(f"{name} must be a whole number")
    return int(result)


def parse_json_setting(environment: Mapping[str, str], name: str) -> object:
    raw = environment.get(name)
    if raw is None or not raw.strip():
        raise ConfigurationError(f"{name} is required")
    if len(raw.encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ConfigurationError(f"{name} exceeds {MAX_CONFIG_BYTES} bytes")
    try:
        return strict_json_loads(raw)
    except (json.JSONDecodeError, ValueError) as error:
        raise ConfigurationError(f"{name} must be valid JSON without duplicate keys") from error


def validate_page_url(value: object) -> str:
    url = require_text(value, "Page url", 500)
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ConfigurationError("every Page url must use a valid HTTPS port") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"facebook.com", "www.facebook.com", "m.facebook.com"}
        or port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.fragment
        or not parsed.path.startswith("/")
    ):
        raise ConfigurationError("every Page url must be an HTTPS facebook.com URL")
    if parsed.query:
        try:
            query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
        except ValueError as error:
            raise ConfigurationError("Page url query string is invalid") from error
        if (
            parsed.path != "/profile.php"
            or set(query) != {"id"}
            or len(query["id"]) != 1
            or not NUMERIC_ID.fullmatch(query["id"][0])
        ):
            raise ConfigurationError("Page url query strings are allowed only for profile.php?id=<digits>")
    return url


def load_settings(environment: Mapping[str, str] | None = None) -> Settings:
    environment = os.environ if environment is None else environment
    raw_pages = parse_json_setting(environment, "META_PAGES_JSON")
    if not isinstance(raw_pages, list) or not 1 <= len(raw_pages) <= 25:
        raise ConfigurationError("META_PAGES_JSON must contain 1-25 Page objects")

    pages = []
    seen_page_ids = set()
    expected = {"id", "name", "url", "access_token"}
    for index, raw_page in enumerate(raw_pages, 1):
        if not isinstance(raw_page, dict) or set(raw_page) != expected:
            raise ConfigurationError(f"Page {index} must contain only id, name, url, and access_token")
        page_id = require_text(raw_page["id"], f"Page {index} id", 64)
        if not NUMERIC_ID.fullmatch(page_id) or page_id in seen_page_ids:
            raise ConfigurationError("Page IDs must be unique and contain only digits")
        token = require_text(raw_page["access_token"], f"Page {index} access_token", 4_096)
        if any(character.isspace() for character in token):
            raise ConfigurationError("Page access tokens must not contain whitespace")
        seen_page_ids.add(page_id)
        pages.append(
            PageConfig(
                id=page_id,
                name=require_text(raw_page["name"], f"Page {index} name", 80),
                url=validate_page_url(raw_page["url"]),
                access_token=token,
            )
        )

    graph_version = require_text(environment.get("META_GRAPH_VERSION"), "META_GRAPH_VERSION", 8)
    if not GRAPH_VERSION.fullmatch(graph_version):
        raise ConfigurationError("META_GRAPH_VERSION must look like v26.0")

    reaction_items = environment.get("REACTION_TYPES", "ANGRY,HAHA").split(",")
    reactions = tuple(require_text(item, "reaction type", 16).upper() for item in reaction_items)
    if not reactions or len(set(reactions)) != len(reactions) or not set(reactions) <= ALLOWED_REACTIONS:
        raise ConfigurationError("REACTION_TYPES must contain unique ANGRY and/or HAHA values")

    parsed_reaction_labels = parse_json_setting(environment, "FACEBOOK_REACTION_LABELS_JSON")
    if not isinstance(parsed_reaction_labels, dict) or set(parsed_reaction_labels) != set(reactions):
        raise ConfigurationError(
            "FACEBOOK_REACTION_LABELS_JSON keys must exactly match REACTION_TYPES"
        )
    reaction_labels = {
        reaction: require_text(parsed_reaction_labels[reaction], f"{reaction} reaction label", 80)
        for reaction in reactions
    }
    if len({label.casefold() for label in reaction_labels.values()}) != len(reaction_labels):
        raise ConfigurationError("FACEBOOK_REACTION_LABELS_JSON values must be unique")

    parsed_icon_markers = parse_json_setting(
        environment, "FACEBOOK_REACTION_ICON_SRC_MARKERS_JSON"
    )
    if not isinstance(parsed_icon_markers, dict) or set(parsed_icon_markers) != set(reactions):
        raise ConfigurationError(
            "FACEBOOK_REACTION_ICON_SRC_MARKERS_JSON keys must exactly match REACTION_TYPES"
        )
    reaction_icon_markers = {
        reaction: require_text(
            parsed_icon_markers[reaction], f"{reaction} reaction icon source marker", 200
        )
        for reaction in reactions
    }
    if any(len(marker) < 4 or any(character.isspace() for character in marker) for marker in reaction_icon_markers.values()):
        raise ConfigurationError(
            "FACEBOOK_REACTION_ICON_SRC_MARKERS_JSON values must be 4-200 non-whitespace characters"
        )
    if len(set(reaction_icon_markers.values())) != len(reaction_icon_markers):
        raise ConfigurationError("FACEBOOK_REACTION_ICON_SRC_MARKERS_JSON values must be unique")

    keyword_items = environment.get("REVIEW_KEYWORDS", ",".join(DEFAULT_REVIEW_KEYWORDS)).split(",")
    review_keywords = tuple(require_text(item, "review keyword", 64).casefold() for item in keyword_items)
    if not 1 <= len(review_keywords) <= 32 or len(set(review_keywords)) != len(review_keywords):
        raise ConfigurationError("REVIEW_KEYWORDS must contain 1-32 unique comma-separated values")

    telegram_token = environment.get("TELEGRAM_BOT_TOKEN") or None
    raw_chat_ids = environment.get("TELEGRAM_CHAT_IDS_JSON")
    if telegram_token or raw_chat_ids:
        telegram_token = require_text(telegram_token, "TELEGRAM_BOT_TOKEN", 128)
        if not TELEGRAM_TOKEN.fullmatch(telegram_token):
            raise ConfigurationError("TELEGRAM_BOT_TOKEN has an unsupported format")
        chat_ids = parse_json_setting(environment, "TELEGRAM_CHAT_IDS_JSON")
        if (
            not isinstance(chat_ids, list)
            or not 1 <= len(chat_ids) <= 10
            or any(not isinstance(item, str) or not TELEGRAM_CHAT_ID.fullmatch(item) for item in chat_ids)
            or len(set(chat_ids)) != len(chat_ids)
        ):
            raise ConfigurationError("TELEGRAM_CHAT_IDS_JSON must contain 1-10 unique numeric strings")
        telegram_chat_ids = tuple(chat_ids)
    else:
        telegram_chat_ids = ()

    storage_state = parse_path(
        environment.get("BROWSER_STORAGE_STATE"), "BROWSER_STORAGE_STATE"
    )
    state_path = parse_path(
        environment.get("DEFENSE_STATE_PATH"),
        "DEFENSE_STATE_PATH",
        ".runtime/reaction-defense-state.json",
    )
    log_path = parse_path(
        environment.get("DEFENSE_LOG_PATH"),
        "DEFENSE_LOG_PATH",
        ".runtime/reaction-defense.log",
    )
    assert state_path is not None and log_path is not None
    try:
        configured_paths = [state_path.resolve(strict=False), log_path.resolve(strict=False)]
        if storage_state is not None:
            configured_paths.append(storage_state.resolve(strict=False))
    except (OSError, RuntimeError, ValueError) as error:
        raise ConfigurationError("configured runtime paths could not be resolved") from error
    if len(configured_paths) != len(set(configured_paths)):
        raise ConfigurationError("state, log, and browser storage paths must be different")
    max_edge_pages = parse_integer(environment.get("MAX_EDGE_PAGES"), "MAX_EDGE_PAGES", 10, 1, 100)
    max_graph_requests = parse_integer(
        environment.get("MAX_GRAPH_REQUESTS_PER_CYCLE"),
        "MAX_GRAPH_REQUESTS_PER_CYCLE",
        500,
        10,
        10_000,
    )
    monitor_comments = parse_bool(environment.get("MONITOR_COMMENTS"), "MONITOR_COMMENTS", True)
    monitor_ratings = parse_bool(environment.get("MONITOR_RATINGS"), "MONITOR_RATINGS", True)
    baseline_requests = 1 + int(monitor_ratings)
    if monitor_comments:
        baseline_requests += 1
    if max_graph_requests < len(pages) * baseline_requests:
        raise ConfigurationError(
            "MAX_GRAPH_REQUESTS_PER_CYCLE is too small for one baseline traversal per Page"
        )

    return Settings(
        pages=tuple(pages),
        graph_version=graph_version,
        reactions=reactions,
        reaction_labels=tuple(reaction_labels.items()),
        reaction_icon_markers=tuple(reaction_icon_markers.items()),
        reaction_more_text=require_text(
            environment.get("FACEBOOK_REACTION_MORE_TEXT", "عرض المزيد"),
            "FACEBOOK_REACTION_MORE_TEXT",
            80,
        ),
        monitor_comments=monitor_comments,
        monitor_ratings=monitor_ratings,
        review_keywords=review_keywords,
        poll_interval=parse_number(
            environment.get("POLL_INTERVAL_SECONDS"), "POLL_INTERVAL_SECONDS", 30, 5, 3_600
        ),
        graph_timeout=parse_number(
            environment.get("GRAPH_TIMEOUT_SECONDS"), "GRAPH_TIMEOUT_SECONDS", 20, 1, 120
        ),
        max_edge_pages=max_edge_pages,
        max_graph_requests=max_graph_requests,
        max_browser_pages=parse_integer(
            environment.get("MAX_REACTION_BROWSER_PAGES_PER_CYCLE"),
            "MAX_REACTION_BROWSER_PAGES_PER_CYCLE",
            100,
            len(pages),
            10_000,
        ),
        max_reaction_actors=parse_integer(
            environment.get("MAX_REACTION_ACTORS_PER_OBJECT"),
            "MAX_REACTION_ACTORS_PER_OBJECT",
            500,
            1,
            10_000,
        ),
        max_moderation_actions=parse_integer(
            environment.get("MAX_MODERATION_ACTIONS_PER_RUN"),
            "MAX_MODERATION_ACTIONS_PER_RUN",
            25,
            1,
            1_000,
        ),
        state_path=state_path,
        log_path=log_path,
        storage_state=storage_state,
        browser_headless=parse_bool(environment.get("BROWSER_HEADLESS"), "BROWSER_HEADLESS", True),
        switch_text=require_text(environment.get("FACEBOOK_SWITCH_TEXT", "تبديل"), "FACEBOOK_SWITCH_TEXT", 80),
        profile_menu_text=require_text(
            environment.get("FACEBOOK_PROFILE_MENU_TEXT", "المزيد"), "FACEBOOK_PROFILE_MENU_TEXT", 80
        ),
        block_text=require_text(environment.get("FACEBOOK_BLOCK_TEXT", "حظر"), "FACEBOOK_BLOCK_TEXT", 80),
        confirm_text=require_text(environment.get("FACEBOOK_CONFIRM_TEXT", "تأكيد"), "FACEBOOK_CONFIRM_TEXT", 80),
        telegram_token=telegram_token,
        telegram_chat_ids=telegram_chat_ids,
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


STATE_KEYS = {"version", "observations", "moderation_targets", "rating_events"}
TARGET_STATUSES = frozenset({"pending", "applying", "submitted", "failed", "uncertain"})


def new_state_data() -> dict[str, object]:
    return {"version": 1, "observations": [], "moderation_targets": [], "rating_events": []}


def valid_state_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 80 or not value.endswith("Z"):
        return False
    if any(ord(character) < 32 for character in value):
        return False
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_state_data(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or set(data) != STATE_KEYS or type(data.get("version")) is not int:
        raise ConfigurationError("state must be a versioned JSON object with the supported schema")
    if data["version"] != 1:
        raise ConfigurationError(f"unsupported state schema version: {data['version']}")
    for collection in ("observations", "moderation_targets", "rating_events"):
        if not isinstance(data[collection], list):
            raise ConfigurationError(f"state {collection} must be a JSON array")

    observation_keys: set[tuple[str, str, str, str]] = set()
    for item in data["observations"]:
        if not isinstance(item, dict) or set(item) != {
            "page_id",
            "actor_id",
            "source_id",
            "source_kind",
            "reaction",
            "first_seen_at",
        }:
            raise ConfigurationError("state contains an invalid observation object")
        if (
            not isinstance(item["page_id"], str)
            or not NUMERIC_ID.fullmatch(item["page_id"])
            or not isinstance(item["actor_id"], str)
            or not NUMERIC_ID.fullmatch(item["actor_id"])
            or not isinstance(item["source_id"], str)
            or not GRAPH_ID.fullmatch(item["source_id"])
            or not isinstance(item["source_kind"], str)
            or item["source_kind"] not in {"post", "comment"}
            or not isinstance(item["reaction"], str)
            or item["reaction"] not in ALLOWED_REACTIONS
            or not valid_state_timestamp(item["first_seen_at"])
        ):
            raise ConfigurationError("state contains invalid observation values")
        key = (item["page_id"], item["actor_id"], item["source_id"], item["reaction"])
        if key in observation_keys:
            raise ConfigurationError("state contains a duplicate observation")
        observation_keys.add(key)

    target_keys: set[tuple[str, str]] = set()
    for item in data["moderation_targets"]:
        if not isinstance(item, dict) or set(item) != {
            "page_id",
            "actor_id",
            "status",
            "attempts",
            "first_seen_at",
            "updated_at",
            "last_error",
        }:
            raise ConfigurationError("state contains an invalid moderation target object")
        last_error = item["last_error"]
        if (
            not isinstance(item["page_id"], str)
            or not NUMERIC_ID.fullmatch(item["page_id"])
            or not isinstance(item["actor_id"], str)
            or not NUMERIC_ID.fullmatch(item["actor_id"])
            or not isinstance(item["status"], str)
            or item["status"] not in TARGET_STATUSES
            or type(item["attempts"]) is not int
            or not 0 <= item["attempts"] <= 1_000_000_000
            or not valid_state_timestamp(item["first_seen_at"])
            or not valid_state_timestamp(item["updated_at"])
            or not (
                last_error is None
                or (
                    isinstance(last_error, str)
                    and 1 <= len(last_error) <= 500
                    and not any(ord(character) < 32 for character in last_error)
                )
            )
        ):
            raise ConfigurationError("state contains invalid moderation target values")
        key = (item["page_id"], item["actor_id"])
        if key in target_keys:
            raise ConfigurationError("state contains a duplicate moderation target")
        target_keys.add(key)

    rating_keys: set[str] = set()
    for item in data["rating_events"]:
        if not isinstance(item, dict) or set(item) != {
            "event_key",
            "page_id",
            "matched",
            "first_seen_at",
        }:
            raise ConfigurationError("state contains an invalid rating event object")
        if (
            not isinstance(item["event_key"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", item["event_key"])
            or not isinstance(item["page_id"], str)
            or not NUMERIC_ID.fullmatch(item["page_id"])
            or type(item["matched"]) is not bool
            or not valid_state_timestamp(item["first_seen_at"])
        ):
            raise ConfigurationError("state contains invalid rating event values")
        if item["event_key"] in rating_keys:
            raise ConfigurationError("state contains a duplicate rating event")
        rating_keys.add(item["event_key"])
    return data


def prepare_private_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ConfigurationError("state directory must be a real directory")
    if path.parent.stat().st_mode & 0o077:
        raise ConfigurationError("state directory must not be accessible by group or others")


@contextmanager
def state_lock(state_path: Path):
    prepare_private_parent(state_path)
    lock_path = state_path.with_name(f"{state_path.name}.lock")
    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("lock path is not a regular file")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        if "descriptor" in locals():
            os.close(descriptor)
        raise ConfigurationError("another state process is active") from None
    try:
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


class JsonState:
    def __init__(self, path: Path, data: dict[str, object]):
        self.path = path
        self.data = data

    @property
    def observations(self) -> list[dict[str, object]]:
        return self.data["observations"]

    @property
    def targets(self) -> list[dict[str, object]]:
        return self.data["moderation_targets"]

    @property
    def ratings(self) -> list[dict[str, object]]:
        return self.data["rating_events"]

    def save(self) -> None:
        validate_state_data(self.data)
        payload = (json.dumps(self.data, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        if len(payload) > MAX_STATE_BYTES:
            raise ConfigurationError(f"state exceeds {MAX_STATE_BYTES} bytes")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
            self.path.chmod(0o600)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)


@contextmanager
def open_state(path: Path):
    if path.is_symlink():
        raise ConfigurationError("state path must not be a symbolic link")
    with state_lock(path):
        if path.exists():
            descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise ConfigurationError("state path must be a regular file")
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    raw = stream.read(MAX_STATE_BYTES + 1)
            finally:
                os.close(descriptor)
            if len(raw) > MAX_STATE_BYTES:
                raise ConfigurationError(f"state exceeds {MAX_STATE_BYTES} bytes")
            try:
                data = validate_state_data(strict_json_loads(raw.decode("utf-8")))
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                if isinstance(error, ConfigurationError):
                    raise
                raise ConfigurationError("state must be valid UTF-8 JSON without duplicate keys") from error
            state = JsonState(path, data)
        else:
            state = JsonState(path, new_state_data())
            state.save()
        yield state


def record_reactor(
    state: JsonState,
    page_id: str,
    actor_id: str,
    source_id: str,
    source_kind: str,
    reaction: str,
) -> tuple[bool, bool]:
    timestamp = utc_now()
    observation_key = (page_id, actor_id, source_id, reaction)
    observation_added = not any(
        (item["page_id"], item["actor_id"], item["source_id"], item["reaction"])
        == observation_key
        for item in state.observations
    )
    target_added = not any(
        item["page_id"] == page_id and item["actor_id"] == actor_id for item in state.targets
    )
    if observation_added:
        state.observations.append(
            {
                "page_id": page_id,
                "actor_id": actor_id,
                "source_id": source_id,
                "source_kind": source_kind,
                "reaction": reaction,
                "first_seen_at": timestamp,
            }
        )
    if target_added:
        state.targets.append(
            {
                "page_id": page_id,
                "actor_id": actor_id,
                "status": "pending",
                "attempts": 0,
                "first_seen_at": timestamp,
                "updated_at": timestamp,
                "last_error": None,
            }
        )
    if observation_added or target_added:
        state.save()
    return observation_added, target_added


def record_rating(
    state: JsonState,
    page_id: str,
    reviewer_id: str,
    created_at: str,
    matched: bool,
) -> bool:
    event_key = hashlib.sha256(f"{page_id}\0{reviewer_id}\0{created_at}".encode()).hexdigest()
    if any(item["event_key"] == event_key for item in state.ratings):
        return False
    state.ratings.append(
        {
            "event_key": event_key,
            "page_id": page_id,
            "matched": matched,
            "first_seen_at": utc_now(),
        }
    )
    state.save()
    return True


def status_summary(state: JsonState) -> dict[str, object]:
    statuses: dict[str, int] = {}
    for target in state.targets:
        status = target["status"]
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "observations": len(state.observations),
        "unique_targets": len(state.targets),
        "target_statuses": dict(sorted(statuses.items())),
        "rating_events": len(state.ratings),
        "matched_rating_alerts": sum(item["matched"] is True for item in state.ratings),
    }


def target_reference(page_id: str, actor_id: str) -> str:
    return hashlib.sha256(f"{page_id}\0{actor_id}".encode()).hexdigest()


def list_incomplete(
    state: JsonState, *, include_identifiers: bool = False
) -> list[dict[str, object]]:
    return [
        {
            "target_ref": target_reference(row["page_id"], row["actor_id"]),
            "status": row["status"],
            "attempts": row["attempts"],
            **(
                {"page_id": row["page_id"], "actor_id": row["actor_id"]}
                if include_identifiers
                else {}
            ),
        }
        for row in sorted(
            (item for item in state.targets if item["status"] in {"applying", "uncertain"}),
            key=lambda item: (item["updated_at"], item["page_id"], item["actor_id"]),
        )
    ]


def resolve_incomplete(state: JsonState, reference: str, outcome: str) -> dict[str, str]:
    if not re.fullmatch(r"[a-f0-9]{64}", reference):
        raise ConfigurationError("target reference must contain 64 lowercase hexadecimal characters")
    if outcome not in {"requeue", "submitted"}:
        raise ConfigurationError("outcome must be requeue or submitted")
    for row in state.targets:
        if row["status"] not in {"applying", "uncertain"}:
            continue
        if target_reference(row["page_id"], row["actor_id"]) != reference:
            continue
        new_status = "pending" if outcome == "requeue" else "submitted"
        row.update(status=new_status, updated_at=utc_now(), last_error=None)
        state.save()
        return {"target_ref": reference, "status": new_status}
    raise ConfigurationError("unknown or already resolved target reference")


def safe_api_error(status: int, body: bytes) -> str:
    message = f"Graph API HTTP {status}"
    try:
        payload = strict_json_loads(body)
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return message
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(code, int):
        message += f" code {code}"
    return message


class GraphClient:
    def __init__(
        self,
        version: str,
        timeout: float,
        max_pages: int,
        max_requests: int = 500,
        *,
        opener=None,
        sleeper=time.sleep,
    ):
        if not GRAPH_VERSION.fullmatch(version):
            raise ConfigurationError("invalid Graph API version")
        self.version = version
        self.timeout = timeout
        self.max_pages = max_pages
        self.max_requests = max_requests
        self.requests_remaining = max_requests
        self.opener = opener or build_opener(NoRedirects)
        self.sleeper = sleeper

    def reset_budget(self, maximum: int | None = None) -> None:
        self.requests_remaining = self.max_requests if maximum is None else maximum

    def _get(self, edge: str, token: str, parameters: dict[str, str]) -> dict[str, object]:
        if not GRAPH_EDGE.fullmatch(edge):
            raise IntegrationError("unsupported Graph API edge")
        url = (
            f"https://graph.facebook.com/{self.version}/{quote(edge, safe='/:_-')}?"
            f"{urlencode(parameters)}"
        )
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "facebook-reaction-abuse-defense/1.0",
            },
        )
        for attempt in range(3):
            if self.requests_remaining <= 0:
                raise RequestBudgetExceeded("Graph request budget was exhausted for this cycle")
            self.requests_remaining -= 1
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise IntegrationError("Graph API response exceeded the size limit")
                    payload = strict_json_loads(body)
                    if not isinstance(payload, dict):
                        raise IntegrationError("Graph API returned an invalid object")
                    if "error" in payload:
                        raise IntegrationError("Graph API returned an application error")
                    return payload
            except HTTPError as error:
                body = error.read(MAX_RESPONSE_BYTES + 1)
                if error.code in {429, 500, 502, 503, 504} and attempt < 2:
                    self.sleeper(2**attempt)
                    continue
                raise IntegrationError(safe_api_error(error.code, body)) from error
            except URLError as error:
                if attempt < 2:
                    self.sleeper(2**attempt)
                    continue
                raise IntegrationError("Graph API network error") from error
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                raise IntegrationError("Graph API returned invalid JSON") from error
        raise AssertionError("unreachable")

    def iter_data(
        self,
        edge: str,
        token: str,
        parameters: Mapping[str, str] | None = None,
    ) -> Iterable[dict[str, object]]:
        query = dict(parameters or {})
        for _ in range(self.max_pages):
            payload = self._get(edge, token, query)
            data = payload.get("data")
            if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                raise IntegrationError("Graph API data has an invalid shape")
            yield from data
            paging = payload.get("paging")
            if paging is None:
                return
            if not isinstance(paging, dict):
                raise IntegrationError("Graph API paging has an invalid shape")
            next_page = paging.get("next")
            if next_page is not None and (
                not isinstance(next_page, str)
                or not next_page
                or len(next_page) > 4_096
                or any(ord(character) < 32 for character in next_page)
            ):
                raise IntegrationError("Graph API next-page metadata has an invalid shape")
            cursors = paging.get("cursors")
            if cursors is None:
                if next_page is not None:
                    raise IntegrationError("Graph API paging has an invalid shape")
                return
            if not isinstance(cursors, dict):
                raise IntegrationError("Graph API cursors have an invalid shape")
            after = cursors.get("after")
            if after is None:
                if next_page is not None:
                    raise IntegrationError("Graph API paging has an invalid shape")
                return
            if not isinstance(after, str) or len(after) > 2_048 or any(ord(character) < 32 for character in after):
                raise IntegrationError("Graph API cursor has an invalid shape")
            if not after:
                raise IntegrationError("Graph API cursor has an invalid shape")
            query["after"] = after
        raise IntegrationError("Graph API pagination exceeded the configured limit")


class TelegramNotifier:
    def __init__(self, token: str | None, chat_ids: tuple[str, ...], timeout: float, *, opener=None):
        self.token = token
        self.chat_ids = chat_ids
        self.timeout = timeout
        self.opener = opener or build_opener(NoRedirects)

    def send(self, message: str) -> None:
        if not self.token:
            return
        for chat_id in self.chat_ids:
            request = Request(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data=urlencode({"chat_id": chat_id, "text": message}).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise IntegrationError("Telegram response exceeded the size limit")
                    payload = strict_json_loads(body)
                    if not isinstance(payload, dict) or payload.get("ok") is not True:
                        raise IntegrationError("Telegram did not accept the notification")
            except (HTTPError, URLError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                raise IntegrationError("Telegram notification failed") from error


def provider_id(value: object) -> str | None:
    return value if isinstance(value, str) and GRAPH_ID.fullmatch(value) else None


async def collect_object_reactions(
    state: JsonState,
    browser: BrowserModerator,
    page: PageConfig,
    object_id: str,
    source_kind: str,
    result: dict[str, int],
) -> None:
    try:
        async for reaction, actor_id in browser.iter_reactors(object_id):
            observation_added, target_added = record_reactor(
                state, page.id, actor_id, object_id, source_kind, reaction
            )
            result["new_observations"] += int(observation_added)
            result["new_targets"] += int(target_added)
    except BrowserPageBudgetExceeded:
        raise
    except ReactionCollectionError as error:
        result["edge_failures"] += 1
        logging.warning(
            "Reaction collection failed for one %s on Page %s: %s",
            source_kind,
            page.name,
            error,
        )


async def monitor_page(
    state: JsonState,
    client: GraphClient,
    browser: BrowserModerator,
    page: PageConfig,
    settings: Settings,
) -> dict[str, int]:
    result = {
        "posts": 0,
        "comments": 0,
        "new_observations": 0,
        "new_targets": 0,
        "new_rating_alerts": 0,
        "edge_failures": 0,
        "budget_exhausted": 0,
        "browser_budget_exhausted": 0,
    }
    if settings.monitor_ratings:
        try:
            ratings = client.iter_data(
                f"{page.id}/ratings",
                page.access_token,
                {"fields": "reviewer,created_time,review_text", "limit": "100"},
            )
            for rating in ratings:
                reviewer = rating.get("reviewer")
                reviewer_id = provider_id(reviewer.get("id")) if isinstance(reviewer, dict) else None
                created_at = rating.get("created_time")
                text = rating.get("review_text", "")
                if (
                    not reviewer_id
                    or not NUMERIC_ID.fullmatch(reviewer_id)
                    or not isinstance(created_at, str)
                    or not 1 <= len(created_at) <= 80
                    or any(ord(character) < 32 for character in created_at)
                    or not isinstance(text, str)
                    or len(text) > 10_000
                ):
                    logging.warning("Skipped a Page rating with an invalid shape")
                    continue
                normalized = unicodedata.normalize("NFKC", text).casefold()
                matched = any(keyword in normalized for keyword in settings.review_keywords)
                if record_rating(state, page.id, reviewer_id, created_at, matched) and matched:
                    result["new_rating_alerts"] += 1
                    logging.info("Suspicious Page rating detected on Page %s", page.name)
        except RequestBudgetExceeded as error:
            result["edge_failures"] += 1
            result["budget_exhausted"] = 1
            logging.warning("Graph request budget exhausted on Page %s: %s", page.name, error)
            return result
        except IntegrationError as error:
            result["edge_failures"] += 1
            logging.warning("Page rating collection failed for Page %s: %s", page.name, error)

    try:
        posts = client.iter_data(f"{page.id}/posts", page.access_token, {"fields": "id", "limit": "100"})
        for post in posts:
            post_id = provider_id(post.get("id"))
            if not post_id:
                logging.warning("Skipped a post with an invalid identifier")
                continue
            result["posts"] += 1
            await collect_object_reactions(state, browser, page, post_id, "post", result)

            if settings.monitor_comments:
                try:
                    comments = client.iter_data(
                        f"{post_id}/comments", page.access_token, {"fields": "id", "limit": "100"}
                    )
                    for comment in comments:
                        comment_id = provider_id(comment.get("id"))
                        if not comment_id:
                            logging.warning("Skipped a comment with an invalid identifier")
                            continue
                        result["comments"] += 1
                        await collect_object_reactions(
                            state, browser, page, comment_id, "comment", result
                        )
                except BrowserPageBudgetExceeded:
                    raise
                except RequestBudgetExceeded:
                    raise
                except IntegrationError as error:
                    result["edge_failures"] += 1
                    logging.warning("Comment discovery failed for Page %s: %s", page.name, error)
    except BrowserPageBudgetExceeded as error:
        result["edge_failures"] += 1
        result["browser_budget_exhausted"] = 1
        logging.warning("Reaction browser budget exhausted on Page %s: %s", page.name, error)
        return result
    except RequestBudgetExceeded as error:
        result["edge_failures"] += 1
        result["budget_exhausted"] = 1
        logging.warning("Graph request budget exhausted on Page %s: %s", page.name, error)
        return result
    except IntegrationError as error:
        result["edge_failures"] += 1
        logging.warning("Post discovery failed for Page %s: %s", page.name, error)

    return result


async def run_monitoring_cycle(
    state: JsonState,
    settings: Settings,
    client: GraphClient,
    browser: BrowserModerator,
    notifier: TelegramNotifier,
) -> dict[str, object]:
    page_budget, extra_requests = divmod(settings.max_graph_requests, len(settings.pages))
    browser_budget, extra_browser_pages = divmod(settings.max_browser_pages, len(settings.pages))
    totals = {
        "pages_ok": 0,
        "pages_failed": 0,
        "posts": 0,
        "comments": 0,
        "new_observations": 0,
        "new_targets": 0,
        "new_rating_alerts": 0,
        "edge_failures": 0,
        "budget_exhausted": 0,
        "browser_budget_exhausted": 0,
    }
    errors = []
    for page_index, page in enumerate(settings.pages):
        if hasattr(client, "reset_budget"):
            client.reset_budget(page_budget + int(page_index < extra_requests))
        browser.reset_collection_budget(
            browser_budget + int(page_index < extra_browser_pages)
        )
        try:
            page_result = await monitor_page(state, client, browser, page, settings)
        except (IntegrationError, BrowserAutomationError) as error:
            totals["pages_failed"] += 1
            errors.append({"page": page.name, "error": str(error)})
            logging.error("Monitoring failed for Page %s: %s", page.name, error)
            continue
        if page_result["edge_failures"]:
            totals["pages_failed"] += 1
            errors.append(
                {"page": page.name, "error": f"{page_result['edge_failures']} collection edge(s) failed"}
            )
        else:
            totals["pages_ok"] += 1
        for key in page_result:
            totals[key] += page_result[key]
        if page_result["new_targets"]:
            try:
                notifier.send(f"{page.name}: {page_result['new_targets']} new reaction-abuse target(s) detected.")
            except IntegrationError as error:
                logging.warning("Notification failed for Page %s: %s", page.name, error)
        if page_result["new_rating_alerts"]:
            try:
                notifier.send(f"{page.name}: {page_result['new_rating_alerts']} suspicious Page rating(s) detected.")
            except IntegrationError as error:
                logging.warning("Rating notification failed for Page %s: %s", page.name, error)
    return {**totals, "errors": errors}


def validate_browser_storage(settings: Settings) -> dict[str, object]:
    if settings.storage_state is None:
        raise ConfigurationError("BROWSER_STORAGE_STATE is required for monitoring")
    try:
        storage_path = settings.storage_state.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ConfigurationError("BROWSER_STORAGE_STATE must be an existing regular file") from error
    if storage_path != settings.storage_state.absolute():
        raise ConfigurationError("BROWSER_STORAGE_STATE path must not contain symbolic links")
    if not storage_path.parent.is_dir() or storage_path.parent.stat().st_mode & 0o077:
        raise ConfigurationError("BROWSER_STORAGE_STATE directory must use private permissions")
    try:
        descriptor = os.open(storage_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as error:
        raise ConfigurationError("BROWSER_STORAGE_STATE must be an existing regular file") from error
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & 0o077
            or metadata.st_size > MAX_STORAGE_STATE_BYTES
        ):
            raise ConfigurationError("BROWSER_STORAGE_STATE is not a bounded regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(MAX_STORAGE_STATE_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(raw) > MAX_STORAGE_STATE_BYTES:
        raise ConfigurationError("BROWSER_STORAGE_STATE exceeds the size limit")
    try:
        payload = strict_json_loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        raise ConfigurationError("BROWSER_STORAGE_STATE must be valid JSON without duplicate keys") from error
    if not isinstance(payload, dict) or set(payload) != {"cookies", "origins"}:
        raise ConfigurationError("BROWSER_STORAGE_STATE must contain only cookies and origins")
    if not isinstance(payload["cookies"], list) or not isinstance(payload["origins"], list):
        raise ConfigurationError("BROWSER_STORAGE_STATE cookies and origins must be arrays")
    if len(payload["cookies"]) > 10_000 or len(payload["origins"]) > 100:
        raise ConfigurationError("BROWSER_STORAGE_STATE contains too many entries")

    cookie_keys = {
        "name",
        "value",
        "domain",
        "path",
        "expires",
        "httpOnly",
        "secure",
        "sameSite",
    }
    for cookie in payload["cookies"]:
        if not isinstance(cookie, dict) or set(cookie) != cookie_keys:
            raise ConfigurationError("BROWSER_STORAGE_STATE contains an invalid cookie")
        domain = cookie["domain"]
        expires = cookie["expires"]
        if (
            not isinstance(cookie["name"], str)
            or not 1 <= len(cookie["name"]) <= 256
            or any(ord(character) < 32 for character in cookie["name"])
            or not isinstance(cookie["value"], str)
            or len(cookie["value"]) > 65_536
            or not isinstance(domain, str)
            or not 1 <= len(domain) <= 255
            or (
                domain.lstrip(".").casefold() != "facebook.com"
                and not domain.lstrip(".").casefold().endswith(".facebook.com")
            )
            or not isinstance(cookie["path"], str)
            or not cookie["path"].startswith("/")
            or len(cookie["path"]) > 2_048
            or isinstance(expires, bool)
            or not isinstance(expires, (int, float))
            or not math.isfinite(expires)
            or not -1 <= expires <= 253_402_300_799
            or type(cookie["httpOnly"]) is not bool
            or type(cookie["secure"]) is not bool
            or not isinstance(cookie["sameSite"], str)
            or cookie["sameSite"] not in {"Lax", "None", "Strict"}
        ):
            raise ConfigurationError("BROWSER_STORAGE_STATE contains invalid cookie values")

    for origin in payload["origins"]:
        if not isinstance(origin, dict) or set(origin) != {"origin", "localStorage"}:
            raise ConfigurationError("BROWSER_STORAGE_STATE contains an invalid origin")
        if not isinstance(origin["origin"], str):
            raise ConfigurationError("BROWSER_STORAGE_STATE contains invalid origin values")
        try:
            parsed_origin = urlsplit(origin["origin"])
            origin_port = parsed_origin.port
        except (TypeError, ValueError):
            raise ConfigurationError("BROWSER_STORAGE_STATE contains an invalid origin") from None
        if (
            parsed_origin.scheme != "https"
            or not parsed_origin.hostname
            or (
                parsed_origin.hostname != "facebook.com"
                and not parsed_origin.hostname.endswith(".facebook.com")
            )
            or origin_port not in (None, 443)
            or parsed_origin.username
            or parsed_origin.password
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
            or not isinstance(origin["localStorage"], list)
            or len(origin["localStorage"]) > 10_000
        ):
            raise ConfigurationError("BROWSER_STORAGE_STATE contains invalid origin values")
        for item in origin["localStorage"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"name", "value"}
                or not isinstance(item["name"], str)
                or not 1 <= len(item["name"]) <= 1_024
                or not isinstance(item["value"], str)
                or len(item["value"]) > 1_000_000
            ):
                raise ConfigurationError(
                    "BROWSER_STORAGE_STATE contains invalid local storage values"
                )
    return payload


async def apply_pending_targets(
    state: JsonState,
    settings: Settings,
    notifier: TelegramNotifier,
    *,
    moderator=None,
    moderator_factory=None,
) -> dict[str, int]:
    pages = {page.id: page for page in settings.pages}
    pending_page_ids = {
        target["page_id"] for target in state.targets if target["status"] == "pending"
    }
    if pending_page_ids - pages.keys():
        raise ConfigurationError("a pending target belongs to an unconfigured Page")
    targets = sorted(
        (target for target in state.targets if target["status"] == "pending"),
        key=lambda target: (target["first_seen_at"], target["page_id"], target["actor_id"]),
    )[: settings.max_moderation_actions]
    result = {"selected": len(targets), "submitted": 0, "failed": 0, "uncertain": 0}
    if not targets:
        return result

    async def apply_with(active_moderator) -> None:
        for target in targets:
            page = pages[target["page_id"]]
            target.update(
                status="applying",
                attempts=target["attempts"] + 1,
                updated_at=utc_now(),
                last_error=None,
            )
            state.save()
            try:
                await active_moderator.block_account(page, target["actor_id"])
            except Exception as error:
                failure_status = "uncertain" if getattr(error, "outcome_uncertain", False) else "failed"
                target.update(
                    status=failure_status,
                    updated_at=utc_now(),
                    last_error="browser moderation failed",
                )
                state.save()
                result[failure_status] += 1
                logging.warning("Browser moderation failed for one target on Page %s", page.name)
            else:
                target.update(status="submitted", updated_at=utc_now(), last_error=None)
                state.save()
                result["submitted"] += 1

    if moderator is None:
        storage_state = validate_browser_storage(settings)
        moderator = (
            moderator_factory(settings)
            if moderator_factory
            else BrowserModerator(settings, storage_state)
        )
        async with moderator:
            await apply_with(moderator)
    else:
        await apply_with(moderator)
    if result["submitted"] or result["failed"] or result["uncertain"]:
        try:
            notifier.send(
                f"Moderation cycle: {result['submitted']} submitted, {result['failed']} failed before confirmation, "
                f"{result['uncertain']} uncertain."
            )
        except IntegrationError as error:
            logging.warning("Moderation summary notification failed: %s", error)
    return result


def retry_failed(state: JsonState) -> int:
    targets = [target for target in state.targets if target["status"] == "failed"]
    if not targets:
        return 0
    timestamp = utc_now()
    for target in targets:
        target.update(status="pending", updated_at=timestamp, last_error=None)
    state.save()
    return len(targets)


def configure_logging(path: Path) -> None:
    if path.is_symlink():
        raise ConfigurationError("log path must not be a symbolic link")
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise ConfigurationError("log directory must not be accessible by group or others")
    if path.exists():
        if not stat.S_ISREG(path.stat().st_mode):
            raise ConfigurationError("log path must be a regular file")
        path.chmod(0o600)
    else:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler()],
        force=True,
    )
    path.chmod(0o600)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-config", help="validate configuration without making network requests")
    run = subparsers.add_parser("run", help="monitor configured Pages")
    run.add_argument("--once", action="store_true", help="run one monitoring cycle and exit")
    run.add_argument("--apply", action="store_true", help="submit Page UI blocks for pending targets")
    status = subparsers.add_parser("status", help="show local aggregate state without identifiers")
    status.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("DEFENSE_STATE_PATH", ".runtime/reaction-defense-state.json")),
    )
    incomplete = subparsers.add_parser(
        "incomplete", help="list opaque references for interrupted or uncertain actions"
    )
    incomplete.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("DEFENSE_STATE_PATH", ".runtime/reaction-defense-state.json")),
    )
    incomplete.add_argument(
        "--show-identifiers",
        action="store_true",
        help="include sensitive Page and account identifiers for local reconciliation",
    )
    incomplete.add_argument("--confirm", choices=("SHOW_PRIVATE_IDENTIFIERS",))
    retry = subparsers.add_parser("retry-failed", help="return failed pre-completion actions to pending")
    retry.add_argument("--confirm", required=True, choices=("RETRY_FAILED_ACTIONS",))
    retry.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("DEFENSE_STATE_PATH", ".runtime/reaction-defense-state.json")),
    )
    resolve = subparsers.add_parser(
        "resolve-incomplete", help="resolve one reconciled interrupted or uncertain action"
    )
    resolve.add_argument("target_ref")
    resolve.add_argument("outcome", choices=("requeue", "submitted"))
    resolve.add_argument("--confirm", required=True, choices=("RESOLVE_INCOMPLETE_ACTION",))
    resolve.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("DEFENSE_STATE_PATH", ".runtime/reaction-defense-state.json")),
    )
    return parser


def run(settings: Settings, *, once: bool, apply: bool) -> int:
    client = GraphClient(
        settings.graph_version,
        settings.graph_timeout,
        settings.max_edge_pages,
        settings.max_graph_requests,
    )
    notifier = TelegramNotifier(settings.telegram_token, settings.telegram_chat_ids, settings.graph_timeout)
    storage_state = validate_browser_storage(settings)

    async def execute() -> int:
        async with BrowserModerator(settings, storage_state) as browser:
            while True:
                with open_state(settings.state_path) as state:
                    monitoring_result = await run_monitoring_cycle(
                        state, settings, client, browser, notifier
                    )
                    moderation_result = None
                    if apply:
                        moderation_result = await apply_pending_targets(
                            state, settings, notifier, moderator=browser
                        )
                print(
                    json.dumps(
                        {"monitoring": monitoring_result, "moderation": moderation_result},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                if once:
                    moderation_failed = moderation_result and (
                        moderation_result["failed"] or moderation_result["uncertain"]
                    )
                    return (
                        1
                        if monitoring_result["pages_failed"]
                        or monitoring_result["edge_failures"]
                        or moderation_failed
                        else 0
                    )
                await asyncio.sleep(settings.poll_interval)

    try:
        return asyncio.run(execute())
    except (ConfigurationError, OSError):
        raise
    except BrowserAutomationError:
        raise IntegrationError("authorized browser session failed") from None


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in {"status", "incomplete", "retry-failed", "resolve-incomplete"}:
            with open_state(args.state) as state:
                if args.command == "status":
                    result = status_summary(state)
                elif args.command == "incomplete":
                    if args.show_identifiers != (args.confirm == "SHOW_PRIVATE_IDENTIFIERS"):
                        raise ConfigurationError(
                            "--show-identifiers requires --confirm SHOW_PRIVATE_IDENTIFIERS"
                        )
                    result = list_incomplete(state, include_identifiers=args.show_identifiers)
                elif args.command == "retry-failed":
                    result = {"requeued": retry_failed(state)}
                else:
                    result = resolve_incomplete(state, args.target_ref, args.outcome)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        settings = load_settings()
        configure_logging(settings.log_path)
        if args.command == "check-config":
            result = {
                "pages": len(settings.pages),
                "reaction_types": list(settings.reactions),
                "reaction_labels": dict(settings.reaction_labels),
                "monitor_comments": settings.monitor_comments,
                "monitor_ratings": settings.monitor_ratings,
                "max_graph_requests_per_cycle": settings.max_graph_requests,
                "max_reaction_browser_pages_per_cycle": settings.max_browser_pages,
                "max_reaction_actors_per_object": settings.max_reaction_actors,
                "max_moderation_actions_per_run": settings.max_moderation_actions,
                "telegram_enabled": bool(settings.telegram_token),
                "browser_storage_configured": settings.storage_state is not None,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        return run(settings, once=args.once, apply=args.apply)
    except (ConfigurationError, IntegrationError, OSError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
