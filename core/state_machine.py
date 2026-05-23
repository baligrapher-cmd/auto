from enum import Enum

class AutoState(Enum):
    INIT = "INIT"
    LOGIN_WAIT = "LOGIN_WAIT"
    OPEN_UPLOAD_PAGE = "OPEN_UPLOAD_PAGE"
    VERIFY_UPLOAD_PAGE = "VERIFY_UPLOAD_PAGE"
    WAIT_QUEUE = "WAIT_QUEUE"
    SELECT_MODE = "SELECT_MODE"
    SET_FILES = "SET_FILES"
    WAIT_PREVIEW = "WAIT_PREVIEW"
    WAIT_METADATA_CONTAINER = "WAIT_METADATA_CONTAINER"
    FILL_METADATA = "FILL_METADATA"
    VERIFY_FILLED = "VERIFY_FILLED"
    FILL_LOCATION = "FILL_LOCATION"
    SUBMIT = "SUBMIT"
    CONFIRM_SUCCESS = "CONFIRM_SUCCESS"
    NEXT_BATCH = "NEXT_BATCH"
    DONE = "DONE"
    ERROR = "ERROR"

class UploadResult(Enum):
    SUCCESS = "SUCCESS"
    SUCCESS_DUPLICATE = "SUCCESS_DUPLICATE"
    ERROR = "ERROR"

class UploadMode(Enum):
    SAFE = "SAFE"
    TURBO = "TURBO"

MODE_CONFIG = {
    UploadMode.SAFE: {
        "delay_meta": 0.3,
        "delay_submit": 0.5,
        "batch_size": "gui",
        "auto_watch_folder": False,
        "strict_preview_wait": True,
        "parallel_tabs": "gui"
    },
    UploadMode.TURBO: {
        "delay_meta": 0.05,
        "delay_submit": 0.1,
        "batch_size": "gui",
        "auto_watch_folder": False,
        "strict_preview_wait": False,
        "parallel_tabs": "max_gui"
    }
}
