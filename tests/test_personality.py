import os
import random
import sys
import unittest
from dataclasses import FrozenInstanceError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from personality import PERSONALITIES, Personality, get_personality


class PersonalityTests(unittest.TestCase):
    def test_each_character_has_distinct_core_line_banks(self) -> None:
        core_triggers = (
            "game_start",
            "player_blunder",
            "player_good_move",
            "bot_capture",
            "checkmate_win",
            "checkmate_loss",
            "idle",
        )
        self.assertEqual(set(PERSONALITIES), {"rookie", "hustler", "professor", "martin"})
        for bot_id, personality in PERSONALITIES.items():
            with self.subTest(bot_id=bot_id):
                for trigger in core_triggers:
                    self.assertGreaterEqual(len(personality.lines[trigger]), 6)
                    self.assertLessEqual(len(personality.lines[trigger]), 10)

    def test_say_uses_the_requested_pool_with_seeded_randomness(self) -> None:
        personality = PERSONALITIES["rookie"]
        line = personality.say("bot_capture", rng=random.Random(7))
        self.assertIn(line, personality.lines["bot_capture"])

    def test_say_falls_back_to_idle_for_an_unknown_trigger(self) -> None:
        personality = PERSONALITIES["martin"]
        line = personality.say("not-a-trigger", rng=random.Random(3))
        self.assertIn(line, personality.lines["idle"])

    def test_say_avoids_an_immediate_repeat(self) -> None:
        personality = PERSONALITIES["professor"]
        previous = personality.lines["bot_capture"][0]
        for seed in range(20):
            with self.subTest(seed=seed):
                self.assertNotEqual(
                    personality.say("bot_capture", rng=random.Random(seed), previous=previous),
                    previous,
                )

    def test_empty_personality_returns_none(self) -> None:
        personality = Personality("quiet", "Quiet", "novice", 1, 0.0, "quiet.png")
        self.assertIsNone(personality.say("idle"))

    def test_unknown_bot_defaults_to_professor(self) -> None:
        self.assertIs(get_personality("missing"), PERSONALITIES["professor"])

    def test_personality_metadata_is_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            PERSONALITIES["rookie"].label = "Changed"


if __name__ == "__main__":
    unittest.main()
