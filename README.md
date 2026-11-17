# pybot-seed-provenance

PyBot's `--seed` is documented as fixing its *wording*. This tool replays a corpus of your own
prompts through PyBot at several seeds and tells you, turn by turn, whether the seed changed the
**wording**, the **answering module**, or **both** — because a rule-based bot that silently changes
which of its 110 modules answers is a reproducibility bug, not a paraphrase.

Why now: PyBot is a 640k-line, no-weights chatbot that an agent swarm wrote, with a `--seed` flag
and 110 competing modules under `bot/modules/`. It ships no way to tell a seed-paraphrase apart from
a module reassignment, and no way to separate a real answer from the interface's hardcoded fallback.

Upstream: https://github.com/huggingface/pybot

## What the upstream is, and what it does not answer

PyBot (`huggingface/pybot`) is a chatbot written entirely in Python: no weights, no training, just
if-else branches, regex patterns and lookup tables. Every turn, each module in `bot/modules/` may
propose a reply and an arbiter picks one. The README documents exactly one reproducibility knob:

> `-s N`, `--seed N` | fix PyBot's choice of wording, to get the same replies again
> — [README.md#L70](https://github.com/huggingface/pybot/blob/main/README.md#L70)

Two things follow, and neither is covered by the upstream:

1. **"Wording" is an assumption, not a measurement.** If two seeds pick two different modules, the
   reply is not a paraphrase of the same answer — it is a different answer from a different rule
   set. The upstream has no test or flag that separates the two cases. (No open issues exist on the
   repository as of 2026-11-18; the claim above is the only documented statement of seed semantics.)
2. **The interface hides failures.** `bot/__main__.py` wraps every turn in `except Exception` and
   prints `"Hello!"`
   ([bot/__main__.py#L13-L14](https://github.com/huggingface/pybot/blob/main/bot/__main__.py#L13-L14)).
   A crashed turn and a genuine greeting are byte-identical on stdout. Replaying the same prompt at
   several seeds is the only offline way to notice that a turn is being answered by the fallback.

This tool measures both, using nothing but PyBot's public command line (`-s`, `-v`, stdin).

## What it does / does not do

It does:

- run `python -m pybot -s <seed> -v` once per seed, feeding the whole corpus on stdin;
- pair every stdout reply with the matching `[module: <name> | <N> ms]` line from stderr;
- classify every prompt as `stable`, `wording-only`, `module-only` or `module-and-text`;
- count prompts that get the `Hello!` fallback, and prompts where a single seed does not reproduce
  itself (`--repeat`), which is the null-hypothesis check for the harness;
- rank modules by wins and report each module's own median / p95 turn time;
- list module files on disk that never won a turn on this corpus (corpus-relative, labelled as such).

It does not: judge answer quality, import PyBot internals, patch upstream, or touch the network.

## Install and run

Python 3.8+, standard library only. Nothing to install. First command, after `git clone` of this
repository — it needs no upstream and no network, and reproduces `examples/out/report.txt`:

```sh
python3 bin/pybot-seed-provenance --corpus examples/in/prompts.txt \
  --pybot-root tests/fake_pybot --runner "python3 $PWD/tests/stub_runner.py" --seeds 0,1,2 --repeat 2
```

Then point it at a real checkout (`--pybot-root`) instead of the fixture. On a slow machine PyBot
compiles its 640k lines once per seed run, so allow a few seconds per seed:

```sh
git clone --depth=1 https://github.com/huggingface/pybot /tmp/pybot
python3 bin/pybot-seed-provenance --corpus examples/in/prompts.txt --pybot-root /tmp/pybot --repeat 2
```

Options:

| Option | Default | Meaning |
|---|---|---|
| `--corpus PATH` | required | one prompt per line; blank lines and `#` lines skipped |
| `--pybot-root PATH` | required | checkout whose `bot/` package is runnable |
| `--seeds 0,1,2` | `0,1,2,3` | comma separated seeds |
| `--repeat N` | `1` | run each seed N times; any difference under one seed is reported |
| `--runner CMD` | `python3 -m pybot` | how to start PyBot (useful for a pinned interpreter) |
| `--timeout SEC` | `180` | per seed run |
| `--json` | off | machine-readable report on stdout |

### `--json` output

```json
{
  "tool": "pybot-seed-provenance",
  "version": "1.0.0",
  "summary": {
    "prompts": 9,
    "observations": 36,
    "classes": {"stable": 9},
    "drifted": 0,
    "stability_rate": 1.0,
    "wording_only_rate": 0.0,
    "module_churn_rate": 0.0,
    "fallback_hello": 0,
    "repeat_mismatch": 0,
    "distinct_modules_seen": 1,
    "module_files_on_disk": null
  },
  "modules": [{"module": "greet", "wins": 36, "prompts": 9, "median_ms": 3, "p95_ms": 3}],
  "modules_never_seen": [],
  "prompts": [{"index": 0, "text": "hi", "class": "stable", "distinct_replies": 1,
               "distinct_modules": 1, "modules": ["greet"], "replies": ["Hi there."],
               "fallback_hello": false, "repeat_mismatch": {}}],
  "drift": false
}
```

(The block above is trimmed for length; the real report keeps one `prompts` entry per prompt. It is
the fixture-stub shape, used by the tests — see `Limits`.)

### Exit codes

| Code | Meaning |
|---|---|
| `0` | every prompt is `stable`, no fallback reply, every seed reproduced itself |
| `1` | drift found: any `wording-only` / `module-only` / `module-and-text`, any `Hello!` fallback, or a seed that did not reproduce |
| `2` | usage or input error: unreadable/empty corpus, bad `--seeds`, missing `bot/` package, runner failure, or reply/module desync |

## Tests

```sh
python3 -m unittest discover -s tests
```

18 tests (15 behavioral: they drive the CLI and assert exit codes, classes and JSON fields). The two
fixtures are honest stand-ins for PyBot's surface, not for its content: `tests/stub_runner.py`
reproduces the `-s` / stdin / `-v` contract, and `tests/fake_pybot/bot/modules/` gives the inventory
check something to read.

## Limits

- **Corpus-relative by construction.** `modules_never_seen` means "never won on these prompts", not
  "dead code". A 9-prompt corpus cannot reach 110 modules.
- **Only the public CLI.** The tool sees the winning module, not the runner-up proposals; it cannot
  say *why* the arbiter changed its mind.
- **Wall-clock numbers are PyBot's own.** `median_ms` / `p95_ms` are the per-turn timings that
  `-v` prints, rounded to whole milliseconds by upstream.
- **The fixture tests prove the classifier, not upstream behaviour.** Numbers in `examples/out/`
  come from `tests/stub_runner.py`. Upstream numbers, if present, are labelled with the commit and
  command that produced them.
- No upstream checkout is vendored here: the tool needs `--pybot-root`, so the repository stays small
  and the upstream version you audit is the one you pin.

## 与同类项目的差异

Searched before writing (`/tmp/similar.md` in the build log; commands were `gh search repos
"chatbot seed reproducibility"`, `gh search repos "pybot audit"`, `gh search code "pybot-seed"`,
`gh search repos "nondeterminism rule engine seed"`). No repository, and no code hit inside
`huggingface/pybot`, does seed-provenance classification. Related but different: chat-transcript
diff tools compare two *models* on one input; this compares one model (a rule engine) across seeds
and separates wording churn from module churn, which is the failure mode unique to an arbiter-based
bot.

## 本轮创新

First measurement of **seed provenance** for an arbiter-based rule chatbot: it turns the upstream's
one-line claim ("fix the choice of wording") into a four-way, per-turn classification with a
null-hypothesis control (same seed twice) and a fallback detector tied to the interface's
`except Exception → "Hello!"`. Nothing in the ledger or in the upstream repo does this: existing
MCP/contract tools compare static schemas, transcript tools compare two models, and PyBot itself has
no test for seed semantics.

## License

MIT. Upstream PyBot is Apache-2.0; no upstream code is copied here.