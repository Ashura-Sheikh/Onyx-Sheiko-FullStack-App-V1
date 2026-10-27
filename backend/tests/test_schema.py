"""The committed OpenAPI schema matches the app, and every endpoint has a
typed response, so the generated frontend types are worth having."""

import json

from onyx.schema import SCHEMA_FILE, openapi_schema, schema_text


def test_committed_schema_is_up_to_date():
    assert SCHEMA_FILE.read_text(encoding="utf-8") == schema_text(), (
        "frontend/openapi.json is out of date: run `uv run python -m onyx.schema` "
        "in backend/, then `npm run gen:api` in frontend/"
    )


def test_every_json_response_has_a_named_model():
    schema = openapi_schema()
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for status, response in operation["responses"].items():
                content = response.get("content", {}).get("application/json")
                if content is None:
                    continue  # 204: no body
                ref = content["schema"].get("$ref")
                assert ref and ref.startswith("#/components/schemas/"), (method, path, status)


def test_schema_lists_the_api_and_nothing_else():
    paths = set(openapi_schema()["paths"])
    assert paths == {"/api/session", "/api/home", "/api/items", "/api/note", "/api/health"}


def test_schema_file_is_plain_json():
    assert json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))["openapi"].startswith("3.")
