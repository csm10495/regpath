import winreg
from unittest.mock import MagicMock, patch

import pytest

from regpath import HKeyNotFoundError, RegistryPath


def test_init():
    with pytest.raises(ValueError):
        RegistryPath("")

    assert RegistryPath("HKLM")._raw_path == "HKLM"
    assert RegistryPath("Computer\\HKLM")._raw_path == "HKLM"
    assert RegistryPath("HKLM", computer="computer").computer is None
    assert RegistryPath("HKLM", computer="mycomputer").computer == r"\\mycomputer"
    assert RegistryPath("HKLM", computer="mycomputer").computer == r"\\mycomputer"
    assert RegistryPath("HKLM", value_name="value-name").value_name == r"value-name"


def test_repr():
    assert repr(RegistryPath("HKLM")) == "<RegistryPath: HKLM>"
    assert (
        repr(RegistryPath("HKLM", value_name="test")) == "<RegistryPath: HKLM -> test>"
    )
    assert (
        repr(RegistryPath("HKLM", value_name="test", computer="mycomputer"))
        == "<RegistryPath: HKLM -> test On \\\\mycomputer>"
    )


def test_eq():
    assert RegistryPath("HKLM") == RegistryPath("HKLM")
    assert RegistryPath("HKLM") != RegistryPath("HKLM", value_name="test")
    assert RegistryPath("HKLM") != RegistryPath("HKLM", computer="test")

    assert RegistryPath("HKLM", value_name="test", computer="joe") == RegistryPath(
        "HKLM", value_name="test", computer="joe"
    )


def test_truediv():
    assert RegistryPath("HKLM") / "testing" == RegistryPath("HKLM\\testing")
    assert RegistryPath("HKLM", computer="lol") / "testing" == RegistryPath(
        "HKLM\\testing", computer="lol"
    )

    with pytest.raises(ValueError):
        RegistryPath("HKLM", value_name="hi") / "anything"


def test_path_split():
    p = RegistryPath("HKLM\\lolcats\\loldogs/okay")
    assert p._path_split() == ["HKLM", "lolcats", "loldogs/okay"]


def test_parse_raw_path_simple():
    p = RegistryPath("HKLM")

    assert p._key_raw == "HKLM"
    assert p._key == winreg.HKEY_LOCAL_MACHINE


def test_parse_raw_path_simple_invalid_key():
    with pytest.raises(HKeyNotFoundError):
        RegistryPath("NotRealKey")


def test_parse_raw_path_simple():
    p = RegistryPath(r"HKLM")

    assert p._key == winreg.HKEY_LOCAL_MACHINE


def test_get_subkey_handle():
    p = RegistryPath("HKLM\\HARDWARE\\Stuff", computer="mycomputer")
    with patch("regpath.winreg.ConnectRegistry") as ConnectRegistry:
        with patch("regpath.winreg.OpenKey") as OpenKey:
            with p._get_subkey_handle(reads=True):
                pass

            ConnectRegistry.assert_called_with(
                r"\\mycomputer", winreg.HKEY_LOCAL_MACHINE
            )
            OpenKey.assert_called_with(
                ConnectRegistry().__enter__.return_value,
                r"HARDWARE\Stuff",
                access=winreg.KEY_READ,
            )

    p = RegistryPath("HKLM\\HARDWARE\\Stuff")

    with patch("regpath.winreg.ConnectRegistry") as ConnectRegistry:
        with patch("regpath.winreg.OpenKey") as OpenKey:
            with p._get_subkey_handle(writes=True):
                pass

            ConnectRegistry.assert_called_with(None, winreg.HKEY_LOCAL_MACHINE)
            OpenKey.assert_called_with(
                ConnectRegistry().__enter__.return_value,
                r"HARDWARE\Stuff",
                access=winreg.KEY_READ | winreg.KEY_WRITE,
            )


def test_exists_key_true():
    p = RegistryPath("HKLM\\HARDWARE\\Stuff")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    assert p.exists()


def test_exists_key_false():
    p = RegistryPath("HKLM\\HARDWARE\\Stuff")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.side_effect = FileNotFoundError()
    assert not p.exists()


def test_exists_value_true():
    p = RegistryPath("HKLM\\HARDWARE\\Stuff", value_name="test")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.QueryValueEx") as QueryValueEx:
        assert p.exists()
        QueryValueEx.assert_called_once_with("handle", "test")


def test_exists_value_false():
    p = RegistryPath("HKLM\\HARDWARE\\Stuff", value_name="test")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.QueryValueEx") as QueryValueEx:
        QueryValueEx.side_effect = FileNotFoundError()
        assert not p.exists()
        QueryValueEx.assert_called_once_with("handle", "test")


def test_is_dir():
    p = RegistryPath("HKLM\\HARDWARE\\Stuff")
    p.exists = MagicMock(return_value=True)
    assert p.is_dir()

    p = RegistryPath("HKLM\\HARDWARE\\Stuff")
    p.exists = MagicMock(return_value=False)
    assert not p.is_dir()

    p = RegistryPath("HKLM\\HARDWARE\\Stuff", value_name="test")
    p.exists = MagicMock(return_value=True)
    assert not p.is_dir()

    p = RegistryPath("HKLM\\HARDWARE\\Stuff", value_name="test")
    p.exists = MagicMock(return_value=False)
    assert not p.is_dir()


def test_is_file():
    p = RegistryPath("HKLM\\HARDWARE\\Stuff")
    assert not p.is_file()

    p = RegistryPath("HKLM\\HARDWARE\\Stuff", value_name="test")
    p.with_value_name = MagicMock(return_value=p)
    p.exists = MagicMock(return_value=True)
    assert p.is_file()

    p = RegistryPath("HKLM\\HARDWARE\\Stuff", value_name="test")
    p.with_value_name = MagicMock(return_value=p)
    p.exists = MagicMock(return_value=False)
    assert not p.is_file()


def test_parent_and_parents():
    p = RegistryPath(r"HKLM\Other\Place\ForMe")

    assert p.parent == RegistryPath(r"HKLM\Other\Place")
    assert p.parents == (
        RegistryPath(r"HKLM\Other\Place"),
        RegistryPath(r"HKLM\Other"),
        RegistryPath(r"HKLM"),
    )

    p = RegistryPath(r"HKLM\Other\Place\ForMe", value_name="v")

    assert p.parent == RegistryPath(r"HKLM\Other\Place\ForMe")
    assert p.parents == (
        RegistryPath(r"HKLM\Other\Place\ForMe"),
        RegistryPath(r"HKLM\Other\Place"),
        RegistryPath(r"HKLM\Other"),
        RegistryPath(r"HKLM"),
    )


def test_name():
    assert RegistryPath(r"HKLM\Other").name == "Other"
    assert RegistryPath(r"HKLM\Other", value_name="myvalue").name == "myvalue"


def test_subkey():
    assert RegistryPath(r"HKLM\Other\Stuff").subkey == r"Other\Stuff"
    assert RegistryPath(r"HKLM\Other\Stuff", value_name="v").subkey == r"Other\Stuff"


def test_registry_type():
    with pytest.raises(ValueError):
        RegistryPath(r"HKLM\Other\Stuff").registry_type

    p = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.QueryValueEx") as QueryValueEx:
        QueryValueEx.return_value = ("value", winreg.REG_SZ)
        assert p.registry_type == winreg.REG_SZ


def test_parts():
    assert RegistryPath(r"HKLM\Other\Place\ForMe").parts == (
        "HKLM",
        "Other",
        "Place",
        "ForMe",
    )
    assert RegistryPath(r"HKLM\Other\Place\ForMe", value_name="v").parts == (
        "HKLM",
        "Other",
        "Place",
        "ForMe",
        "v",
    )


def test_mkdir():
    p = RegistryPath(r"HKLM\Other\Stuff")
    p.is_dir = MagicMock(return_value=False)
    p.parent._get_subkey_handle = MagicMock()
    p.parent._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.CreateKey") as CreateKey:
        p.mkdir()
        CreateKey.assert_called_once_with("handle", "Stuff")


def test_mkdir_file_exists():
    p = RegistryPath(r"HKLM\Other\Stuff")
    p.is_dir = MagicMock(return_value=True)
    with pytest.raises(FileExistsError):
        p.mkdir()


def test_mkdir_file_exists_but_exist_ok():
    p = RegistryPath(r"HKLM\Other\Stuff")
    p.is_dir = MagicMock(return_value=True)
    p.mkdir(exist_ok=True)


def test_mkdir_parents_true():
    p = RegistryPath(r"HKLM\Other\Stuff")

    for parent in p.parents:
        parent.mkdir = MagicMock()

    p.is_dir = MagicMock(return_value=False)
    p.parent._get_subkey_handle = MagicMock()
    p.parent._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.CreateKey") as CreateKey:
        p.mkdir(parents=True)
        CreateKey.assert_called_once_with("handle", "Stuff")

    for parent in p.parents:
        parent.mkdir.assert_called_once_with(exist_ok=True)


def test_iterdir_not_a_dir():
    p = RegistryPath(r"HKLM\Other\Stuff")
    p.is_dir = MagicMock(return_value=False)
    with pytest.raises(NotADirectoryError):
        list(p.iterdir())


def test_iterdir():
    p = RegistryPath(r"HKLM\Other\Stuff")
    p.is_dir = MagicMock(return_value=True)
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.QueryInfoKey", return_value=(3, 2, 0)) as QueryInfoKey:
        with patch("regpath.winreg.EnumKey", lambda handle, idx: str(idx)):
            with patch(
                "regpath.winreg.EnumValue", lambda handle, idx: (str(idx), "", "")
            ):
                assert list(p.iterdir()) == [
                    RegistryPath(r"HKLM\Other\Stuff\0"),
                    RegistryPath(r"HKLM\Other\Stuff\1"),
                    RegistryPath(r"HKLM\Other\Stuff\2"),
                    RegistryPath(r"HKLM\Other\Stuff", value_name="0"),
                    RegistryPath(r"HKLM\Other\Stuff", value_name="1"),
                ]

    QueryInfoKey.assert_called_once_with("handle")


def test_unlink_not_a_file():
    p = RegistryPath(r"HKLM\Other\Stuff")
    with pytest.raises(FileNotFoundError):
        p.unlink()


def test_unlink_file_not_found():
    p = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with pytest.raises(FileNotFoundError):
        with patch(
            "regpath.winreg.DeleteValue", side_effect=FileNotFoundError
        ) as DeleteValue:
            p.unlink()

    DeleteValue.assert_called_once_with("handle", "v")


def test_unlink_file_not_found_missing_ok():
    p = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with patch(
        "regpath.winreg.DeleteValue", side_effect=FileNotFoundError
    ) as DeleteValue:
        p.unlink(missing_ok=True)

    DeleteValue.assert_called_once_with("handle", "v")


def test_rmdir():
    p = RegistryPath(r"HKLM\Other\Stuff")
    p.iterdir = MagicMock(side_effect=StopIteration())
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.DeleteKey") as DeleteKey:
        p.rmdir()

    DeleteKey.assert_called_once_with("handle", "Stuff")


def test_rmdir_non_empty():
    p = RegistryPath(r"HKLM\Other\Stuff")

    def iterdir():
        for i in range(2):
            yield i

    p.iterdir = iterdir
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with pytest.raises(OSError):
        p.rmdir()


def test_rmtree():
    p = RegistryPath(r"HKLM\Other\Stuff")
    p.rmdir = MagicMock()

    p1 = RegistryPath(r"HKLM\Other\Stuff\Inner")
    p1.is_dir = lambda: True
    p1.rmtree = MagicMock()

    p2 = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p2.is_dir = lambda: False
    p2.unlink = MagicMock()

    def iterdir():
        for i in [p1, p2]:
            yield i

    p.iterdir = iterdir

    p.rmtree()
    p1.rmtree.assert_called_once_with()
    p2.unlink.assert_called_once_with()
    p.rmdir.assert_called_once_with()


def test_with_value_name():
    p = RegistryPath(r"HKLM\Other\Stuff", computer="steve")
    p1 = p.with_value_name("v")
    assert p1 == RegistryPath(r"HKLM\Other\Stuff", value_name="v", computer="steve")


def test_read_raw():
    p = RegistryPath(r"HKLM\Other\Stuff")
    with pytest.raises(ValueError):
        p.read_raw()

    p = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.QueryValueEx", return_value=(b"abc", 1)) as QueryValueEx:
        assert p.read_raw() == (b"abc", 1)

    QueryValueEx.assert_called_once_with("handle", "v")


def test_read():
    p = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p.read_raw = MagicMock(return_value=(1, 2))

    assert p.read("test") == 1

    p.read_raw.assert_called_once_with("test")


def test_write_raw():
    p = RegistryPath(r"HKLM\Other\Stuff")
    with pytest.raises(ValueError):
        p.write_raw(1, 2)

    p = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p._get_subkey_handle = MagicMock()
    p._get_subkey_handle().__enter__.return_value = "handle"
    with patch("regpath.winreg.SetValueEx") as SetValueEx:
        p.write_raw(1, 2)

    SetValueEx.assert_called_once_with("handle", "v", 0, 2, 1)


def test_write_no_guessing():
    class RegistryPathWithRegistryType(RegistryPath):
        registry_type = 3

    p = RegistryPathWithRegistryType(r"HKLM\Other\Stuff", value_name="v")
    p.with_value_name = lambda x: p
    p.write_raw = MagicMock()

    p.write(1)

    p.write_raw.assert_called_once_with(1, 3, "v")


@pytest.mark.parametrize(
    "value, expected_type",
    [
        (1, winreg.REG_DWORD),
        (0xFFFFFFFFFF, winreg.REG_QWORD),
        ("hello", winreg.REG_SZ),
        ("%hello%", winreg.REG_EXPAND_SZ),
        (["hi", "world"], winreg.REG_MULTI_SZ),
        (None, winreg.REG_NONE),
        (b"123", winreg.REG_BINARY),
    ],
)
def test_write_guessing(value, expected_type):

    p = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p.write_raw = MagicMock()
    p.write(value, read_type=False)

    p.write_raw.assert_called_once_with(value, expected_type, "v")


def test_write_negative_number_error():
    p = RegistryPath(r"HKLM\Other\Stuff", value_name="v")
    p.write_raw = MagicMock()

    with pytest.raises(ValueError):
        p.write(-1, read_type=False)
