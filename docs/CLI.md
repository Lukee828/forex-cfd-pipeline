# Alpha Registry CLI

> Generated from `alpha_factory.registry_cli` help output.

## Top-level

```text
usage: alpha-registry [-h] [--db DB]
                      {init,register,list,best,summary,backup,refresh-runs,search,lineage,export}
                      ...

positional arguments:
  {init,register,list,best,summary,backup,refresh-runs,search,lineage,export}

options:
  -h, --help            show this help message and exit
  --db DB
```

## Subcommands

### init

```text
usage: alpha-registry init [-h]

options:
  -h, --help  show this help message and exit
```

### register

```text
usage: alpha-registry register [-h] --cfg CFG --metrics METRICS [--tags TAGS]

options:
  -h, --help         show this help message and exit
  --cfg CFG
  --metrics METRICS
  --tags TAGS
```

### list

```text
usage: alpha-registry list [-h] [--limit LIMIT] [--tag TAG]

options:
  -h, --help     show this help message and exit
  --limit LIMIT
  --tag TAG
```

### best

```text
usage: alpha-registry best [-h] --metric METRIC [--top TOP]

options:
  -h, --help       show this help message and exit
  --metric METRIC
  --top TOP
```

### summary

```text
usage: alpha-registry summary [-h] --metric METRIC

options:
  -h, --help       show this help message and exit
  --metric METRIC
```

### backup

```text
usage: alpha-registry backup [-h] [--retention RETENTION] [--dir DIR]

options:
  -h, --help            show this help message and exit
  --retention RETENTION
  --dir DIR
```

### refresh-runs

```text
usage: alpha-registry refresh-runs [-h]

options:
  -h, --help  show this help message and exit
```

### search

```text
usage: alpha-registry search [-h] --metric METRIC [--min MIN] [--max MAX]
                             [--tag TAG] [--limit LIMIT]

options:
  -h, --help       show this help message and exit
  --metric METRIC
  --min MIN
  --max MAX
  --tag TAG
  --limit LIMIT
```

### lineage

```text
usage: alpha-registry lineage [-h] --alpha ALPHA

options:
  -h, --help     show this help message and exit
  --alpha ALPHA
```

### export

```text
usage: alpha-registry export [-h] --what {best,summary} --metric METRIC
                             [--top TOP] [--format {csv,html}]
                             [--theme {light,dark}] --out OUT

options:
  -h, --help            show this help message and exit
  --what {best,summary}
  --metric METRIC
  --top TOP
  --format {csv,html}
  --theme {light,dark}
  --out OUT
```
