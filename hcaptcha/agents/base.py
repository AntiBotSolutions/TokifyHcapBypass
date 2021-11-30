from typing import Literal
from urllib.parse import urlencode
import json
import time

class Agent:
    def __init__(self):
        self._epoch_offset = 0

    def get_screen_properties(self) -> dict:
        """Returns dict representing `window.screen`."""
        return {}
    
    def get_navigator_properties(self) -> dict:
        """Returns dict representing `window.navigator`."""
        return {}

    def epoch(self, ms: bool = True):
        """Returns current timestamp, with offset added."""
        t = time.time() * 1000
        t += self._epoch_offset
        if not ms: t /= 1000
        return int(t)

    def epoch_travel(self, delta: float, ms: bool = True):
        """Offsets the epoch returned by `Agent.epoch`."""
        if not ms: delta *= 1000
        self._epoch_offset += delta

    def epoch_wait(self):
        """Resets the epoch offset."""
        if self._epoch_offset > 0:
            time.sleep(self._epoch_offset/1000)
        self._epoch_offset = 0

    def json_encode(self, data: Literal) -> str:
        """Simulates a browser's way of JSON encoding."""
        return json.dumps(data, separators=(",", ":"))

    def url_encode(self, data: dict) -> str:
        """Simulates a browser's way of URL encoding."""
        return urlencode(data)
    
    def format_headers(
        self,
        url: str,
        body: bytes = None,
        headers: dict = {},
        origin_url: str = None,
        sec_site: str = "cross-site",
        sec_mode: str = "cors",
        sec_dest: str = "empty"
    ) -> dict:
        """Formats headers in a browser-like way."""
        return headers