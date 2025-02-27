# Basic Templating for for Grist

Supply a YAML file as configuration, as in [this example](example.yml).
Via the document ID and SQL query, point at data in a
[Grist](https://github.com/gristlabs/grist-core) document.

Optionally, it inserts or update records in the database based on the
data processed.

## Install

```
pip install grist-template
```

or

```
pipx install grist-mailmerge
```
## Use

```
grist-template config.yml
```

## "Documentation"

See the [this example](example.yml) and the command line help.
