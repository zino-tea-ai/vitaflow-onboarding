"""
示例测试文件
"""
import unittest


class TestExample(unittest.TestCase):
    """示例测试类"""

    def test_addition(self):
        """测试加法"""
        self.assertEqual(1 + 1, 2)

    def test_string(self):
        """测试字符串"""
        self.assertEqual("hello".upper(), "HELLO")

    def test_list(self):
        """测试列表"""
        items = [1, 2, 3]
        self.assertIn(2, items)
        self.assertEqual(len(items), 3)


if __name__ == "__main__":
    unittest.main()
