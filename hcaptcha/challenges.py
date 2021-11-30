from .agents import Agent, random_agent
from .constants import *
from .curves import gen_mouse_movements
from .exceptions import *
from .http_ import HTTPClient
from .models import Tile
from .proofs import get_proof
from .structures import EventRecorder
from .utils import random_widget_id, latest_version_id, hostname_from_url
from random import randint
from typing import Iterator, List, Union
import json
import ssl
import zlib

class Challenge:
    _version_id = latest_version_id()
    _default_ssl_context = ssl.create_default_context()

    id: str
    token: str
    config: dict
    mode: str
    question: dict
    tiles: List[Tile]

    def __init__(
        self,
        site_key: str,
        site_url: str,
        data: Union[dict, None] = None,
        agent: Agent = None,
        http_client: HTTPClient = None,
        **http_kwargs
    ):
        """Represents a hCaptcha challenge.

        :param site_key: `data-sitekey` attr. of the target website.
        :param site_url: url of the page where the captcha is visible on the target website.
        :param data: (optional) Mapping of custom form fields to be passed to hCaptcha.
        :param agent: (optional) :class:`Agent` to be used for simulating browser properties. Defaults to :class:`ChromeAgent`.
        :param http_client: (optional) :class:`HTTPClient` to be used when sending requests.
        :param **http_kwargs: (optional) Arguments to be used for constructing a :class:`HTTPClient` when one isn't provided.
        """
        self._site_key = site_key
        self._site_url = site_url
        self._site_hostname = hostname_from_url(site_url)
        self._custom_data = data or {}
        self._widget_id = random_widget_id()
        self._proof_data = None
        self._answers = []

        self._agent = agent or random_agent()
        self._http_client = http_client or HTTPClient(**http_kwargs)

        self.id = None
        self.token = None
        self.config = None
        self.mode = None
        self.question = None
        self.tiles = []

        self._agent.epoch_travel(-10)
        self._setup_frames()
        self._validate_config()
        self._get_captcha()
        self._frame.set_data("dct", self._frame._manifest["st"])

    def __iter__(self) -> Iterator[Tile]:
        """Iterates over the challenge's tiles."""
        if not self.tiles: return
        yield from self.tiles

    def close(self) -> None:
        self._http_client.clear()

    def answer(self, tile: Tile) -> None:
        """Adds :class:`Tile` to list of answers.
        
        :param tile: the :class:`Tile` to be marked as an answer.
        """
        assert isinstance(tile, Tile), "Not a tile object."
        self._answers.append(tile)
    
    def submit(self) -> str:
        """Submits list of answers.
        Returns solution token if successful.
        """
        if self.token: return self.token
    
        self._simulate_mouse_events()
        self._agent.epoch_wait()
        data = self._request(
            method="POST",
            url=f"https://hcaptcha.com/checkcaptcha/{self.id}"
                f"?s={self._site_key}",
            headers={
                "Accept": "*/*",
                "Content-type": "application/json;charset=UTF-8"
            },
            body=self._agent.json_encode({
                "v": self._version_id,
                "job_mode": self.mode,
                "answers": {
                    tile.id: "true" if tile in self._answers else "false"
                    for tile in self.tiles
                },
                "serverdomain": self._site_hostname,
                "sitekey": self._site_key,
                "motionData": self._agent.json_encode({
                    **self._frame.get_data(),
                    "topLevel": self._top.get_data(),
                    "v": 1
                }),
                "n": self._get_proof(),
                "c": self._agent.json_encode(self._proof_data)
            }),
            origin_url="https://newassets.hcaptcha.com/",
            sec_site="same-site",
            sec_mode="cors",
            sec_dest="empty"
        )

        if not data.get("pass"):
            raise RequestRejected("Submit request was rejected.")

        self.token = data["generated_pass_UUID"]
        return self.token

    def _validate_config(self):
        data = self._request(
            method="GET",
            url="https://hcaptcha.com/checksiteconfig"
               f"?host={self._site_hostname}&sitekey={self._site_key}"
                "&sc=1&swa=1",
            headers={
                "Cache-Control": "no-cache",
                "Content-type": "application/json; charset=utf-8"
            },
            origin_url="https://newassets.hcaptcha.com/",
            sec_site="same-site",
            sec_mode="cors",
            sec_dest="empty"
        )

        if not data.get("pass"):
            raise RequestRejected(
                "Validation request failed. Are you sure the site key is valid?")

    def _get_captcha(self):
        print("Test")
        data = self._request(
            method="POST",
            url="https://hcaptcha.com/getcaptcha"
               f"?s={self._site_key}",
            headers={
                "Accept": "application/json",
                "Content-type": "application/x-www-form-urlencoded"
            },
            body=self._agent.url_encode({
                "v": self._version_id,
                "sitekey": self._site_key,
                "host": self._site_hostname,
                "hl": "en",
                "motionData": self._agent.json_encode({
                    "v": 1,
                    **self._frame.get_data(),
                    "topLevel": self._top.get_data(),
                    "session": {},
                    "widgetList": [self._widget_id],
                    "widgetId": self._widget_id,
                    "href": self._site_url,
                    "prev": {
                        "escaped": False,
                        "passed": False,
                        "expiredChallenge": False,
                        "expiredResponse": False
                    }
                }),
                **self._custom_data,
                "n": self._get_proof(),
                "c": self._agent.json_encode(self._proof_data)
            }),
            origin_url="https://newassets.hcaptcha.com/",
            sec_site="same-site",
            sec_mode="cors",
            sec_dest="empty"
        )
        
        if data.get("pass"):
            self.token = data["generated_pass_UUID"]
            return

        if data.get("success") == False:
            raise RequestRejected(
                "Challenge creation request was rejected.")
        
        self.id = data["key"]
        self.config = data["request_config"]
        self.mode = data["request_type"]
        self.question = data["requester_question"]
        self.tiles = [
            Tile(id=info["task_key"],
                 image_url=info["datapoint_uri"],
                 index=index,
                 challenge=self)
            for index, info in enumerate(data["tasklist"])
        ]

    def _get_tile_image(self, image_url):
        data = self._request(
            method="GET",
            url=image_url,
            headers={"Accept-Encoding": "gzip, deflate, br"}
        )
        return data

    def _request(
        self,
        method: str,
        url: str,
        headers: dict = {},
        body: bytes = None,
        origin_url: str = None,
        sec_site: str = "cross-site",
        sec_mode: str = "cors",
        sec_dest: str = "empty"
    ):
        headers = self._agent.format_headers(
            url=url,
            body=body,
            headers=headers,
            origin_url=origin_url,
            sec_site=sec_site,
            sec_mode=sec_mode,
            sec_dest=sec_dest)

        resp = self._http_client.request(method, url, headers, body)
        data = resp.read()

        if (encoding := resp.headers.get("content-encoding")):
            if encoding == "gzip":
                data = zlib.decompress(data, 16 + zlib.MAX_WBITS)

        if resp.status > 403:
            raise RequestRejected(
                f"Unrecognized status code: {resp.status}: {resp.reason}")

        if resp.headers["content-type"].startswith("application/json"):
            data = json.loads(data)
            if "c" in data:
                self._proof_data = data["c"]
            
        return data

    def _get_proof(self):
        if not self._proof_data: return "null"
        return get_proof(
            self._proof_data["type"],
            self._proof_data["req"])

    def _setup_frames(self):
        self._top = EventRecorder(agent=self._agent)
        self._top.record()
        self._top.set_data("dr", "") # referrer
        self._top.set_data("inv", False)
        self._top.set_data("sc", self._agent.get_screen_properties())
        self._top.set_data("nv", self._agent.get_navigator_properties())
        self._top.set_data("exec", False)
        self._agent.epoch_travel(randint(200, 400))
        self._frame = EventRecorder(agent=self._agent)
        self._frame.record()

    def _simulate_mouse_events(self):
            total_pages = max(1, int(len(self.tiles) / TILES_PER_PAGE))
            cursor_pos = (randint(1, 5), randint(300, 350))

            for page in range(total_pages):
                page_tiles = self.tiles[page * TILES_PER_PAGE : (page + 1) * TILES_PER_PAGE]
                for tile in page_tiles:
                    if not tile in self._answers:
                        continue
                    tile_pos = (
                        (TILE_IMAGE_SIZE[0] * int(tile.index % TILES_PER_ROW))
                            + TILE_IMAGE_PADDING[0] * int(tile.index % TILES_PER_ROW)
                            + randint(10, TILE_IMAGE_SIZE[0])
                            + TILE_IMAGE_START_POS[0],
                        (TILE_IMAGE_SIZE[1] * int(tile.index / TILES_PER_ROW))
                            + TILE_IMAGE_PADDING[1] * int(tile.index / TILES_PER_ROW)
                            + randint(10, TILE_IMAGE_SIZE[1])
                            + TILE_IMAGE_START_POS[1],
                    )
                    for event in gen_mouse_movements(cursor_pos, tile_pos, self._agent,
                            offsetBoundaryX=0, offsetBoundaryY=0, leftBoundary=0,
                            rightBoundary=FRAME_SIZE[0], upBoundary=FRAME_SIZE[1],
                            downBoundary=0):
                        self._frame.record_event("mm", event)
                    # TODO: add time delay for mouse down and mouse up
                    self._frame.record_event("md", event)
                    self._frame.record_event("mu", event)
                    cursor_pos = tile_pos
                
                # click verify/next/skip btn
                btn_pos = (
                    VERIFY_BTN_POS[0] + randint(5, 50),
                    VERIFY_BTN_POS[1] + randint(5, 15),
                )
                for event in gen_mouse_movements(cursor_pos, btn_pos, self._agent,
                        offsetBoundaryX=0, offsetBoundaryY=0, leftBoundary=0,
                        rightBoundary=FRAME_SIZE[0], upBoundary=FRAME_SIZE[1],
                        downBoundary=0):
                    self._frame.record_event("mm", event)
                # TODO: add time delay for mouse down and mouse up
                self._frame.record_event("md", event)
                self._frame.record_event("mu", event)
                cursor_pos = btn_pos
