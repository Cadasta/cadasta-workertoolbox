import unittest
from mock import MagicMock

from cadasta.workertoolbox import utils


class TestUtils(unittest.TestCase):
    def test_extract_followups(self):
        request = MagicMock(
            callbacks=['1', '2', '3'],
            errbacks=['a', 'b', 'c'],
        )
        mock_task = MagicMock(request=request)

        output = utils.extract_followups(mock_task)

        # Assert links and link_errors were extracted
        self.assertEqual(
            output,
            {
                'link': ['1', '2', '3'],
                'link_error': ['a', 'b', 'c'],
            }
        )
        # Assert links were removed from request
        self.assertEqual(mock_task.request.callbacks, None)

    def test_colorformatter(self):
        assert utils.ColorFormatter("%(message)s")
