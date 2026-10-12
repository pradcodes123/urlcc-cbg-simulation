
import unittest

from src.urllc import preset_config, generate_urllc_traffic


class TestURLLCArrivalPatterns(unittest.TestCase):
    def setUp(self):
        self.config = preset_config("medium", simulation_time=20)

    def test_same_event_count_across_patterns(self):
        patterns = ("poisson", "evenly_spaced", "bursty")
        counts = [
            len(generate_urllc_traffic(self.config, 42, p))
            for p in patterns
        ]
        self.assertEqual(counts, [4, 4, 4])

    def test_demands_matched_by_event_id(self):
        patterns = ("poisson", "evenly_spaced", "bursty")
        events_by_pattern = {
            p: {
                e.event_id: e.resource_demand
                for e in generate_urllc_traffic(self.config, 42, p)
            }
            for p in patterns
        }
        self.assertEqual(
            events_by_pattern["poisson"],
            events_by_pattern["evenly_spaced"],
        )
        self.assertEqual(
            events_by_pattern["poisson"],
            events_by_pattern["bursty"],
        )

    def test_generation_is_reproducible(self):
        for pattern in ("poisson", "evenly_spaced", "bursty"):
            self.assertEqual(
                generate_urllc_traffic(self.config, 123, pattern),
                generate_urllc_traffic(self.config, 123, pattern),
            )

    def test_unknown_pattern_rejected(self):
        with self.assertRaises(ValueError):
            generate_urllc_traffic(self.config, 42, "invalid")


if __name__ == "__main__":
    unittest.main()
