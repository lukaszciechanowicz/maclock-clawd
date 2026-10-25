"""Playback boundaries that would visibly break the website's motions."""

import unittest

from pipclock.animations import WebsiteAnimations


class PlaybackTests(unittest.TestCase):
    def test_header_wave_reverses_instead_of_jumping_to_the_first_pose(self):
        wave = {"frames": 17, "fps": 12, "mode": "pingpong"}
        ticks = (0, 15, 16, 17, 31, 32, 33)
        self.assertEqual(
            [WebsiteAnimations.frame_index(wave, tick / 12) for tick in ticks],
            [0, 15, 16, 15, 1, 0, 1],
        )

    def test_walking_does_not_replay_the_entry_poses_at_each_step_cycle(self):
        walk = {"frames": 28, "fps": 12, "loop": [8, 24]}
        ticks = (0, 1, 15, 16, 31, 32)
        self.assertEqual(
            [WebsiteAnimations.frame_index(walk, tick / 12) for tick in ticks],
            [8, 9, 23, 8, 23, 8],
        )


if __name__ == "__main__":
    unittest.main()
