from __future__ import annotations

import os
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import typed_argparse as tap
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, Field
from pygrist_mini import GristClient


if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import timezone


UTC  = ZoneInfo("UTC")


class TemplateDocument(BaseModel):
    grist_root_url: str
    grist_doc_id: str

    parameters: list[str] = Field(default_factory=list)

    query: str
    template: str

    timezone: str | None = None


def format_date_timestamp(
            tstamp: float,
            format: str = "%Y-%m-%d",
        ) -> str:
    import datetime
    dt = datetime.datetime.fromtimestamp(tstamp, tz=UTC).date()
    return dt.strftime(format)


def format_timestamp(
            tstamp: float,
            format: str = "%c",
            timezone: timezone | None = None
        ) -> str:
    import datetime
    dt = datetime.datetime.fromtimestamp(tstamp, tz=timezone)
    return dt.strftime(format)


class Row:
    pass


def row_to_object(row: dict[str, Any]) -> Row:
    obj = Row()
    obj.__dict__.update(row)
    return obj


def sql_query(client: GristClient, query: str, *args: str) -> Sequence[Row]:
    return [row_to_object(row) for row in client.sql(query, args)]


class RenderArgs(tap.TypedArgs):
    filename: str = tap.arg(positional=True, metavar="FILENAME")
    parameters: list[str] = tap.arg(positional=True)
    dry_run: bool = tap.arg("-n")
    verbose: bool = tap.arg("-v")

    api_key: str = tap.arg(
                    metavar="FILENAME",
                    default=os.path.expanduser("~/.grist-api-key"))


def render(args: RenderArgs):
    from saneyaml import load
    data = load(Path(args.filename).read_text())

    doc = TemplateDocument.model_validate(data)

    grist_api_key = Path(args.api_key).read_text().strip()
    client = GristClient(doc.grist_root_url, grist_api_key, doc.grist_doc_id)

    env = Environment(undefined=StrictUndefined)
    if doc.timezone is not None:
        from zoneinfo import ZoneInfo
        from_ts = partial(
                    format_timestamp,
                    timezone=ZoneInfo(doc.timezone))  # pyright: ignore[reportArgumentType]
    else:
        from warnings import warn
        warn("'timezone' key not specified, timestamps will be local", stacklevel=1)
        from_ts = format_timestamp
    env.filters["format_timestamp"] = from_ts
    env.filters["format_date_timestamp"] = format_date_timestamp
    env.globals["q"] = partial(sql_query, client)  # pyright: ignore[reportArgumentType]
    env.globals["file_exists"] = os.path.exists

    query = doc.query

    if doc.parameters:
        nrequired = len(doc.parameters)
        nsupplied = len(args.parameters)
        if nrequired != nsupplied:
            raise ValueError(
                f"{nrequired} parameters required, {nsupplied} supplied")

        param_values = dict(zip(doc.parameters,
                                               args.parameters,
                                               strict=True))
        query = env.from_string(query).render(param_values)
    else:
        param_values = {}

    template = env.from_string(doc.template)
    print(template.render({
        "rows": [row_to_object(row) for row in client.sql(query)],
        **param_values,
    }))


def main():
    tap.Parser(RenderArgs).bind(render).run()


if __name__ == "__main__":
    main()

# vim: foldmethod=marker
