"""Test doit_helpers/doc.py."""

import os
import shutil
from pathlib import Path

from dash_dev.doit_helpers.doc import _write_pdoc_config_files, task_tag_create, task_tag_remove, task_update_cl
from dash_dev.doit_helpers.doit_globals import DIG

from ..configuration import DIG_CWD


def test_task_update_cl():
    """Test task_update_cl."""
    result = task_update_cl()

    assert len(result['actions']) == 1
    assert Path(os.environ['GITCHANGELOG_CONFIG_FILENAME']) == DIG.path_gitchangelog
    assert result['actions'][0] == 'gitchangelog > CHANGELOG-raw.md'


def test_task_tag_create():
    """Test task_tag_create."""
    DIG.set_paths(source_path=DIG_CWD)

    result = task_tag_create()

    assert len(result['actions']) == 3
    assert result['actions'][0].startswith('git tag -a')
    assert result['actions'][1] == 'git tag -n10 --list'
    assert result['actions'][2] == 'git push origin --tags'


def test_task_tag_remove():
    """Test task_tag_remove."""
    DIG.set_paths(source_path=DIG_CWD)

    result = task_tag_remove()

    assert len(result['actions']) == 3
    assert result['actions'][0].startswith('git tag -d')
    assert result['actions'][1] == 'git tag -n10 --list'
    assert result['actions'][2].startswith('git push origin :refs/tags/')


def test_write_pdoc_config_files():
    """Test write_pdoc_config_files."""
    DIG.set_paths(source_path=DIG_CWD)
    head_file = (DIG.template_dir / 'head.mako')
    config_file = (DIG.template_dir / 'config.mako')

    _write_pdoc_config_files()  # act

    assert head_file.is_file()
    assert config_file.is_file()
    shutil.rmtree(config_file.parent)