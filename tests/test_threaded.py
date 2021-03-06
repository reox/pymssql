import sys
import threading
import time
import unittest

from nose.plugins.attrib import attr

from _mssql import MSSQLDatabaseException

from .helpers import mssqlconn, StoredProc


error_sproc = StoredProc(
    "pymssqlErrorThreadTest",
    args=(),
    body="SELECT unknown_column FROM unknown_table")


class TestingThread(threading.Thread):
    def __init__(self):
        super(TestingThread, self).__init__()
        self.results = []
        self.exc = None

    def run(self):
        try:
            with mssqlconn() as mssql:
                for i in range(0, 1000):
                    num = mssql.execute_scalar('SELECT %d', (i,))
                    assert num == i
                    self.results.append(num)
        except Exception as exc:
            self.exc = exc


class TestingErrorThread(TestingThread):
    def run(self):
        try:
            with mssqlconn() as mssql:
                mssql.execute_query('SELECT unknown_column')
        except Exception as exc:
            self.exc = exc


class SprocTestingErrorThread(TestingThread):
    def run(self):
        try:
            with mssqlconn() as mssql:
                error_sproc.execute(mssql=mssql)
        except Exception as exc:
            self.exc = exc


class ThreadedTests(unittest.TestCase):
    def run_threads(self, num, thread_class):
        threads = [thread_class() for _ in range(num)]
        for thread in threads:
            thread.start()

        results = []
        exceptions = []

        while len(threads) > 0:
            sys.stdout.write(".")
            sys.stdout.flush()
            for thread in threads:
                if not thread.is_alive():
                    threads.remove(thread)
                if thread.results:
                    results.append(thread.results)
                if thread.exc:
                    exceptions.append(thread.exc)
            time.sleep(5)

        sys.stdout.write(" ")
        sys.stdout.flush()

        return results, exceptions

    @attr('slow')
    def testThreadedUse(self):
        results, exceptions = self.run_threads(
            num=50,
            thread_class=TestingThread)
        self.assertEqual(len(exceptions), 0)
        for result in results:
            self.assertEqual(result, list(range(0, 1000)))

    @attr('slow')
    def testErrorThreadedUse(self):
        results, exceptions = self.run_threads(
            num=2,
            thread_class=TestingErrorThread)
        self.assertEqual(len(exceptions), 2)
        for exc in exceptions:
            self.assertEqual(type(exc), MSSQLDatabaseException)

    @attr('slow')
    def testErrorSprocThreadedUse(self):
        with error_sproc.create():
            results, exceptions = self.run_threads(
                num=5,
                thread_class=SprocTestingErrorThread)
        self.assertEqual(len(exceptions), 5)
        for exc in exceptions:
            self.assertEqual(type(exc), MSSQLDatabaseException)


suite = unittest.TestSuite()
suite.addTest(unittest.makeSuite(ThreadedTests))

if __name__ == '__main__':
    unittest.main()
