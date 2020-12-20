"""DoIt Documentation Utilities."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Pattern

from loguru import logger
from transitions import Machine

from ..log_helpers import log_fun
from .base import debug_task, open_in_browser, read_lines
from .doit_globals import DIG, DoItTask

# ----------------------------------------------------------------------------------------------------------------------
# Manage Tags


@log_fun
def task_tag_create() -> DoItTask:
    """Create a git tag based on the version in pyproject.toml.

    Returns:
        DoItTask: DoIt task

    """
    message = 'New Revision from PyProject.toml'
    return debug_task([
        f'git tag -a {DIG.meta.pkg_version} -m "{message}"',
        'git tag -n10 --list',
        'git push origin --tags',
    ])


@log_fun
def task_tag_remove() -> DoItTask:
    """Delete tag for current version in pyproject.toml.

    Returns:
        DoItTask: DoIt task

    """
    return debug_task([
        f'git tag -d "{DIG.meta.pkg_version}"',
        'git tag -n10 --list',
        f'git push origin :refs/tags/{DIG.meta.pkg_version}',
    ])


# ----------------------------------------------------------------------------------------------------------------------
# Update __init__.py with Documentation

_INIT_DIVIDER: str = f'# {"=" * 15} Above is Auto-Generated by calcipy. User content goes below {"=" * 15}'
"""Divider between auto-generated content and possible user-content in the `__init__.py` file."""

_LOGGER_CONFIG: str = """{docstring}

from loguru import logger

__version__ = '{pkg_version}'
__pkg_name__ = '{pkg_name}'

logger.disable(__pkg_name__)
"""
"""Python code to be appended to `__init__.py`."""


@log_fun
def _write_pkg_init() -> None:
    """Write the package `__init__.py` file."""
    init_text = _LOGGER_CONFIG.format(
        docstring=f'"""{DIG.meta.pkg_name}."""',
        pkg_version=DIG.meta.pkg_version,
        pkg_name=DIG.meta.pkg_name,
    ) + '\n' + _INIT_DIVIDER
    init_path = (DIG.meta.path_source / DIG.meta.pkg_name / '__init__.py')
    init_lines = init_path.read_text().strip().split('\n')
    try:
        break_index = init_lines.index(_INIT_DIVIDER) + 1
        user_text = '\n'.join(init_lines[break_index:])
    except ValueError as err:
        logger.warning('Did not find a divider, so overwriting any existing user text', err=err)
        user_text = ''
    init_path.write_text((init_text.replace('\t', ' ' * 4) + user_text).strip() + '\n')


# ----------------------------------------------------------------------------------------------------------------------
# Manage Changelog


@log_fun
def task_cl_write() -> DoItTask:
    """Write a Changelog file with the raw Git history.

    Resources:

    - https://keepachangelog.com/en/1.0.0/
    - https://www.conventionalcommits.org/en/v1.0.0/
    - https://writingfordevelopers.substack.com/p/how-to-write-a-commit-message
    - https://chris.beams.io/posts/git-commit/
    - https://semver.org/

    Returns:
        DoItTask: DoIt task

    """
    return debug_task(['poetry run cz changelog'])


@log_fun
def task_cl_bump() -> DoItTask:
    """Bump and write the Changelog file with the raw Git history.

    Returns:
        DoItTask: DoIt task

    """
    return debug_task(['poetry run cz bump --changelog'])


# ----------------------------------------------------------------------------------------------------------------------
# Manage README Updates


class _ReadMeMachine:  # noqa: H601
    """State machine to replace commented sections of readme with new text."""

    states: List[str] = ['readme', 'new']

    transitions: List[Dict[str, str]] = [
        {'trigger': 'start_new', 'source': 'readme', 'dest': 'new'},
        {'trigger': 'end', 'source': 'new', 'dest': 'readme'},
    ]

    readme_lines: Optional[List[str]] = None

    def __init__(self) -> None:
        """Initialize state machine."""
        self.machine = Machine(model=self, states=self.states, initial='readme', transitions=self.transitions)

    @log_fun
    def parse(self, lines: List[str], comment_pattern: Pattern[str],  # noqa: CCR001
              new_text: Dict[str, str]) -> List[str]:
        """Parse lines and insert new_text.

        Args:
            lines: list of text files
            comment_pattern: comment pattern to match (ex: ``)
            new_text: dictionary with comment string as key

        Returns:
            list: list of strings for README

        """
        self.readme_lines = []
        for line in lines:
            if comment_pattern.match(line):
                self.readme_lines.append(line)
                if line.strip().startswith('<!-- /'):
                    self.end()
                else:
                    key = comment_pattern.match(line).group(1)
                    self.readme_lines.extend(['', *new_text[key], ''])
                    self.start_new()
            elif self.state == 'readme':
                self.readme_lines.append(line)

            new_line = self.readme_lines[-1]
            made_change = (line != new_line)
            logger.debug('Parsed README Line', self_state=self.state, line=line,
                         made_change=made_change, new_line=new_line if made_change else None)

        return self.readme_lines


@log_fun
def _write_to_readme(comment_pattern: Pattern[str], new_text: Dict[str, str]) -> None:
    """Wrap _ReadMeMachine. Handle reading then writing changes to the README.

    Args:
        comment_pattern: comment pattern to match (ex: ``)
        new_text: dictionary with comment string as key

    """
    readme_path = DIG.meta.path_source / 'README.md'
    readme_lines = _ReadMeMachine().parse(read_lines(readme_path), comment_pattern, new_text)
    readme_path.write_text('\n'.join(readme_lines))


@log_fun
def _write_code_to_readme() -> None:
    """Replace commented sections in README with linked file contents."""
    comment_pattern = re.compile(r'\s*<!-- /?(CODE:.*) -->')
    fn = 'tests/examples/readme.py'
    script_path = DIG.meta.path_source / fn
    if script_path.is_file():
        source_code = ['```py', *read_lines(script_path), '```']
        new_text = {f'CODE:{fn}': [f'{line}'.rstrip() for line in source_code]}
        _write_to_readme(comment_pattern, new_text)
    else:
        logger.warning(f'Could not locate: {script_path}')


@log_fun
def _write_coverage_to_readme() -> None:
    """Read the coverage.json file and write a Markdown table to the README file."""
    # Create the 'coverage.json' file from .coverage SQL database. Suppress errors if failed
    try:
        import sh
        sh.poetry.run.python('-m', 'coverage', 'json')
    except ImportError:
        # HACK: sh doesn't work in Windows because of fcntl dependency. Need alternative
        logger.warning('Could not use "sh." Submit an issue on Github: https://github.com/KyleKing/calcipy/issues/new')
    except sh.ErrorReturnCode_1:
        logger.exception('Coverage conversion to JSON failed')

    coverage_path = (DIG.meta.path_source / 'coverage.json')
    if coverage_path.is_file():
        # Read coverage information from json file
        coverage = json.loads(coverage_path.read_text())
        # Collect raw data
        legend = ['File', 'Statements', 'Missing', 'Excluded', 'Coverage']
        int_keys = ['num_statements', 'missing_lines', 'excluded_lines']
        rows = [legend, ['--:'] * len(legend)]
        for file_path, file_obj in coverage['files'].items():
            rel_path = Path(file_path).resolve().relative_to(DIG.meta.path_source).as_posix()
            per = round(file_obj['summary']['percent_covered'], 1)
            rows.append([f'`{rel_path}`'] + [file_obj['summary'][key] for key in int_keys] + [f'{per}%'])
        # Format table for Github Markdown
        table_lines = [f"| {' | '.join([str(value) for value in row])} |" for row in rows]
        table_lines.extend(['', f"Generated on: {coverage['meta']['timestamp']}"])
        # Replace coverage section in README
        comment_pattern = re.compile(r'<!-- /?(COVERAGE) -->')
        _write_to_readme(comment_pattern, {'COVERAGE': table_lines})


# ----------------------------------------------------------------------------------------------------------------------
# mkdocs


# poetry run mkdocs serve
# poetry run mkdocs build --site-dir releases/docs
# poetry run mkdocs build --site-dir DIG.doc.path_out


# ----------------------------------------------------------------------------------------------------------------------
# Main Documentation Tasks


@log_fun
def task_document() -> DoItTask:
    """Build the HTML documentation.

    Returns:
        DoItTask: DoIt task

    """
    return debug_task([
        (_write_code_to_readme, ()),
        (_write_coverage_to_readme, ()),
        (_write_pkg_init, ()),
        # args = f'{DIG.meta.pkg_name} --html --force --output-dir "{DIG.doc.path_out}"'
        # f'poetry run portray {args}',  # PLANNED: Implement portray or mkdocs!
    ])


@log_fun
def task_open_docs() -> DoItTask:
    """Open the documentation files in the default browser.

    Returns:
        DoItTask: DoIt task

    """
    path_doc_index = DIG.doc.path_out / DIG.meta.pkg_name / 'index.html'
    return debug_task([
        (open_in_browser, (path_doc_index,)),
    ])
