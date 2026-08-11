"""Unit tests for the centralized security helpers."""
import os

import pytest
from werkzeug.exceptions import NotFound

from app.security import send_stored_file, parse_int


def test_parse_int_valid_and_invalid():
    assert parse_int("5") == 5
    assert parse_int(5) == 5
    assert parse_int(None) is None
    assert parse_int("abc") is None
    assert parse_int("") is None


def test_send_stored_file_serves_file_inside_uploads(app):
    """A file that really lives under the uploads root is served."""
    with app.app_context():
        root = os.path.join(app.root_path, "uploads", "_pytest_tmp")
        os.makedirs(root, exist_ok=True)
        fpath = os.path.join(root, "ok.txt")
        with open(fpath, "w") as f:
            f.write("hello")
        try:
            with app.test_request_context():
                resp = send_stored_file(fpath)
                assert resp.status_code == 200
        finally:
            os.remove(fpath)
            os.rmdir(root)


@pytest.mark.parametrize("bad_path", [
    "/etc/passwd",                       # absolute, outside uploads
    "../../../../etc/passwd",            # traversal out of uploads
    "uploads/../../../etc/passwd",       # traversal after the uploads prefix
    "",                                  # empty
    None,                                # missing
])
def test_send_stored_file_rejects_paths_outside_uploads(app, bad_path):
    """Anything that resolves outside the uploads roots must 404, never serve."""
    with app.app_context(), app.test_request_context():
        with pytest.raises(NotFound):
            send_stored_file(bad_path)
