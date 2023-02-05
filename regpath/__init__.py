"""
Home to RegistryPath and friends
"""

from __future__ import annotations

import contextlib
import functools
import typing
import winreg

__version__ = "0.0.1"


REGISTRY_KEYS = {
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKU": winreg.HKEY_USERS,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKCC": winreg.HKEY_CURRENT_CONFIG,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}


class HKeyNotFoundError(FileNotFoundError):
    """Denotes that we couldn't find the HKEY constant for this path"""

    def __init__(self, path: RegistryPath):
        self.path = path

    def __str__(self):
        return f"Couldn't find the HKEY component for {self.path}"


class RegistryPath:
    def __init__(
        self, raw_path: str, value_name: str | None = None, computer: str | None = None
    ):

        if computer is not None:
            if computer.lower() == "computer":
                computer = None

        if isinstance(computer, str):
            computer = r"\\" + computer.lstrip("\\")

        self.computer = computer
        self.value_name = value_name

        if not raw_path:
            raise ValueError(
                "The given raw registry path must be a string and longer than one character"
            )

        # get rid of computer from the front of a registry path
        if raw_path.lower().startswith("computer"):
            raw_path = raw_path[len("computer") + 1 :]

        self._raw_path = raw_path
        self._parse_raw_path(self._path_split())

    def __repr__(self) -> str:
        """
        Returns a representation of the object
        """
        if self.value_name is None:
            ret = f"<RegistryPath: {self._raw_path}"
        else:
            ret = f"<RegistryPath: {self._raw_path} -> {self.value_name}"

        if self.computer is not None:
            ret += f" On {self.computer}"

        ret += ">"
        return ret

    def __hash__(self) -> int:
        """
        Returns a unique hash for this object
        """
        return hash(repr(self))

    def __eq__(self, other) -> bool:
        """Returns True if both are equal"""
        return hash(self) == hash(other)

    def __truediv__(self, other: str):
        """
        Implementation for the / operator.
        Allows concatenating subkeys on keys/subkeys
        """
        if self.value_name is not None:
            raise ValueError(
                "Cannot do <path to file/value name> <SLASH> something else"
            )

        # value_name MUST be None
        return RegistryPath(
            "\\".join(self.parts) + "\\" + other, computer=self.computer
        )

    def _path_split(self) -> list[str]:
        """
        Splits the path into a list of components

        We allow using the '/' operator BUT we can't split on that since registry keys can have / in them.
        This explains why using / instead of \\ in paths will not work properly.
        """
        return self._raw_path.split("\\")

    def _parse_raw_path(self, path_components: list[str] | None) -> None:
        """
        Sets self._key from the given path components.
        Will raise if the inital HKey is not valid.
        """
        first_component = path_components[0]

        if first_component.upper() in REGISTRY_KEYS:
            key_raw = path_components[0]
        else:
            raise HKeyNotFoundError(self)

        self._key = REGISTRY_KEYS[key_raw]

    @contextlib.contextmanager
    def _get_subkey_handle(
        self, reads: bool = True, writes: bool = False
    ) -> typing.Iterator[winreg.HKEYType]:
        """
        Contextmanager to get a handle to the referenced subkey inside the registry on the given computer

        If reads is True, open with read access (default)
        If writes is True, open with write access

        Will close the handle(s) out upon exit.
        """
        access = 0
        if reads:
            access |= winreg.KEY_READ
        if writes:
            access |= winreg.KEY_WRITE

        with winreg.ConnectRegistry(self.computer, self._key) as reg_handle:
            # folder/key
            with winreg.OpenKey(reg_handle, self.subkey, access=access) as handle:
                yield handle

    def exists(self) -> bool:
        """
        Returns True if the given path resolves to something (either a key or value)
        """
        try:
            with self._get_subkey_handle() as handle:
                if self.value_name is None:
                    # dir/key and its there
                    return True
                else:
                    # value name ... need to check for that.
                    winreg.QueryValueEx(handle, self.value_name)
                    return True
        except FileNotFoundError:
            return False

    def is_dir(self) -> bool:
        """
        Returns True if this path appears to be a dir/key
        """

        return self.value_name is None and self.exists()

    def is_file(self, value_name: str | None = None) -> bool:
        """
        Returns True if this path appears to be a value name/file
        """
        vname = value_name or self.value_name
        return (
            vname is not None and self.with_value_name(value_name=value_name).exists()
        )

    @property
    @functools.lru_cache
    def parent(self) -> RegistryPath:
        """
        Returns the first parent of this path
        """
        return self.parents[0]

    @property
    @functools.lru_cache
    def parents(self) -> tuple[RegistryPath]:
        """
        Returns a tuple of all parent parts of this RegistryPath
        """
        ret_list = []
        for i in range(1, len(self.parts)):
            ret_list.append(RegistryPath("\\".join(self.parts[:-i])))
        return tuple(ret_list)

    @property
    @functools.lru_cache
    def name(self) -> str:
        """
        Returns the name of our key (if we're a dir/key) or the value_name if we're a value
        """

        # if this is a key, return the key name
        if self.value_name is None:
            return self.parts[-1]

        # if this is a value name, return that
        return self.value_name

    @property
    @functools.lru_cache
    def subkey(self) -> str:
        """
        Returns the subkey (all dirs that lead to the final key skipping the first key)
        """
        # if we have a value_name, parts will include the value name... skip that part
        if self.value_name is not None:
            return "\\".join(self.parts[1:-1])

        # no value name, so just skip the HKEY
        return "\\".join(self.parts[1:])

    @property
    def registry_type(self) -> int:
        """
        Returns the registry type for the current file/value path

        This doesn't work with directories/keys
        """
        if self.value_name is None:
            raise ValueError(
                "This function only works if value_name is set.. so it only works with values"
            )

        with self._get_subkey_handle() as handle:
            _, typ = winreg.QueryValueEx(handle, self.value_name)
            return typ

    @property
    @functools.lru_cache
    def parts(self) -> tuple[str]:
        """
        Returns a tuple of parts that make up this path
        """
        ret_list = self._path_split()
        if self.value_name is not None:
            ret_list.append(self.value_name)
        return tuple(ret_list)

    def mkdir(self, parents: bool = False, exist_ok: bool = False) -> None:
        """
        Makes this key.

        If parents is True, will create all needed parents to get here.
        If exist_ok is True, will not raise an error if the path already exists
        """
        if self.value_name is not None:
            raise ValueError(
                "Cannot mkdir if a value_name was given. This path is for a value not a key."
            )

        if self.is_dir():
            if exist_ok:
                return
            else:
                raise FileExistsError(f"Key {self} already exists")

        if parents:
            for p in reversed(self.parents):
                p.mkdir(exist_ok=True)

        with self.parent._get_subkey_handle(writes=True) as handle:
            # use with to close the new key
            with winreg.CreateKey(handle, self.name):
                pass

    def iterdir(self) -> typing.Generator[RegistryPath, None, None]:
        """
        Iterates over all the subkeys and values in this key
        """
        if not self.is_dir():
            raise NotADirectoryError(f"{self} is not a key/directory")

        with self._get_subkey_handle() as handle:
            num_sub_keys, num_values, _ = winreg.QueryInfoKey(handle)

            for sub_key_idx in range(num_sub_keys):
                sub_key_name = winreg.EnumKey(handle, sub_key_idx)
                yield self / sub_key_name

            for value_idx in range(num_values):
                value_name, _, _ = winreg.EnumValue(handle, value_idx)
                yield self.with_value_name(value_name)

    def unlink(self, missing_ok: bool = False):
        """
        Removes the given value_name. From the current subkey
        """
        if self.value_name is None:
            raise FileNotFoundError(f"{self} points to a directory/key not a file")

        with self._get_subkey_handle(writes=True) as handle:
            try:
                winreg.DeleteValue(handle, self.value_name)
            except FileNotFoundError:
                if not missing_ok:
                    raise

    def rmdir(self):
        """
        Removes this if its a directory/key
        """
        try:
            next(self.iterdir())
            raise OSError(f"The directory/key is not empty: {self}")
        except StopIteration:
            # this is ok.. it means the dir/key is empty... we can safely remove it.
            with self.parent._get_subkey_handle(writes=True) as handle:
                winreg.DeleteKey(handle, self.name)

    def rmtree(self):
        """
        Recursively removes this directory/key and all its contents
        """

        for child in self.iterdir():
            if child.is_dir():
                child.rmtree()
            else:
                child.unlink()
        self.rmdir()

    def with_value_name(self, value_name: str | None = None) -> RegistryPath:
        """
        Makes a copy of this RegistryPath, though modifies the value_name field to what is passed in
        """
        return RegistryPath(
            self._raw_path, value_name=value_name, computer=self.computer
        )

    def read_raw(self, value_name: str | None = None) -> tuple:
        """
        Attempts to read the given value_name from our current path from the registry.

        Returns the output of winreg.QueryValueEx()

        If value_name is None, will use the constructor's value_name instead. If that was also None, will raise ValueError
        """
        vname = value_name or self.value_name
        if vname is None:
            raise ValueError("value_name must be provided to use read_raw()")

        with self._get_subkey_handle() as handle:
            return winreg.QueryValueEx(handle, vname)

    def read(self, value_name: str | None = None) -> typing.Any:
        """
        Attempts to read the given value_name from our current path from the registry.

        Returns a Python object based on the registry type.

        If value_name is None, will use the constructor's value_name instead. If that was also None, will raise ValueError
        """
        raw_value, _ = self.read_raw(value_name)
        # we can throw out the type since python coerces most of the values already
        # ones that don't are: REG_RESOURCE_REQUIREMENTS_LIST, REG_FULL_RESOURCE_DESCRIPTOR, REG_RESOURCE_LIST
        # those will likely just return bytes
        return raw_value

    def write_raw(self, value: typing.Any, typ: int, value_name: str | None = None):
        """
        Write the given value of the given type into the registry at our current value_name.
        If value_name is not given, will use the one on this RegistryPath object.
        """
        vname = value_name or self.value_name
        if vname is None:
            raise ValueError("value_name must be provided to use write_raw()")

        with self._get_subkey_handle(writes=True) as handle:
            winreg.SetValueEx(handle, vname, 0, typ, value)

    def write(
        self, value: typing.Any, value_name: str | None = None, read_type: bool = True
    ):
        """
        Write the given value into the registry at our current value_name.
        If value_name is not given, will use the one on this RegistryPath object.

        If read_type is True, will attempt to read the current type from the registry for the
        given value_name. If the value already exists, will attempt to write the new data with the
        same type.

        If we are unable to get the type (either the value name doesn't exist already or read_type is False)
        we will look at the data and use some heuristics to figure out which type to use.

        If more control is needed over type, use write_raw()
        """

        vname = value_name or self.value_name
        if vname is None:
            raise ValueError("value_name must be provided to use write()")

        # default to binary data
        typ = winreg.REG_BINARY

        guess_type = True
        if read_type:
            try:
                typ = self.with_value_name(vname).registry_type
                guess_type = False
            except FileNotFoundError:
                # can't read it if it doesn't exist... that's ok.. we'll guess
                pass

        if guess_type:
            if isinstance(value, str):
                percent_count = value.count("%")
                if percent_count > 0 and percent_count % 2 == 0:
                    # .. possibly detected env vars
                    typ = winreg.REG_EXPAND_SZ
                else:
                    typ = winreg.REG_SZ
            elif isinstance(value, list):
                # if someone does like a list of ints... this will break
                typ = winreg.REG_MULTI_SZ
            elif isinstance(value, type(None)):
                typ = winreg.REG_NONE
            elif isinstance(value, int):
                if value < 0:
                    raise ValueError(
                        "Guessed an integer type.. but you passed a negative. Numbers in the registry are unsigned."
                    )

                if value > 0xFFFFFFFF:
                    typ = winreg.REG_QWORD
                else:
                    typ = winreg.REG_DWORD

        self.write_raw(value, typ, vname)
