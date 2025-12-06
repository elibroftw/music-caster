import pytest


def pytest_addoption(parser):
    parser.addoption('--ci', action='store_true', default=False)
    parser.addoption('--upload', action='store_true', default=False)
    parser.addoption('--test-auto-update', action='store_true', default=False)


@pytest.fixture(scope='session')
def ci(pytestconfig):
    return pytestconfig.getoption('ci')


def pytest_collection_modifyitems(config, items):
    if config.getoption('--ci'):
        skip_non_ci = pytest.mark.skip(reason='test not for CI')
        for item in items:
            if 'no_ci' in item.keywords:
                item.add_marker(skip_non_ci)
    else:
        skip_ci = pytest.mark.skip(reason='test only for CI')
        for item in items:
            if 'ci_only' in item.keywords:
                item.add_marker(skip_ci)
