"""Test that the wildcard import works as expected."""

from calcipy.doit_tasks import *  # noqa


def test_doit_tasks_imports():
    """Test that the wildcard import for DoIt tasks only imports tasks."""
    suppress = ['test_doit_tasks_imports']

    wc_imports = [_g for _g in globals() if not _g.startswith('_') and _g not in suppress]  # act

    assert all(imp.startswith('task_') for imp in wc_imports)
    assert len(wc_imports) == 22  # Update if the number of tasks change