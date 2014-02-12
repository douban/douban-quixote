
import sys
import os.path
import unittest


p = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, p)



class BaseTestCase(unittest.TestCase):

    def create_publisher(self, ui_cls, conf=None):
        import quixote.publish
        quixote.publish._publisher = None
        publisher = quixote.publish.Publisher(ui_cls())
        if not conf:
            conf = {}
        publisher.configure(**conf)
        return publisher
