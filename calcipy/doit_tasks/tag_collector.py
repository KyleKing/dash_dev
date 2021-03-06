"""Collect issue tags and output for review in a single location."""

# PLANNED: Revisit and standardize wording for tag vs. comment

import re
from collections import defaultdict
from pathlib import Path
from typing import List, Pattern, Sequence

import attr
from loguru import logger

from ..log_helpers import log_fun
from .base import debug_task, read_lines
from .doit_globals import DIG, DoItTask

_TAG_SUMMARY_FILENAME = 'TAG_SUMMARY.md'
"""Name of the tag summary file."""  # PLANNED: Maybe make this configurable?


@attr.s(auto_attribs=True)
class _TaggedComment:  # noqa: H601
    """Tagged (FIXME,TODO,etc) with contextual information."""  # noqa: T100,T101

    lineno: int
    tag: str
    text: str


@attr.s(auto_attribs=True)
class _Tags:  # noqa: H601
    """Collection of tagged comments with additional contextual information."""

    file_path: Path
    tagged_comments: List[_TaggedComment]


def _compile_issue_regex(regex_raw: str, tags: List[str]) -> Pattern[str]:
    """Compile the regex for the specified raw regular expression string and tags.

    Args:
        regex_raw: string regular expression that contains `{tag}`
        tags: string of tag names to match

    Returns:
        Pattern[str]: compiled regular expression to match all of the specified tags

    """
    return re.compile(regex_raw.format(tag='|'.join(tags)))


_regex_raw = r'((\s|\()(?P<tag>{tag})(:[^\r\n]))(?P<text>.+)'
_tags = ['DEBUG', 'FIXME', 'FYI', 'HACK', 'NOTE', 'PLANNED', 'REVIEW', 'TBD', 'TODO']  # noqa: T100,T101,T103

_COMPILED_RE = _compile_issue_regex(_regex_raw, _tags)
"""Default compiled regular expression."""


def _search_lines(
    lines: Sequence[str],
    regex_compiled: Pattern[str] = _COMPILED_RE,
) -> List[_TaggedComment]:
    """Search lines of text for matches to the compiled regular expression.

    Args:
        lines: lines of text as list
        regex_compiled: compiled regular expression. Expected to have matching groups `(tag, text)`

    Returns:
        List[_TaggedComment]: list of all tagged comments found in lines

    """
    comments = []
    for lineno, line in enumerate(lines):
        match = regex_compiled.search(line)
        if lineno <= 3 and ':skip_tags:' in line:
            break
        if match:
            mg = match.groupdict()
            comments.append(_TaggedComment(lineno + 1, tag=mg['tag'], text=mg['text']))
    return comments


def _search_files(
    paths_file: Sequence[Path],
    regex_compiled: Pattern[str] = _COMPILED_RE,
) -> List[_Tags]:
    """Collect matches from multiple files.

    Args:
        paths_file: list of files to parse
        regex_compiled: compiled regular expression. Expected to have matching groups `(tag, text)`

    Returns:
        List[_Tags]: list of all tagged comments found in files

    """
    matches = []
    for file_path in paths_file:
        lines = []
        try:
            lines = read_lines(file_path)
        except UnicodeDecodeError as err:
            logger.warning(f'Could not parse: {file_path}', err=err)

        comments = _search_lines(lines, regex_compiled)
        if comments:
            matches.append(_Tags(file_path, comments))

    return matches


def _format_report(base_dir: Path, tagged_collection: List[_Tags]) -> str:  # noqa: CCR001
    """Pretty-format the tagged items by file and line number.

    Args:
        base_dir: base directory relative to the searched files
        tagged_collection: list of all tagged comments found in files

    Returns:
        str: pretty-formatted text

    """
    output = ''
    counter = defaultdict(lambda: 0)
    for comments in sorted(tagged_collection, key=lambda tc: tc.file_path, reverse=False):
        output += f'{comments.file_path.relative_to(base_dir)}\n'
        for comment in comments.tagged_comments:
            output += f'    line {comment.lineno:>3} {comment.tag:>7}: {comment.text}\n'
            counter[comment.tag] += 1
        output += '\n'

    formatted_summary = ',  '.join([f'{tag} ({count})' for tag, count in counter.items()])
    if formatted_summary:
        output += f'Found tagged comments for {formatted_summary}\n'
    return output


def _find_files() -> List[Path]:
    """Find files within the project directory that should be parsed for tags. Ignores .venv, output, etc.

    Returns:
        List[Path]: list of file paths to parse

    """
    # TODO: Move all of these configuration items into DIG
    dot_directories = [pth for pth in DIG.meta.path_project.glob('.*') if pth.is_dir()]
    ignored_sub_dirs = [DIG.test.path_out.parent.name] + dot_directories
    ignored_filenames = [_TAG_SUMMARY_FILENAME]
    supported_suffixes = ['.md', '.py']

    paths_file = []
    # NOTE: THE TOP LEVEL path_project MUST USE GLOB (NOT RGLOB!)
    for suffix in supported_suffixes:
        paths = [*DIG.meta.path_project.glob(f'*{suffix}')]
        paths_file.extend([pth for pth in paths if pth.name not in ignored_filenames])

    paths_sub_dir = [pth for pth in DIG.meta.path_project.glob('*') if pth.is_dir() and pth not in ignored_sub_dirs]
    for path_dir in paths_sub_dir:
        for suffix in supported_suffixes:
            paths_file.extend([pth for pth in path_dir.rglob(f'*{suffix}') if pth.name not in ignored_filenames])
    logger.info(
        f'Found {len(paths_file)} files in {len(paths_sub_dir)} dir', paths_file=paths_file,
        paths_sub_dir=paths_sub_dir,
    )
    return paths_file


@log_fun
def _create_tag_file(path_tag_summary: Path) -> None:
    """Create the tag summary file.

    Args:
        path_tag_summary: Path to the output file

    """
    header = f'# Task Summary\n\nAuto-Generated by {DIG.meta.pkg_name}\n\n```log\n'
    footer = '```\n'
    matches = _search_files(_find_files())
    report = _format_report(DIG.meta.path_project, matches)
    if report.strip():
        path_tag_summary.write_text(header + report + footer)
    elif path_tag_summary.is_file():
        path_tag_summary.unlink()


def task_create_tag_file() -> DoItTask:
    """Create a summary file with all of the found tagged comments.

    Returns:
        DoItTask: doit task

    """
    path_tag_summary = DIG.meta.path_project / _TAG_SUMMARY_FILENAME
    return debug_task([(_create_tag_file, (path_tag_summary,))])
