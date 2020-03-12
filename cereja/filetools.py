import os
from typing import Union, List, Iterator, Tuple, Sequence, Any

from cereja.arraytools import is_sequence, is_iterable
from cereja.display import Progress
import logging

from cereja.path import normalize_path
from cereja.utils import invert_dict

logger = logging.Logger(__name__)

_explicit_exclude = ["_auto_ident_py", "FileBase", "_walk_dirs_and_replace"]

"""
CRLF platforms:
Atari TOS, Microsoft Windows, DOS (MS-DOS, PC DOS, etc.), DEC TOPS-10, RT-11, CP/M, MP/M, OS/2,
Symbian OS, Palm OS, Amstrad CPC, and most other early non-Unix and non-IBM operating systems
"""
CRLF = '\r\n'
"""
LF platforms:
Multics, Unix and Unix-like systems (Linux, macOS, FreeBSD, AIX, Xenix, etc.), BeOS, Amiga, RISC OS, and others
"""
LF = '\n'
"""
CR platforms:
Commodore 8-bit machines (C64, C128), Acorn BBC, ZX Spectrum, TRS-80, Apple II series, Oberon,
the classic Mac OS, MIT Lisp Machine and OS-9
"""
CR = "\r"

# UNIX is DEFAULT
DEFAULT_END_LINE = LF

_LINE_SEP_MAP = {
    CRLF: "CRLF",
    LF: "LF",
    CR: "CR"
}
_STR_LINE_SEP_MAP = invert_dict(_LINE_SEP_MAP)


class FileBase(object):
    """
    High-level API for creating and manipulating files
    """

    _line_sep_map = _LINE_SEP_MAP.copy()
    _str_line_sep_map = _STR_LINE_SEP_MAP.copy()
    _default_end_line = DEFAULT_END_LINE
    _dont_read = [".pyc",
                  ]

    def __init__(self, path_: str, content_file: Union[Sequence, str, Any]):
        self.__line_sep = None
        self.path_ = normalize_path(path_)
        self.__lines = self.normalize_data(content_file)
        if self.is_empty:
            self.line_sep = self._default_end_line
            self.content_file = [self._default_end_line]
        else:
            line_sep_ = self.parse_line_sep(self.__lines[0])
            if line_sep_ is None:
                self.line_sep = self._default_end_line
            else:
                self.line_sep = line_sep_

        self.__lock = True

    @classmethod
    def _add_line_sep(cls, data: List, line_sep_):
        if line_sep_ is None:
            line_sep_ = cls._default_end_line
        line_sep_ = cls.parse_line_sep(line_sep_)
        data_has_end_line = bool(cls.parse_line_sep(data[0]))
        if not data_has_end_line:
            return list(map(lambda line: line + f'{line_sep_}', data))
        elif data_has_end_line:
            logger.info("It has already been applied.")
        return data

    @classmethod
    def normalize_unix_line_sep(cls, content: str) -> str:
        return content.replace(cls._str_line_sep_map['CRLF'],
                               cls._default_end_line).replace(cls._str_line_sep_map['CR'],
                                                              cls._default_end_line)

    @classmethod
    def normalize_data(cls, data: Any, line_sep_=None):
        if is_iterable(data):
            if is_sequence(data):
                data = list(map(str, data))
            elif isinstance(data, str):
                data = data.splitlines(keepends=True)
            return cls._add_line_sep(data, line_sep_)
        else:
            raise ValueError("Invalid value. Send other ")

    @property
    def content_file(self) -> List[str]:
        return self.__lines

    @content_file.setter
    def content_file(self, lines: Sequence[str]):
        if hasattr(self, "__lock"):
            if self.__lock:
                raise AttributeError("Unable to apply content lines again, use another method.")
        self.__lines = self.normalize_data(lines)

    @classmethod
    def parse_line_sep(cls, line_sep_: str) -> Union[str, None]:
        if is_iterable(line_sep_):
            for ln in cls._line_sep_map:
                if ln in line_sep_:
                    return ln

        if line_sep_ in cls._str_line_sep_map:
            return cls._str_line_sep_map[line_sep_]

        logger.info("unknown end line.")
        return None

    @property
    def line_sep(self):
        return self._line_sep_map[self.__line_sep]

    @line_sep.setter
    def line_sep(self, line_sep_: str):
        self.__line_sep = self.parse_line_sep(line_sep_) or self._default_end_line

    @property
    def path_(self):
        return self.__path

    @path_.setter
    def path_(self, p: str):
        self.__path = p

    @property
    def file_name(self):
        return os.path.basename(self.path_)

    @property
    def file_name_without_ext(self):
        return os.path.splitext(self.file_name)[0]

    @property
    def n_lines(self):
        return len(self.__lines)

    @property
    def is_empty(self):
        return not bool(self.n_lines)

    @property
    def dir_name(self):
        return os.path.basename(self.dir_path)

    @property
    def dir_path(self):
        return os.path.dirname(self.path_)

    @property
    def is_link(self):
        return os.path.islink(self.path_)

    @property
    def content_str(self):
        return ''.join(self.__lines)

    @property
    def ext(self):
        return os.path.splitext(self.file_name)[-1]

    def _replace_file_sep(self, new):
        if new == self.__line_sep:
            return
        self.__lines = self.normalize_unix_line_sep(self.content_str).replace(self._default_end_line, new).splitlines(
            keepends=True)
        self.line_sep = new

    @classmethod
    def read(cls, path_: str, mode='r+', encoding='utf-8', **kwargs):
        path_ = normalize_path(path_)
        file_name = os.path.basename(path_)
        ext = os.path.splitext(file_name)[-1]
        if ext in cls._dont_read:
            logger.warning(f"I can't read this file. See class attribute <{cls.__name__}._dont_read>")
            return
        try:
            with open(path_, mode=mode, encoding=encoding, newline='', **kwargs) as fp:
                lines = fp.readlines()
        except PermissionError as err:
            logger.error(err)
            return

        return cls(path_, lines)

    @classmethod
    def replace_file_sep(cls, new, save: bool = True):
        raise NotImplementedError

    @classmethod
    def walk(cls, root_dir: str) -> Iterator[Tuple[str, int, list]]:
        """
        It works in a similar way to os.walk. With the difference that the File instance returns.
        :param root_dir: Root directory you want to start browsing
        :return:
        """
        for dir_name, _, files in os.walk(root_dir):
            files_ = []
            if files:
                for file_name in files:
                    file_path = os.path.join(dir_name, file_name)
                    if not os.path.islink(file_path):
                        try:
                            file_obj = cls.read(file_path)
                            if file_obj is not None:
                                files_.append(file_obj)
                        except UnicodeDecodeError as err:
                            logger.error(f'Error reading the file {file_name}: {err}')
            yield os.path.basename(dir_name), len(files_), files_

    def _insert(self, index: int, data: Union[Sequence, str]):
        pass

    @classmethod
    def save(cls, path_: Union[str, None]):
        raise NotImplementedError

    def __str__(self):
        return f'{self.__class__.__name__}<{self.file_name}>'


class File(FileBase):
    """
    High-level API for creating and manipulating files
    """

    def save(self, on_new_path: Union[os.PathLike, None] = None, encoding='utf-8', **kwargs):
        if on_new_path is not None:
            self.path_ = on_new_path
        with open(self.path_, 'w', newline='', encoding=encoding, **kwargs) as fp:
            fp.writelines(self.content_file)
        return self

    def replace_file_sep(self, new, save: bool = True):
        new = self.parse_line_sep(new)
        if new is None:
            raise ValueError(f"{new} is'nt valid.")
        try:
            self._replace_file_sep(new)
            if save is True:
                self.save()
        except UnicodeDecodeError:
            logger.error(f'Not possibility convert {self.file_name}')
        return self


class _FilePython(File):
    def insert_license(self):
        pass


def _walk_dirs_and_replace(dir_path, new, ext_in: list = None):
    ext_in = ext_in or []
    with Progress(f"Looking to {dir_path}") as prog:
        for dir_name, n_files, files_obj in File.walk(dir_path):
            if files_obj:
                prog.update(1, n_files)
                for i, file_obj in enumerate(files_obj):
                    if file_obj.is_link or (ext_in and file_obj.ext not in ext_in):
                        continue
                    prog.task_name = f"Converting {dir_name} ({file_obj})"
                    file_obj.replace_file_sep(new)
                    prog.update(i)


def convert_line_sep(path_: str, line_sep: str, ext_in: list = None):
    line_sep = File.parse_line_sep(line_sep)

    if line_sep is None:
        raise ValueError(f"The value sent {line_sep} is not valid.")

    if os.path.isdir(path_):
        _walk_dirs_and_replace(path_, LF, ext_in)
    else:
        with Progress(f"Converting {os.path.basename(path_)}") as prog:
            File.read(path_).replace_file_sep(line_sep)


def crlf_to_lf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    convert_line_sep(path_, LF, ext_in=ext_in)


def lf_to_crlf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    convert_line_sep(path_, CRLF, ext_in=ext_in)


def to_lf(path_: str):
    convert_line_sep(path_, LF)


def to_cr(path_: str):
    convert_line_sep(path_, CR)


def to_crlf(path_: str):
    convert_line_sep(path_, CRLF)


def _auto_ident_py(path: str):
    pass


if __name__ == '__main__':
    # f = File('./test.py', ['for i in range(5):', "    print(i)"]).save()
    lf_to_crlf('../lab/__init__.py')

    pass
