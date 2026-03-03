from django.db import connections
from django.conf import settings
from django.core import management

from .runner import JunoDiscoverRunner


RERUN_LOG_FILE_NAME = getattr(
    settings,
    'TEST_RUNNER_RERUN_LOG_FILE_NAME',
    'test_rerun.txt'
)


class TestSuiteRunner(JunoDiscoverRunner):
    """
    Extended version of the standard Django test runner to support:

    * immediately showing error details during test progress, in addition
        to showing them once the suite  has completed
    * logging the dotted path for the failing tests to a file to make it
        easier to re-run failed tests via the YJ run_tests Fabric task
    * numbering tests/showing a progress counter
    * colourised output (and yes, that's the correct spelling of 'colourised' ;-) )

    """

    def __init__(self, *args, **kwargs):
        self.slow_test_count = int(kwargs.get('slow_test_count', 0))
        self.only_failed = kwargs.get('only_failed', False)
        self.methods = kwargs.get('methods', None)
        super().__init__(*args, **kwargs)

    @classmethod
    def add_arguments(cls, parser):
        super(TestSuiteRunner, cls).add_arguments(parser)
        parser.add_argument(
            '-s', '--slow-tests',
            action='store',
            dest='slow_test_count',
            default=0,
            help='Print given number of slowest tests'
        )
        parser.add_argument(
            '--only-failed',
            action='store_true',
            help='Run only failed tests'
        )
        parser.add_argument(
            '--methods',
            action='store',
            dest='methods',
            default=None,
            help='List of test method names to run'
        )

    def run_tests(self, test_labels, **kwargs):
        """
        Run the unit tests for all the test labels in the provided list.
        """

        if self.only_failed:
            with open(RERUN_LOG_FILE_NAME, 'r') as f:
                test_labels = list(filter(None, f.read().split('\n')))

        self.setup_test_environment()
        suite = self.build_suite(test_labels)

        old_config = self.setup_databases()
        result = self.run_suite(suite)
        self.teardown_databases(old_config)
        self.teardown_test_environment()
        return self.suite_result(suite, result)
