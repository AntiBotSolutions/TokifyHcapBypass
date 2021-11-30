from ..challenges import Challenge
from .exceptions import *
from collections import Mapping
from hashlib import sha1
from typing import Union
import random
import re
import redis

question_patterns = (
    re.compile("Please click each image containing a[n]? (.+)"),
)

class Solver:
    def __init__(
        self,
        database: Union[redis.Redis, Mapping],
        min_answers: int = 3
        ):
        """Used for solving hCaptcha challenges.
        
        :param database: :class:`Redis` or :class:`Mapping` object to be used for storing tile IDs and counts.
        :param min_answers: minimum amount of answers to be submitted for a challenge."""
        self._database = database
        self._min_answers = min_answers

    def solve(self, challenge: Challenge) -> str:
        """Solves and returns solution key of given challenge.
        Utilizes RNG and cached data for solving."""
        # Return solution key if challenge is already solved.
        if challenge.token: return challenge.token

        # The only type of challenge supported right now
        # is 'image_label_binary'.
        if challenge.mode != "image_label_binary":
            raise UnsupportedChallenge(
                f"Unsupported challenge mode: '{challenge.mode}'")

        # Extract keyword from question.
        question = challenge.question["en"]
        keyword = None

        for pattern in question_patterns:
            if (m := pattern.match(question)):
                keyword = m.group(1).lower().rstrip(".")
                break

        if not keyword:
            raise UnsupportedChallenge(
                f"Unsupported challenge question: '{question}'")
        
        # Assign custom IDs to tiles ('keyword|image hash').
        for tile in challenge.tiles:
            image = tile.get_image(raw=True)
            image_hash = sha1(image).hexdigest()
            tile.custom_id = f"{keyword}|{image_hash}"
            tile.score = self._get_tile_score(tile)
            tile.selected = False

        # Sort tiles according to their score,
        # or a random float between 0 - 0.9 for RNG.
        challenge.tiles.sort(
            key=lambda tile: tile.score or random.uniform(0, 0.9),
            reverse=True)
        
        # Select first <min_answers> tiles, or more
        # if >0 score tasks are greater.
        for index in range(max(
                self._min_answers,
                len([1 for tile in challenge.tiles if tile.score >= 1])
            )):
            tile = challenge.tiles[index]
            tile.selected = True
            challenge.answer(tile)

        challenge.submit()

        # If no error is raised past this point, the answers
        # can be assumed correct.

        # Increment score of selected tiles.
        for tile in challenge.tiles:
            if not tile.selected: continue
            self._incr_tile_score(tile, 1)
        
        # Return solution key.
        return challenge.token

    def _get_tile_score(self, tile):
        if isinstance(self._database, redis.Redis):
            return int(self._database.get(tile.custom_id) or 0)

        elif isinstance(self._database, Mapping):
            return self._database.get(tile.custom_id, 0)

    def _incr_tile_score(self, tile, delta):
        if isinstance(self._database, redis.Redis):
            self._database.incrby(tile.custom_id, delta)

        elif isinstance(self._database, Mapping):
            prev_value = self._database.get(tile.custom_id, 0)
            self._database[tile.custom_id] = prev_value + delta