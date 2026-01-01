import unittest


class TestSample(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(1 + 1, 2)

    def test_string(self):
        self.assertEqual("hello".upper(), "HELLO")


if __name__ == "__main__":
    unittest.main()
