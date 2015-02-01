import unittest
import os
import sys
import re
import time

import qdns

class MockSocketModule(object):
    @classmethod
    def is_addr(self, what):
        if ':' in what:
            return 6
        elif re.match(ur'^[0-9.]{7,15}$', what):
            return 4
        else:
            return False

    @classmethod
    def getaddrinfo(self, host, port, family = None, socktype = None, proto = None, flags = None):
        time.sleep(2)
        addr = None
        if self.is_addr(host) == 6:
            addr = (host, port, 0, 0)
        elif self.is_addr(host) == 4:
            addr = (host, port)
        else:
            addr = ('82.94.164.162', port)
        return [(0, 0, 0, '', addr)]

    @classmethod
    def gethostbyname(self, hostname):
        time.sleep(2)
        return hostname if self.is_addr(hostname) else '82.94.164.162'

    @classmethod
    def gethostbyname_ex(self, hostname):
        time.sleep(2)
        return (hostname, [], [hostname if self.is_addr(hostname) else '82.94.164.162'])

    @classmethod
    def gethostbyaddr(self, ip_address):
        time.sleep(2)
        return ('python.org', [], [ip_address])

class TestQDNS(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestQDNS, self).__init__(*args, **kwargs)
        qdns.socket = MockSocketModule

    def setUp(self):
        self.received = []

    def tearDown(self):
        self.received = []

    def _receive(self, name, **kwargs):
        self.received.append(name)

    def test_getaddrinfo_host(self):
        qdns.configure()
        qdns.getaddrinfo('python.org', self._receive)
        qdns.stop(True)
        self.assertEquals('82.94.164.162', self.received[0][0][4][0])

    def test_getaddrinfo_v4(self):
        qdns.configure()
        qdns.getaddrinfo('1.2.3.4', self._receive)
        qdns.stop(True)
        self.assertEquals('1.2.3.4', self.received[0][0][4][0])

    def test_getaddrinfo_v6(self):
        qdns.configure()
        qdns.getaddrinfo('::1', self._receive)
        qdns.stop(True)
        self.assertEquals('::1', self.received[0][0][4][0])

    def test_gethostbyname_host(self):
        qdns.configure()
        qdns.gethostbyname('python.org', self._receive)
        qdns.stop(True)
        self.assertEquals('82.94.164.162', self.received[0])

    def test_gethostbyname_v4(self):
        qdns.configure()
        qdns.gethostbyname('1.2.3.4', self._receive)
        qdns.stop(True)
        self.assertEquals('1.2.3.4', self.received[0])

    def test_gethostbyname_v6(self):
        qdns.configure()
        qdns.gethostbyname('::1', self._receive)
        qdns.stop(True)
        self.assertEquals('::1', self.received[0])

    def test_gethostbyname_ex_host(self):
        qdns.configure()
        qdns.gethostbyname_ex('python.org', self._receive)
        qdns.stop(True)
        self.assertEquals('82.94.164.162', self.received[0][2][0])

    def test_gethostbyname_ex_v4(self):
        qdns.configure()
        qdns.gethostbyname_ex('1.2.3.4', self._receive)
        qdns.stop(True)
        self.assertEquals('1.2.3.4', self.received[0][2][0])

    def test_gethostbyname_ex_v6(self):
        qdns.configure()
        qdns.gethostbyname_ex('::1', self._receive)
        qdns.stop(True)
        self.assertEquals('::1', self.received[0][2][0])

    def test_gethostbyaddr(self):
        qdns.configure()
        qdns.gethostbyaddr('82.94.164.162', self._receive)
        qdns.stop(True)
        self.assertEquals('python.org', self.received[0][0])

if __name__ == '__main__':
    unittest.main()