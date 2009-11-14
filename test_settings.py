from settings import *

DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = TEST_DATABASE_NAME = ':memory:'

CACHE_BACKEND = 'locmem:///'

TEST_RUNNER='test_runner.test_runner_with_coverage'

COVERAGE_MODULES = [
        'imap.models',
]
