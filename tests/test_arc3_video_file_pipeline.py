import unittest

from arc3.video_file_pipeline import clip_windows


class VideoFilePipelineTests(unittest.TestCase):
    def test_five_second_non_overlapping_windows(self):
        self.assertEqual(
            clip_windows(12.4, clip_seconds=5.0),
            [(0.0, 5.0), (5.0, 10.0)],
        )

    def test_strided_windows(self):
        self.assertEqual(
            clip_windows(7.5, clip_seconds=5.0, stride_seconds=2.5),
            [(0.0, 5.0), (2.5, 7.5)],
        )

    def test_exact_length_clip_is_included(self):
        self.assertEqual(clip_windows(5.0), [(0.0, 5.0)])

    def test_invalid_clip_length_rejected(self):
        with self.assertRaises(ValueError):
            clip_windows(10.0, clip_seconds=0)

    def test_invalid_stride_rejected(self):
        with self.assertRaises(ValueError):
            clip_windows(10.0, stride_seconds=-1)


if __name__ == "__main__":
    unittest.main()
