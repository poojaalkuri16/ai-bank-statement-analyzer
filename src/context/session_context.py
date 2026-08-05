from typing import Any


class SessionContextManager:
    """
    Manages the state of the current analysis session.
    """

    _UPLOADED_FILES = "uploaded_files"
    _ACTIVE_FILE = "active_file"
    _STATUS = "status"
    _METADATA = "metadata"

    STATUS_NOT_STARTED = "NOT_STARTED"
    STATUS_PARSING = "PARSING"
    STATUS_CATEGORIZING = "CATEGORIZING"
    STATUS_VALIDATING = "VALIDATING"
    STATUS_REPORT_READY = "REPORT_READY"
    STATUS_FAILED = "FAILED"

    def __init__(self) -> None:

        self._state = {
            self._UPLOADED_FILES: [],
            self._ACTIVE_FILE: None,
            self._STATUS: self.STATUS_NOT_STARTED,
            self._METADATA: {},
        }

    def add_file(
        self,
        file_path: str,
    ) -> None:

        if file_path not in self._state[self._UPLOADED_FILES]:
            self._state[self._UPLOADED_FILES].append(file_path)

        self._state[self._ACTIVE_FILE] = file_path

    def set_active_file(
        self,
        file_path: str,
    ) -> None:

        if file_path not in self._state[self._UPLOADED_FILES]:
            raise ValueError(
                "File is not part of the current session."
            )

        self._state[self._ACTIVE_FILE] = file_path

    def get_active_file(
        self,
    ) -> str | None:

        return self._state[self._ACTIVE_FILE]

    def get_uploaded_files(
        self,
    ) -> list[str]:

        return list(
            self._state[self._UPLOADED_FILES]
        )

    def update_status(
        self,
        status: str,
    ) -> None:

        self._state[self._STATUS] = status

    def get_status(
        self,
    ) -> str:

        return self._state[self._STATUS]

    def update_metadata(
        self,
        key: str,
        value: Any,
    ) -> None:

        self._state[self._METADATA][key] = value

    def get_metadata(
        self,
        key: str | None = None,
    ) -> Any:
        """
        Return a single metadata entry if a key is supplied.
        Otherwise return a copy of all metadata.
        """

        metadata = self._state[self._METADATA]

        if key is None:
            return dict(metadata)

        return metadata.get(key)

    def clear_session(
        self,
    ) -> None:

        self._state = {
            self._UPLOADED_FILES: [],
            self._ACTIVE_FILE: None,
            self._STATUS: self.STATUS_NOT_STARTED,
            self._METADATA: {},
        }