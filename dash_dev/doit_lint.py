"""DoIt Linting Utilities."""

import toml

from .doit_base import DIG, debug_action, echo, if_found_unlink, write_text

# ----------------------------------------------------------------------------------------------------------------------
# General


def collect_py_files(add_paths=(), excluded_files=None, subdirectories=None):
    """Collect the tracked files for linting and formatting. Return as list of string paths.

    Args:
        add_paths: List of absolute paths to additional Python files to process. Default is an empty list
        excluded_files: filenames to skip when collecting files. Default is `[__init__.py]`
        subdirectories: folder names to recursively check for Python files. Default is
            `[DIG.pkg_name] + DIG.external_doc_dirs`

    Returns:
        list: of string path names

    Raises:
        RuntimeError: if the add_paths argument is not a list or tuple

    """
    if not isinstance(add_paths, (list, tuple)):
        raise RuntimeError(f'Expected add_paths to be a list of Paths, but received: {add_paths}')
    if excluded_files is None:
        excluded_files = ['__init__.py']
    if subdirectories is None:
        subdirectories = [DIG.pkg_name] + DIG.external_doc_dirs
    package_files = [*add_paths] + [*DIG.source_path.glob('*.py')]
    for subdir in subdirectories:  # Capture files in package and in tests directory
        package_files.extend([*(DIG.source_path / subdir).rglob('*.py')])
    return [str(file_path) for file_path in package_files if file_path.name not in excluded_files]


# ----------------------------------------------------------------------------------------------------------------------
# Configuration Settings

FLAKE8 = """
[flake8]
annoy = true
assertive-snakecase = true
cohesion-below = 50.0
docstring-convention = all
# Explanation and Notes on Flake8 Ignore Rules. Also see: https://www.flake8rules.com/
# D203,D213,D214,D406,D407 / (conflicts with Google docstrings) http://www.pydocstyle.org/en/latest/error_codes.html
# G004 / https://github.com/globality-corp/flake8-logging-format#violations-detected
# PD005,PD011 / (false positives) https://github.com/deppen8/pandas-vet/issues/74
# S322 / https://github.com/tylerwince/flake8-bandit
# W503 - Must select one of W503 or W504. See: https://lintlyci.github.io/Flake8Rules/rules/W504.html
#   Python 3 standard is a line break BEFORE binary operator, so ignore W503. Enforce W504
ignore = D203,D213,D214,D406,D407,G004,PD005,PD011,S322,W503
# Default is 7. See: https://github.com/Melevir/flake8-cognitive-complexity
max-cognitive-complexity = 7
max-complexity = 10
# Default is 7. See: https://github.com/best-doctor/flake8-expression-complexity
max-expression-complexity = 7
max-function-length = 55
max-line-length = 120
max-parameters-amount = 6
per-file-ignores=test_*.py:S101,DAR101
select = A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z

# Do not modify, auto-generated by dash_dev
"""
"""Flake8 configuration file settings."""

ISORT = {
    'line_length': 120,
    'length_sort': False,
    'default_section': 'THIRDPARTY',
}
"""ISort configuration file settings."""


def task_set_lint_config():
    """Lint specified files creating summary log file of errors.

    Returns:
        dict: DoIt task

    """
    user_toml = toml.load(DIG.toml_path)
    user_toml['tool']['isort'] = ISORT
    return debug_action([
        (write_text, (DIG.flake8_path, FLAKE8.strip())),
        (write_text, (DIG.toml_path, toml.dumps(user_toml))),
    ])


# ----------------------------------------------------------------------------------------------------------------------
# Linting


def list_lint_file_paths(path_list):
    """Create a list of all Python files specified in the path_list.

    Args:
        path_list: list of paths to directories or files

    Returns:
        list: list of file Paths

    """
    file_paths = []
    for path_item in path_list:
        if path_item.is_dir():
            file_paths.extend([*path_item.rglob('*.py')])
        else:
            file_paths.append(path_item)
    return file_paths


def check_linting_errors(flake8_log_path, ignore_errors=None):  # noqa: CCR001
    """Check for errors reported in flake8 log file. Removes log file if no errors detected.

    Args:
        flake8_log_path: path to flake8 log file created with flag: `--output-file=flake8_log_path`
        ignore_errors: list of error codes to ignore (beyond the flake8 config settings). Default is None

    Raises:
        RuntimeError: if flake8 log file contains any text results

    """
    flake8_full_path = flake8_log_path.parent / f'{flake8_log_path.stem}-full{flake8_log_path.suffix}'
    log_contents = flake8_log_path.read_text().strip()
    review_info = f'. Review: {flake8_log_path}'
    if ignore_errors is not None:
        # Backup the full list of errors
        flake8_full_path.write_text(log_contents)
        # Exclude the errors specificed to be ignored by the user
        lines = []
        for line in log_contents.split('\n'):
            if not any(f': {error_code}' in line for error_code in ignore_errors):
                lines.append(line)
        log_contents = '\n'.join(lines)
        flake8_log_path.write_text(log_contents)
        review_info = (f' even when ignoring {ignore_errors}.\nReview: {flake8_log_path}'
                       f'\nNote: the full list linting errors are reported in {flake8_full_path}')
    else:
        if_found_unlink(flake8_full_path)

    # Raise an exception if any errors were found. Remove the files if not
    if len(log_contents) > 0:
        raise RuntimeError(f'Found Linting Errors{review_info}')
    if_found_unlink(flake8_log_path)


def lint_project(lint_paths, flake8_path=DIG.flake8_path, ignore_errors=None):
    """Lint specified files creating summary log file of errors.

    Args:
        lint_paths: list of file and directory paths to lint
        flake8_path: path to flake8 configuration file. Default is `DIG.flake8_path`
        ignore_errors: list of error codes to ignore (beyond the flake8 config settings). Default is None

    Returns:
        dict: DoIt task

    """
    # Flake8 appends to the log file. Ensure that an existing file is deleted so that Flake8 creates a fresh file
    flake8_log_path = DIG.source_path / 'flake8.log'
    actions = [(if_found_unlink, (flake8_log_path, ))]
    run = 'poetry run python -m'
    flags = f'--config={flake8_path}  --output-file={flake8_log_path} --exit-zero'
    for lint_path in list_lint_file_paths(lint_paths):
        actions.append(f'{run} flake8 "{lint_path}" {flags}')
    actions.append((check_linting_errors, (flake8_log_path, ignore_errors)))
    return actions


def task_lint_project():
    """Lint files from DIG creating summary log file of errors.

    Returns:
        dict: DoIt task

    """
    return debug_action(lint_project(DIG.lint_paths, flake8_path=DIG.flake8_path, ignore_errors=None))


def task_lint_pre_commit():
    """Lint files from DIG creating summary log file of errors, but ignore non-critical errors.

    Returns:
        dict: DoIt task

    """
    ignore_errors = [
        'AAA01',  # AAA01 / act block in pytest
        'C901',  # C901 / complexity from "max-complexity = 10"
        'D417',  # D417 / missing arg descriptors
        'DAR101', 'DAR201', 'DAR401',  # https://pypi.org/project/darglint/ (Scroll to error codes)
        'DUO106',  # DUO106 / insecure use of os
        'E800',  # E800 / Commented out code
        'G001',  # G001 / logging format for un-indexed parameters
        'H601',  # H601 / class with low cohesion
        'P101', 'P103',  # P101,P103 / format string
        'PD013',
        'PD901',  # PD901 / 'df' is a bad variable name
        'S101',  # S101 / assert
        'S605', 'S607',  # S605,S607 / os.popen(...)
        'T100', 'T101',  # T100,T101 / fixme and todo comments
    ]
    return debug_action(lint_project(DIG.lint_paths, flake8_path=DIG.flake8_path, ignore_errors=ignore_errors))


def task_radon_lint():
    """See documentation: https://radon.readthedocs.io/en/latest/intro.html. Lint project with Radon.

    Returns:
        dict: DoIt task

    """
    actions = []
    for args in ['mi', 'cc --total-average -nb', 'hal']:
        actions.extend(
            [(echo, (f'# Radon with args: {args}', ))]
            + [f'poetry run radon {args} "{lint_path}"' for lint_path in list_lint_file_paths(DIG.lint_paths)],
        )
    return debug_action(actions)


# ----------------------------------------------------------------------------------------------------------------------
# Formatting


def task_auto_format():
    """Format code with isort and autopep8.

    Returns:
        dict: DoIt task

    """
    run = 'poetry run python -m'
    actions = []
    for lint_path in DIG.lint_paths:
        actions.append(f'{run} isort "{lint_path}" --settings-path {DIG.toml_path}')
        for fn in list_lint_file_paths([lint_path]):
            actions.append(f'{run} autopep8 "{fn}" --in-place --aggressive')
    return debug_action(actions)
