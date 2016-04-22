import os

from django.test.runner import DiscoverRunner
from django.test.runner import reorder_suite

from junorunner.extended_runner import TextTestRunner

from unittest.suite import TestSuite


class JunoDiscoverRunner(DiscoverRunner):
    """
    The only real difference between this and the standard DiscoverRunner in Django 1.6+
    is the use of the custom TextTestRunner, which we hook in via run_suite()
    """

    def run_suite(self, suite, **kwargs):
        return TextTestRunner(
            verbosity=self.verbosity,
            failfast=self.failfast,
            total_tests=len(suite._tests),
            slow_test_count=self.slow_test_count
        ).run(suite)

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        suite = TestSuite()
        test_labels = test_labels or ['.']
        extra_tests = extra_tests or []

        input_test_labels = ','.join(test_labels).split(':', 1)
        if len(input_test_labels) == 2:
            test_labels, methods = map(lambda vals: [val for val in vals.split(',') if val], input_test_labels)
        else:
            test_labels, methods = input_test_labels[0].split(','), []

        discover_kwargs = {}
        if self.pattern is not None:
            discover_kwargs['pattern'] = self.pattern
        if self.top_level is not None:
            discover_kwargs['top_level_dir'] = self.top_level

        for label in test_labels:
            kwargs = discover_kwargs.copy()
            tests = None

            label_as_path = os.path.abspath(label)

            # if a module, or "module.ClassName[.method_name]", just run those
            if not os.path.exists(label_as_path):
                tests = self.test_loader.loadTestsFromName(label)
            elif os.path.isdir(label_as_path) and not self.top_level:
                # Try to be a bit smarter than unittest about finding the
                # default top-level for a given directory path, to avoid
                # breaking relative imports. (Unittest's default is to set
                # top-level equal to the path, which means relative imports
                # will result in "Attempted relative import in non-package.").

                # We'd be happy to skip this and require dotted module paths
                # (which don't cause this problem) instead of file paths (which
                # do), but in the case of a directory in the cwd, which would
                # be equally valid if considered as a top-level module or as a
                # directory path, unittest unfortunately prefers the latter.

                top_level = label_as_path
                while True:
                    init_py = os.path.join(top_level, '__init__.py')
                    if os.path.exists(init_py):
                        try_next = os.path.dirname(top_level)
                        if try_next == top_level:
                            # __init__.py all the way down? give up.
                            break
                        top_level = try_next
                        continue
                    break
                kwargs['top_level_dir'] = top_level

            if not (tests and tests.countTestCases()):
                # if no tests found, it's probably a package; try discovery
                tests = self.test_loader.discover(start_dir=label, **kwargs)

                # make unittest forget the top-level dir it calculated from this
                # run, to support running tests from two different top-levels.
                self.test_loader._top_level_dir = None

            tests = self.get_tests_defined_in_methods_or_none(tests, methods)
            if tests:
                suite.addTests(tests)

        for test in extra_tests:
            suite.addTest(test)

        return reorder_suite(suite, self.reorder_by)

    def get_tests_defined_in_methods_or_none(self, tests, methods):
        if not methods:
            return tests
        else:
            if isinstance(tests, TestSuite):
                returned_tests = []
                for test in tests:
                    returned_test = self.get_tests_defined_in_methods_or_none(test, methods)
                    if returned_test:
                        returned_tests.append(returned_test)
                return TestSuite(returned_tests)
            elif tests._testMethodName in methods:
                return tests
            else:
                return None