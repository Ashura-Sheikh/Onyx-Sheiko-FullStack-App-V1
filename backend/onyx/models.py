"""Response models: the shape of every API response.

FastAPI checks each response against its model before sending it, and the
OpenAPI schema is generated from these. The frontend's types are generated
from that schema (frontend/src/api-types.ts), so the two can't drift apart:
a test fails if the committed schema or the generated types are out of date.

Field names match the JSON exactly. Where the JSON name isn't a valid Python
name ("from", "in-progress"), the field has an alias.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Stage = Literal["open", "in-progress", "in-review", "done"]
Priority = Literal["high", "normal", "low"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ErrorResponse(Model):
    detail: str


class SessionStatus(Model):
    authenticated: bool


class Health(Model):
    status: str


class StageCounts(Model):
    open: int
    in_progress: int = Field(alias="in-progress")
    in_review: int = Field(alias="in-review")
    done: int


class TaskSummary(Model):
    path: str
    title: str
    status: Stage | None
    priority: Priority | None
    due: str | None = Field(description="YYYY-MM-DD")


class RecentNote(Model):
    path: str
    title: str
    folder: str
    updated: str = Field(description="ISO 8601 time")


class HistoryEntry(Model):
    at: str = Field(description="ISO 8601 time")
    path: str
    title: str
    from_stage: str = Field(alias="from")
    to: Stage
    remark: str | None


class HomeData(Model):
    today: str = Field(description="YYYY-MM-DD")
    counts: StageCounts
    due: list[TaskSummary]
    waiting: list[TaskSummary]
    recent_notes: list[RecentNote]
    history: list[HistoryEntry]


class Item(Model):
    kind: Literal["note", "task"]
    path: str
    title: str


class ItemList(Model):
    items: list[Item]


class TaskHistoryEntry(Model):
    at: str = Field(description="ISO 8601 time")
    from_stage: str = Field(alias="from")
    to: Stage
    remark: str | None


class TaskDetail(Model):
    status: Stage | None
    priority: Priority | None
    due: str | None = Field(description="YYYY-MM-DD")
    projects: list[str]
    created: str | None
    completed: str | None
    closed_by: str | None
    time_to_close_minutes: int | None
    history: list[TaskHistoryEntry]


class NoteRef(Model):
    path: str
    title: str


class TaskRef(Model):
    path: str
    title: str
    status: Stage | None


class NoteDetail(Model):
    path: str
    title: str
    folder: str
    kind: Literal["note", "task"]
    updated: str = Field(description="ISO 8601 time")
    tags: list[str]
    body: str
    links: dict[str, str | None] = Field(
        description="Each [[link]] target in the body, and the note it opens (null: none)"
    )
    backlinks: list[NoteRef]
    related_tasks: list[TaskRef]
    task: TaskDetail | None


class NoteSummary(Model):
    path: str
    title: str
    folder: str
    updated: str = Field(description="ISO 8601 time")
    tags: list[str]


class NoteList(Model):
    notes: list[NoteSummary]


class SnippetPart(Model):
    text: str
    match: bool


class SearchResult(Model):
    path: str
    title: str
    kind: Literal["note", "task"]
    folder: str
    snippet: list[SnippetPart] = Field(
        description="Body text around the match, matched words marked"
    )


class SearchResults(Model):
    results: list[SearchResult]
