"""Use case: Writes portable archives without wall-clock or temporary-file metadata.

What it does: Fixes ZIP container metadata and streams trusted renderer files in
bounded chunks; real report timestamps remain inside the exported document.
"""

from pathlib import Path, PurePosixPath
from shutil import copyfileobj
from typing import Any, cast
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


class ReproducibleZip(ZipFile):
    def _entry(self, name: str, compression: int | None, level: int | None) -> ZipInfo:
        if name.startswith("/") or ".." in PurePosixPath(name).parts or "\\" in name:
            raise ValueError("Invalid renderer archive member")
        value = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        value.create_system = 3
        value.external_attr = 0o600 << 16
        value.compress_type = ZIP_DEFLATED if compression is None else compression
        # Python 3.12's real ZipInfo slot is omitted from its typing stub.
        cast(Any, value)._compresslevel = 6 if level is None else level
        return value

    def writestr(
        self,
        zinfo_or_arcname: Any,
        data: Any,
        compress_type: Any = None,
        compresslevel: Any = None,
    ) -> None:
        name = (
            zinfo_or_arcname.filename if isinstance(zinfo_or_arcname, ZipInfo) else zinfo_or_arcname
        )
        super().writestr(self._entry(name, compress_type, compresslevel), data)

    def write(
        self,
        filename: Any,
        arcname: Any = None,
        compress_type: Any = None,
        compresslevel: Any = None,
    ) -> None:
        name = str(arcname) if arcname is not None else Path(filename).name
        with (
            open(filename, "rb") as source,
            self.open(self._entry(name, compress_type, compresslevel), "w") as destination,
        ):
            copyfileobj(source, destination, length=64 * 1024)
