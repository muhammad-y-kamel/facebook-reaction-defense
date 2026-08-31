"""Playwright boundary for reaction collection and Page-scoped moderation."""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

if TYPE_CHECKING:
    from reaction_defense import PageConfig, Settings

NUMERIC_ID = re.compile(r"[0-9]{1,64}\Z")
GRAPH_ID = re.compile(r"[A-Za-z0-9_:-]{1,200}\Z")
FACEBOOK_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "mbasic.facebook.com"}
REACTION_BROWSER_PATH = "/ufi/reaction/profile/browser"


class BrowserAutomationError(RuntimeError):
    """A safe browser-automation failure message."""


class ReactionCollectionError(BrowserAutomationError):
    """Reaction actors could not be collected safely."""


class BrowserPageBudgetExceeded(ReactionCollectionError):
    """The configured reaction-browser page budget was exhausted."""


class ModerationError(BrowserAutomationError):
    """A safe browser-moderation failure message."""


class ModerationOutcomeUncertain(ModerationError):
    """The confirmation control may have received the action."""

    outcome_uncertain = True


class BrowserModerator:
    def __init__(self, settings: Settings, storage_state: dict[str, object] | None = None):
        self.settings = settings
        self.storage_state = storage_state
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.active_page_id = None
        self.collection_pages_remaining = settings.max_browser_pages

    async def __aenter__(self):
        if self.storage_state is None:
            raise ModerationError("validated browser storage is required")
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.firefox.launch(headless=self.settings.browser_headless)
            self.context = await self.browser.new_context(storage_state=self.storage_state)
            self.page = await self.context.new_page()
            return self
        except Exception as error:
            await self._close()
            raise ModerationError("could not start the authorized browser session") from error

    async def __aexit__(self, *_):
        await self._close()

    async def _close(self) -> None:
        for resource in (self.context, self.browser):
            if resource is not None:
                try:
                    await resource.close()
                except Exception:
                    pass
        if self.playwright is not None:
            try:
                await self.playwright.stop()
            except Exception:
                pass

    def reset_collection_budget(self, maximum: int) -> None:
        self.collection_pages_remaining = maximum

    @staticmethod
    def _reaction_page_matches(url: str, object_id: str) -> bool:
        try:
            parsed = urlsplit(url)
            query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
            port = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == "https"
            and parsed.hostname == "mbasic.facebook.com"
            and port in (None, 443)
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and parsed.path.rstrip("/").casefold() == REACTION_BROWSER_PATH
            and query.get("ft_ent_identifier") == [object_id]
        )

    @staticmethod
    def _profile_id(href: str, base_url: str) -> str | None:
        try:
            parsed = urlsplit(urljoin(base_url, href))
            query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
            port = parsed.port
        except ValueError:
            return None
        actor_id = query.get("id")
        if (
            parsed.scheme != "https"
            or parsed.hostname not in FACEBOOK_HOSTS
            or port not in (None, 443)
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.path.rstrip("/").casefold() != "/profile.php"
            or not actor_id
            or len(actor_id) != 1
            or not NUMERIC_ID.fullmatch(actor_id[0])
        ):
            return None
        return actor_id[0]

    async def iter_reactors(self, object_id: str):
        if not GRAPH_ID.fullmatch(object_id):
            raise ReactionCollectionError("content identifier is invalid")
        labels = {
            unicodedata.normalize("NFKC", label).casefold(): reaction
            for reaction, label in self.settings.reaction_labels
        }
        icon_markers = dict(self.settings.reaction_icon_markers)
        url = (
            f"https://mbasic.facebook.com{REACTION_BROWSER_PATH}/?"
            f"{urlencode({'ft_ent_identifier': object_id})}"
        )
        actors: set[tuple[str, str]] = set()
        actor_ids: set[str] = set()
        visited = set()

        try:
            for _ in range(self.settings.max_edge_pages):
                if self.collection_pages_remaining <= 0:
                    raise BrowserPageBudgetExceeded(
                        "reaction browser page budget was exhausted for this Page"
                    )
                self.collection_pages_remaining -= 1
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                if not self._reaction_page_matches(self.page.url, object_id) or self.page.url in visited:
                    raise ReactionCollectionError("reaction browser navigation could not be confirmed")
                visited.add(self.page.url)

                items = self.page.locator("li._5i_q")
                for index in range(min(await items.count(), 500)):
                    item = items.nth(index)
                    matches = set()
                    images = item.locator("img")
                    for image_index in range(min(await images.count(), 10)):
                        label = await images.nth(image_index).get_attribute("alt")
                        source = await images.nth(image_index).get_attribute("src")
                        if isinstance(label, str) and isinstance(source, str):
                            reaction = labels.get(
                                unicodedata.normalize("NFKC", label).strip().casefold()
                            )
                            if reaction and icon_markers[reaction] in source:
                                matches.add(reaction)
                    if len(matches) > 1:
                        raise ReactionCollectionError("reaction row matched more than one configured label")
                    if not matches:
                        continue
                    reaction = matches.pop()

                    links = item.locator("a[href*='profile.php']")
                    for link_index in range(min(await links.count(), 10)):
                        href = await links.nth(link_index).get_attribute("href")
                        actor_id = self._profile_id(href, self.page.url) if isinstance(href, str) else None
                        if actor_id:
                            pair = (reaction, actor_id)
                            if pair not in actors:
                                actors.add(pair)
                                actor_ids.add(actor_id)
                                yield pair
                            break
                    if len(actor_ids) >= self.settings.max_reaction_actors:
                        return

                more = self.page.get_by_text(self.settings.reaction_more_text, exact=True)
                if not await more.count():
                    return
                href = await more.last.get_attribute("href")
                next_url = urljoin(self.page.url, href) if isinstance(href, str) else ""
                if not self._reaction_page_matches(next_url, object_id):
                    raise ReactionCollectionError("reaction browser pagination could not be confirmed")
                url = next_url
        except ReactionCollectionError:
            raise
        except Exception as error:
            raise ReactionCollectionError("reaction actor collection failed") from error
        raise ReactionCollectionError("reaction browser pagination exceeded the configured limit")

    async def _current_identity_matches(self, page_config: PageConfig, timeout: int) -> bool:
        try:
            await self.page.goto("https://www.facebook.com/me", wait_until="domcontentloaded", timeout=30_000)
            current = urlsplit(self.page.url)
            expected = urlsplit(page_config.url)
            current_query = parse_qs(current.query)
            current_path = current.path.rstrip("/").casefold()
            expected_path = expected.path.rstrip("/").casefold()
            identity_matches = (
                current.scheme == "https"
                and current.hostname in {"facebook.com", "www.facebook.com", "m.facebook.com"}
                and (
                    (current_path == "/profile.php" and current_query.get("id") == [page_config.id])
                    or (expected_path not in {"", "/profile.php"} and current_path == expected_path)
                )
            )
            if not identity_matches:
                return False
            await self.page.get_by_text(page_config.name, exact=True).first.wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    async def _switch_to_page(self, page_config: PageConfig) -> None:
        self.active_page_id = None
        try:
            await self.page.goto(page_config.url, wait_until="domcontentloaded", timeout=60_000)
            if await self._current_identity_matches(page_config, 5_000):
                self.active_page_id = page_config.id
                return

            await self.page.goto(page_config.url, wait_until="domcontentloaded", timeout=60_000)
            switch = self.page.get_by_text(self.settings.switch_text, exact=True).first
            await switch.wait_for(state="visible", timeout=15_000)
            await switch.click()

            try:
                confirmation = self.page.locator('[role="dialog"]').get_by_text(
                    self.settings.switch_text, exact=True
                ).first
                await confirmation.wait_for(state="visible", timeout=8_000)
                await confirmation.click()
            except Exception:
                pass

            if not await self._current_identity_matches(page_config, 30_000):
                raise ModerationError("Page identity could not be confirmed")
            self.active_page_id = page_config.id
        except ModerationError:
            raise
        except Exception as error:
            raise ModerationError("Page identity switch failed") from error

    async def _open_profile_menu(self):
        clicked = False
        try:
            menu_button = self.page.get_by_role(
                "button", name=self.settings.profile_menu_text, exact=True
            ).first
            await menu_button.wait_for(state="visible", timeout=5_000)
            await menu_button.click()
            clicked = True
        except Exception:
            try:
                svgs = self.page.locator("main").first.locator("svg")
                for index in range(min(await svgs.count(), 250)):
                    svg = svgs.nth(index)
                    markup = await svg.inner_html()
                    if all(marker in markup for marker in ('cx="12"', 'cx="19.5"', 'cx="4.5"')):
                        await svg.click()
                        clicked = True
                        break
            except Exception as error:
                raise ModerationError("profile action menu could not be inspected") from error
        if not clicked:
            raise ModerationError("profile action menu was not found")
        try:
            menu = self.page.locator('[role="menu"]:visible').last
            await menu.wait_for(state="visible", timeout=5_000)
            return menu
        except Exception as error:
            raise ModerationError("profile action menu did not open") from error

    async def block_account(self, page_config: PageConfig, actor_id: str) -> None:
        if not NUMERIC_ID.fullmatch(actor_id):
            raise ModerationError("target identifier is invalid")
        if self.active_page_id != page_config.id or not await self._current_identity_matches(
            page_config, 5_000
        ):
            await self._switch_to_page(page_config)
        if self.active_page_id != page_config.id:
            raise ModerationError("Page identity was not confirmed")

        try:
            await self.page.goto(
                f"https://www.facebook.com/profile.php?id={actor_id}",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            target = urlsplit(self.page.url)
            try:
                target_port = target.port
                target_query = parse_qs(
                    target.query, keep_blank_values=True, strict_parsing=True
                )
            except ValueError:
                raise ModerationError("target profile could not be confirmed") from None
            if not (
                target.scheme == "https"
                and target.hostname in {"facebook.com", "www.facebook.com", "m.facebook.com"}
                and target_port in (None, 443)
                and not target.username
                and not target.password
                and not target.fragment
                and target.path.rstrip("/").casefold() == "/profile.php"
                and set(target_query) == {"id"}
                and target_query["id"] == [actor_id]
            ):
                raise ModerationError("target profile could not be confirmed")
            menu = await self._open_profile_menu()
            block = menu.get_by_text(self.settings.block_text, exact=True).first
            await block.wait_for(state="visible", timeout=10_000)
            await block.click()
            dialog = self.page.locator('[role="dialog"]:visible').last
            await dialog.wait_for(state="visible", timeout=10_000)
            confirmation = dialog.get_by_text(self.settings.confirm_text, exact=True).first
            await confirmation.wait_for(state="visible", timeout=10_000)
            try:
                await confirmation.click()
            except Exception as error:
                raise ModerationOutcomeUncertain("block confirmation outcome is uncertain") from error
        except ModerationError:
            raise
        except Exception as error:
            raise ModerationError("block submission did not complete") from error
