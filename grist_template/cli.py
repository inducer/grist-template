from __future__ import annotations

import argparse
import ast
import os
import sys
from functools import partial
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, StrictUndefined
from pygrist_mini import GristClient
from strictyaml import Map, Optional, Seq, Str, load


if TYPE_CHECKING:
    from datetime import timezone


UTC  = ZoneInfo("UTC")


YAML_SCHEMA = Map({
    "grist_root_url": Str(),
    "grist_doc_id": Str(),
    Optional("parameters"): Seq(Str()),
    "query": Str(),
    "template": Str(),
    Optional("timezone"): Str(),
    })


# based on https://stackoverflow.com/a/76636602
def exec_with_return(
        code: str, location: str, globals: dict | None,
        locals: dict | None = None,
        ) -> Any:
    a = ast.parse(code)
    last_expression = None
    if a.body:
        if isinstance(a_last := a.body[-1], ast.Expr):
            last_expression = ast.unparse(a.body.pop())
        elif isinstance(a_last, ast.Assign):
            last_expression = ast.unparse(a_last.targets[0])
        elif isinstance(a_last, ast.AnnAssign | ast.AugAssign):
            last_expression = ast.unparse(a_last.target)
    compiled_code = compile(ast.unparse(a), location, "exec")
    exec(compiled_code, globals, locals)
    if last_expression:
        return eval(last_expression, globals, locals)


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


def row_to_object(row: dict[str, Any]) -> object:
    obj = Row()
    obj.__dict__.update(row)
    return obj


def main():
    parser = argparse.ArgumentParser(description="Email merge for Grist")
    parser.add_argument("filename", metavar="FILENAME.YML")
    parser.add_argument("parameters", metavar="PAR", nargs="*")
    parser.add_argument("-n", "--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--api-key", metavar="FILENAME",
                        default=os.path.expanduser("~/.grist-api-key"))
    args = parser.parse_args()

    sys.path.append(os.path.dirname(os.path.abspath(args.filename)))

    with open(args.filename) as inf:
        yaml_doc = load(inf.read(), YAML_SCHEMA)

    with open(args.api_key) as inf:
        api_key = inf.read().strip()

    env = Environment(undefined=StrictUndefined)
    if "timezone" in yaml_doc:
        from zoneinfo import ZoneInfo
        from_ts = partial(
                    format_timestamp,
                    timezone=ZoneInfo(yaml_doc["timezone"].text))
    else:
        from warnings import warn
        warn("'timezone' key not specified, timestamps will be local", stacklevel=1)
        from_ts = format_timestamp
    env.filters["format_timestamp"] = from_ts
    env.filters["format_date_timestamp"] = format_date_timestamp

    client = GristClient(
            yaml_doc["grist_root_url"].text,
            api_key,
            yaml_doc["grist_doc_id"].text)

    query = yaml_doc["query"].text

    if "parameters" in yaml_doc:
        nrequired = len(yaml_doc["parameters"])
        nsupplied = len(args.parameters)
        if nrequired != nsupplied:
            raise ValueError(
                f"{nrequired} parameters required, {nsupplied} supplied")

        param_values = {name.text: value
                        for name, value in zip(yaml_doc["parameters"],
                                               args.parameters,
                                               strict=True)}
        query = env.from_string(query).render(param_values)
    else:
        param_values = {}

    template = env.from_string(yaml_doc["template"].text)
    print(template.render({
        "rows": [row_to_object(row) for row in client.sql(query)]
    }))

# vim: foldmethod=marker
