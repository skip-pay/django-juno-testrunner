import logging
import os
import unittest
import warnings

from django.test.runner import DiscoverRunner, partition_suite_by_case, filter_tests_by_tags
from django.test.runner import reorder_tests
from django.core import management
from django.conf import settings
from django.test.utils import NullTimeKeeper, TimeKeeper, iter_test_cases

from junorunner.extended_runner import TextTestRunner

from unittest.suite import TestSuite
from unittest import loader


class JunoDiscoverRunner(DiscoverRunner):
    """
    The only real difference between this and the standard DiscoverRunner in Django 1.6+
    is the use of the custom TextTestRunner, which we hook in via run_suite()
    """

    test_runner = TextTestRunner
    total_tests = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_log_files = not self.failfast

    def get_test_runner_kwargs(self):
        return {
            "failfast": self.failfast,
            "resultclass": self.get_resultclass(),
            "verbosity": self.verbosity,
            "buffer": self.buffer,
            "total_tests": self.total_tests,
            "slow_test_count": self.slow_test_count,
            "use_log_files": self.use_log_files,
        }

    def build_suite(self, test_labels=None, **kwargs):
        methods = self.methods.split(',') if self.methods else []
        if methods:
            self.use_log_files = False
        test_labels = test_labels or ["."]

        discover_kwargs = {}
        if self.pattern is not None:
            discover_kwargs["pattern"] = self.pattern
        if self.top_level is not None:
            discover_kwargs["top_level_dir"] = self.top_level
        self.setup_shuffler()

        all_tests = []
        for label in test_labels:
            tests = self.load_tests_for_label(label, discover_kwargs)
            tests = self.get_tests_defined_in_methods_or_none(tests, methods)
            if tests:
                all_tests.extend(iter_test_cases(tests))

        if self.tags or self.exclude_tags:
            if self.tags:
                self.log(
                    "Including test tag(s): %s." % ", ".join(sorted(self.tags)),
                    level=logging.DEBUG,
                )
            if self.exclude_tags:
                self.log(
                    "Excluding test tag(s): %s." % ", ".join(sorted(self.exclude_tags)),
                    level=logging.DEBUG,
                )
            all_tests = filter_tests_by_tags(all_tests, self.tags, self.exclude_tags)

        # Put the failures detected at load time first for quicker feedback.
        # _FailedTest objects include things like test modules that couldn't be
        # found or that couldn't be loaded due to syntax errors.
        test_types = (unittest.loader._FailedTest, *self.reorder_by)
        all_tests = list(
            reorder_tests(
                all_tests,
                test_types,
                shuffler=self._shuffler,
                reverse=self.reverse,
            )
        )
        self.log("Found %d test(s)." % len(all_tests))
        suite = self.test_suite(all_tests)

        if self.parallel > 1:
            subsuites = partition_suite_by_case(suite)
            # Since tests are distributed across processes on a per-TestCase
            # basis, there's no need for more processes than TestCases.
            processes = min(self.parallel, len(subsuites))
            # Update also "parallel" because it's used to determine the number
            # of test databases.
            self.parallel = processes
            if processes > 1:
                suite = self.parallel_test_suite(
                    subsuites,
                    processes,
                    self.failfast,
                    self.debug_mode,
                    self.buffer,
                )

        return suite

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
            elif isinstance(tests, loader._FailedTest):
                return tests
            else:
                return None
