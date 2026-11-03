#!/usr/bin/env python3
"""Differentially check pinned Tree-sitter grammars against published lmscript.

The full local run reads tracked files from mono/skills-scripts/cpp/lmok without
copying their contents into this public repository. Public CI uses the cpp/lmok
roots plus both grammar repositories' committed corpus documents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAMMAR_TESTS = ROOT / "tests" / "grammar"
PINS = json.loads((GRAMMAR_TESTS / "tree-sitter-pins.json").read_text())
CORPUS_RE = re.compile(r"^={10,}\r?\n([^\r\n]+)\r?\n={10,}\r?\n([\s\S]*?)\r?\n---\r?\n", re.M)
BLOCK_RE = re.compile(r"(_lmcode_|_dsl_)")
MUTATIONS = (
    "\nlet __tree_sitter_diff_missing_value = ;\n",
    "\nif (true) { let __tree_sitter_diff_open_block = 1;\n",
    "\nlet __tree_sitter_diff_unclosed_string = \"unterminated\n",
)


@dataclass(frozen=True)
class Document:
    name: str
    language: str
    tree_source: str
    compiler_source: str
    compiler_name: str
    compiler_cwd: Path
    origin: str
    block_index: int = -1
    mutated: bool = False
    mutation: str = ""


def git_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *patterns], capture_output=True)
    if result.returncode:
        raise RuntimeError(f"cannot enumerate tracked corpus at {root}: {result.stderr.decode(errors='replace')}")
    return [root / item.decode() for item in result.stdout.split(b"\0") if item]


def revision(root: Path) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"source is not a git checkout: {root}")
    return result.stdout.strip()


def corpus_cases(root: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted((root / "test" / "corpus").rglob("*.txt")):
        for index, match in enumerate(CORPUS_RE.finditer(path.read_text(encoding="utf-8"))):
            found.append((f"{path.relative_to(root)}::{match.group(1)}::{index}", match.group(2)))
    return found


def source_files(root: Path, patterns: tuple[str, ...], prefix: str) -> list[tuple[str, str, Path]]:
    files = []
    for path in git_files(root, patterns):
        if path.is_file():
            files.append((f"{prefix}/{path.relative_to(root).as_posix()}", path.read_text(encoding="utf-8"), path))
    return files


def blocks_with_spans(source: str) -> list[tuple[str, str, int, int]]:
    """Return marker, body, and body line range; marker/closer lines follow block rules."""
    lines = source.splitlines(keepends=True)
    blocks: list[tuple[str, str, int, int]] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        found = BLOCK_RE.search(line)
        if not found or line.startswith("end ") or ";" not in line[found.end():]:
            index += 1
            continue
        marker = found.group(1)
        close = index + 1
        while close < len(lines) and lines[close].rstrip("\r\n") != f"end {marker}":
            close += 1
        if close == len(lines):
            index += 1
            continue
        body_lines = lines[index + 1:close]
        blocks.append((marker, "".join(body_lines), index + 1, close))
        index = close + 1
    return blocks


def normalize_code_splices(body: str) -> str:
    """Make computed outer splices deterministic so --check reaches the DSL parser."""
    sys.path.insert(0, str(GRAMMAR_TESTS))
    from prelexer import find_heredocs, substitute_splices
    lines = body.split("\n")
    regions, _ = find_heredocs(lines)
    heredoc_lines = set()
    for start, end in regions:
        heredoc_lines.update(range(start + 1, end + 1))
    return substitute_splices(body, heredoc_lines)


def normalize_source_splices(source: str) -> str:
    lines = source.splitlines(keepends=True)
    for _index, (_marker, body, first, last) in reversed(list(enumerate(blocks_with_spans(source)))):
        normalized = normalize_code_splices(body)
        replacement = normalized.splitlines(keepends=True)
        if normalized and not normalized.endswith(("\n", "\r")):
            replacement[-1] += "\n"
        lines[first:last] = replacement
    return "".join(lines)


def mutate_outer(source: str, mutation: str) -> str:
    return source.rstrip("\r\n") + mutation


def mutate_lmcode_source(source: str, block_index: int, mutation: str) -> tuple[str, str]:
    lines = source.splitlines(keepends=True)
    blocks = blocks_with_spans(source)
    marker, body, first, last = blocks[block_index]
    changed_body = body.rstrip("\r\n") + mutation
    replacement = changed_body.splitlines(keepends=True)
    if changed_body and not changed_body.endswith(("\n", "\r")):
        replacement[-1] += "\n"
    lines[first:last] = replacement
    return "".join(lines), changed_body


def make_document(
    *, name: str, language: str, tree_source: str, compiler_source: str,
    compiler_name: str, compiler_cwd: Path, origin: str, mutated: bool = False,
    mutation: str = "", block_index: int = -1,
) -> Document:
    return Document(name, language, tree_source, compiler_source, compiler_name, compiler_cwd,
                    origin, block_index, mutated, mutation)


def collect_inputs(args: argparse.Namespace, temp: Path) -> tuple[list[Document], dict[str, str]]:
    roots: dict[str, Path] = {}
    for label, env_name, required in (
        ("cpp", "LMCODE_CPP", True), ("lmok", "LMOK", True),
        ("mono", "MONO_ROOT", args.live), ("skills", "SKILLS_ROOT", args.live),
    ):
        value = os.environ.get(env_name)
        if required and not value:
            raise RuntimeError(f"{env_name} is required for this corpus mode")
        if value:
            roots[label] = Path(value).resolve()
    revisions = {label: revision(root) for label, root in roots.items()}
    expected_sources = {"cpp": PINS["lmcode_cpp_corpus_pin"], "lmok": PINS["lmok_corpus_pin"]}
    if "mono" in roots:
        expected_sources["mono"] = PINS["mono_corpus_pin"]
    for label, expected in expected_sources.items():
        if revisions[label] != expected:
            raise RuntimeError(f"{label} corpus pin mismatch: expected {expected}, found {revisions[label]}")

    raw: list[tuple[str, str, Path, str]] = []
    if "mono" in roots:
        raw += [(name, text, path, "mono") for name, text, path in source_files(roots["mono"], ("lmscript/examples/*.lms",), "mono")]
    if "skills" in roots:
        raw += [(name, text, path, "skills-scripts") for name, text, path in source_files(roots["skills"], ("*.lms",), "skills-scripts")]
    raw += [(name, text, path, "lmcode-cpp") for name, text, path in source_files(roots["cpp"], ("sample-suite/**/*.lms",), "lmcode-cpp")]
    raw += [(name, text, path, "lmok") for name, text, path in source_files(roots["lmok"], ("rules/**/*.lms",), "lmok")]

    documents: list[Document] = []
    sources: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    for name, text, path, origin in raw:
        digest = hashlib.sha256(text.encode()).hexdigest()
        if ("lmscript", digest) not in seen:
            documents.append(make_document(name=name, language="lmscript", tree_source=text,
                compiler_source=normalize_source_splices(text), compiler_name=str(path),
                compiler_cwd=path.parent, origin=origin))
            seen.add(("lmscript", digest))
        blocks = blocks_with_spans(text)
        for block_index, (marker, body, _first, _last) in enumerate(blocks):
            digest = hashlib.sha256(body.encode()).hexdigest()
            if ("lmcode", digest) not in seen:
                documents.append(make_document(name=f"{name}::{marker}#{block_index}", language="lmcode",
                    tree_source=body, compiler_source=normalize_source_splices(text), compiler_name=str(path),
                    compiler_cwd=path.parent, origin=origin, block_index=block_index))
                seen.add(("lmcode", digest))
        sources[origin] = revisions.get({"lmcode-cpp": "cpp", "skills-scripts": "skills", "mono": "mono", "lmok": "lmok"}.get(origin, ""), "unavailable")

    # Both public grammar corpora are source inputs in CI and locally. LMScript
    # cases are whole scripts; lmcode cases are wrapped for the real compiler.
    compiler_corpus = temp / "corpus"
    compiler_corpus.mkdir()
    empty_schema = compiler_corpus / "empty-schema.json"
    empty_schema.write_text(json.dumps({"dsl.schema": 2, "name": "diff", "types": {}, "functions": {}, "context": {}}) + "\n")
    grammar_roots = {
        "lmscript": Path(os.environ["TREE_SITTER_LMSCRIPT_ROOT"]).resolve(),
        "lmcode": Path(os.environ["TREE_SITTER_LMCODE_ROOT"]).resolve(),
    }
    for language, grammar_root in grammar_roots.items():
        revision_value = revision(grammar_root)
        expected = PINS[language]["commit"]
        if revision_value != expected:
            raise RuntimeError(f"{language} grammar pin mismatch: expected {expected}, found {revision_value}")
        sources[f"tree-sitter-{language}"] = revision_value
        for label, content in corpus_cases(grammar_root):
            path = compiler_corpus / f"{language}-{len(documents):05d}.lms"
            if language == "lmscript":
                compiler_source = content
                tree_source = content
                doc_language = "lmscript"
            else:
                compiler_source = f'program = _lmcode_ schema={json.dumps(str(empty_schema))};\n{content}\nend _lmcode_\n'
                compiler_source = normalize_source_splices(compiler_source)
                tree_source = content
                doc_language = "lmcode"
            documents.append(make_document(name=f"{label}", language=doc_language,
                tree_source=tree_source, compiler_source=compiler_source,
                compiler_name=str(path), compiler_cwd=compiler_corpus,
                origin=f"tree-sitter-{language}-corpus"))
    # Deterministic formatted-string seeds exercise nested expressions and
    # escapes in the compiler/tree-sitter differential independently of the
    # grammar corpus count. Keep invalid forms here as compiler refusal seeds.
    fstring_seeds = (
        ('fstring-scalar', 'let value = f"value={str(7)}";'),
        ('fstring-nested-expression', 'let value = f"value={str((2 + 3) * 4)}";'),
        ('fstring-literal-braces', 'let value = f"{{literal}}";'),
        ('fstring-escape', 'let value = f"line\\n{str(1)}";'),
        ('fstring-no-nested-format', 'let value = f"{f"nested"}";'),
        ('fstring-unclosed-field', 'let value = f"{str(1)";'),
        ('fstring-format-spec-refused', 'let value = f"{str(1):04}";'),
    )
    for label, content in fstring_seeds:
        path = compiler_corpus / f"lmcode-fstring-{len(documents):05d}.lms"
        wrapped = f'program = _lmcode_ schema={json.dumps(str(empty_schema))};\n{content}\nend _lmcode_\n'
        documents.append(make_document(name=f"fstring-seed::{label}", language="lmcode",
            tree_source=content, compiler_source=wrapped, compiler_name=str(path),
            compiler_cwd=compiler_corpus, origin="formatted-string-seed"))
    return documents, sources


def build_library(cli: str, grammar_root: Path, output: Path) -> None:
    result = subprocess.run([cli, "build", str(grammar_root), "--output", str(output)], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Tree-sitter build failed for {grammar_root}: {result.stdout}{result.stderr}")


def tree_sitter_verdicts(cli: str, library: Path, lang: str, documents: list[Document], scratch: Path) -> dict[str, tuple[bool | None, str]]:
    selected = [doc for doc in documents if doc.language == lang]
    files: list[Path] = []
    by_path: dict[str, Document] = {}
    for index, doc in enumerate(selected):
        extension = ".lmcode" if lang == "lmcode" else ".lms"
        path = scratch / f"{lang}-{index:06d}{extension}"
        path.write_text(doc.tree_source, encoding="utf-8")
        files.append(path)
        by_path[str(path)] = doc
    if not files:
        return {}
    paths_file = scratch / f"{lang}-paths.txt"
    paths_file.write_text("\n".join(map(str, files)) + "\n")
    result = subprocess.run([cli, "parse", "--json-summary", "--lib-path", str(library),
        "--lang-name", lang, "--paths", str(paths_file)], text=True, capture_output=True)
    try:
        # On parse errors the CLI prints one human-readable error line per
        # source before its JSON summary. Read the final object, not those lines.
        start = result.stdout.rfind("\n{")
        payload = result.stdout[start + 1:] if start >= 0 else result.stdout
        summary = json.loads(payload)
    except json.JSONDecodeError:
        raise RuntimeError(f"Tree-sitter parse failed for {lang}: {result.stdout}{result.stderr}")
    verdicts: dict[str, tuple[bool | None, str]] = {}
    for source in summary.get("parse_summaries", []):
        path = source.get("file", "")
        doc = by_path.get(path)
        if not doc:
            raise RuntimeError(f"Tree-sitter result has unknown source path {path}")
        successful = source.get("successful") is True
        verdicts[doc.name] = (successful, "" if successful else "Tree-sitter reported ERROR or MISSING nodes")
    missing = [doc.name for doc in selected if doc.name not in verdicts]
    if missing:
        raise RuntimeError(f"Tree-sitter omitted {len(missing)} {lang} parse results; first={missing[0]}")
    return verdicts


def compiler_verdict(cli: str, doc: Document, env: dict[str, str]) -> tuple[bool | None, str]:
    for attempt in range(8):
        result = subprocess.run([cli, "--check", "--source-name", doc.compiler_name, "-"],
            input=doc.compiler_source, text=True, capture_output=True, cwd=doc.compiler_cwd, env=env)
        message = (result.stderr + result.stdout).strip().splitlines()
        detail = message[0] if message else f"lmscript exit {result.returncode}"
        if result.returncode != 1 or "EAGAIN" not in detail or attempt == 7:
            break
        time.sleep(0.1)
    if result.returncode == 0:
        return True, ""
    if result.returncode == 2:
        return False, detail if message else "compile error without a diagnostic"
    return None, detail


def divergence_class(doc: Document, message: str) -> str | None:
    lower = message.lower()
    if (doc.language == "lmcode" and doc.origin == "formatted-string-seed"
            and "undefined name 'f'" in lower):
        return "published-baseline"
    if (doc.language == "lmscript" and "fstrings" in doc.name.lower()
            and "undefined function 'f'" in lower):
        return "published-baseline"
    if "import aliases were removed" in lower:
        return "mainline-parser-change"
    if ('is not on path' in lower or 'not found (resolved ' in lower or 'unknown native module' in lower
            or 'not in the tool cache' in lower or 'install github:' in lower):
        return "external-schema"
    if any(term in lower for term in ("unexpected character \"$\"", "lmcode_return_", "no host declared", "unknown option 'out'", "load_schema", "template_extract", "unterminated field before newline", "field cannot cross an uncontinued newline")):
        return "published-baseline"
    if "out=" in doc.tree_source and "expected ';' after the assignment" in lower:
        return "published-baseline"
    if doc.language == "lmcode" and "${" in doc.tree_source and ("//" in doc.tree_source or "/*" in doc.tree_source) and "expected an expression, found '/'" in lower:
        return "published-baseline"
    if doc.language == "lmscript" and any(term in lower for term in ("json", "graphql", "toml", "csv", "_lmcode_", "_cmd_")):
        return "embedded-body"
    semantic = (
        "undefined", "undeclared", "no method", "expects ", "overload", "shadow", "already declared",
        "reserved", "conflicts", "cannot be", "must be", "requires ", "not allowed", "no implicit conversion",
        "has no effect", "unknown name", "unknown type", "does not implement", "interface ", "return is",
        "loop", "range", "duplicate", "schema", "argument", "property", "not a ",
        "command: one command per line", "the dsl body is empty",
    )
    if any(term in lower for term in semantic):
        return "checker-only"
    return None


def append_mutations(documents: list[Document], seed: int, count: int) -> list[Document]:
    rng = random.Random(seed)
    mutated: list[Document] = []
    for doc in documents:
        if doc.mutated:
            continue
        for mutation in rng.sample(MUTATIONS, count):
            if doc.language == "lmcode":
                tree_source = doc.tree_source.rstrip("\r\n") + mutation
                compiler_source = doc.compiler_source
                if doc.origin.startswith("tree-sitter-lmcode-corpus"):
                    compiler_source = re.sub(r"\nend _lmcode_\s*$", mutation + "end _lmcode_\n", doc.compiler_source)
                else:
                    if doc.block_index >= 0:
                        compiler_source, _ = mutate_lmcode_source(doc.compiler_source, doc.block_index, mutation)
                    else:
                        # Body bytes are still checked separately; this wrapper keeps
                        # the compiler oracle tied to exactly the seeded body.
                        compiler_source = doc.compiler_source.rstrip("\r\n") + "\n" + mutation
                mutated.append(Document(doc.name + "::mutant-" + str(MUTATIONS.index(mutation)), doc.language,
                    tree_source, compiler_source, doc.compiler_name, doc.compiler_cwd,
                    doc.origin, doc.block_index, True, mutation.strip()))
            else:
                source = mutate_outer(doc.tree_source, mutation)
                compiler_source = mutate_outer(doc.compiler_source, mutation)
                mutated.append(Document(doc.name + "::mutant-" + str(MUTATIONS.index(mutation)), doc.language,
                    source, compiler_source, doc.compiler_name, doc.compiler_cwd, doc.origin,
                    doc.block_index, True, mutation.strip()))
    return documents + mutated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="also scan the local mono and skills-scripts source roots")
    parser.add_argument("--fixture-only", action="store_true", help="use only the public negative-control fixture")
    parser.add_argument("--only", choices=("lmscript", "lmcode"), help="limit this check to one grammar (control tests)")
    parser.add_argument("--min-documents", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--json", default="", help="write summary metadata without source text")
    args = parser.parse_args()
    cli = os.environ.get("TREE_SITTER", "tree-sitter")
    compiler = os.environ.get("LMSCRIPT_BIN", "lmscript")
    grammar_roots = {lang: Path(os.environ[f"TREE_SITTER_{lang.upper()}_ROOT"]).resolve() for lang in ("lmscript", "lmcode")}
    with tempfile.TemporaryDirectory(prefix="lmcode-tree-diff-") as temp_dir:
        scratch = Path(temp_dir)
        if args.fixture_only:
            fixture = GRAMMAR_TESTS / "fixtures" / "control-valid.lms"
            source = fixture.read_text(encoding="utf-8")
            documents = [make_document(name="control-valid.lms", language="lmscript", tree_source=source,
                compiler_source=source, compiler_name=str(fixture), compiler_cwd=fixture.parent, origin="control-fixture")]
            source_pins = {}
        else:
            documents, source_pins = collect_inputs(args, scratch)
        if args.only:
            documents = [doc for doc in documents if doc.language == args.only]
        documents = append_mutations(documents, args.seed, 1 if args.live else 2)
        if len(documents) < args.min_documents:
            raise RuntimeError(f"differential corpus has {len(documents)} documents; required minimum is {args.min_documents}")

        libraries = {}
        if not args.fixture_only:
            for lang, grammar_root in grammar_roots.items():
                libraries[lang] = scratch / f"{lang}.so"
                build_library(cli, grammar_root, libraries[lang])
        else:
            language = args.only or "lmscript"
            lib_env = os.environ.get(f"TREE_SITTER_{language.upper()}_LIB")
            libraries[language] = Path(lib_env) if lib_env else scratch / f"{language}.so"
            if not lib_env:
                build_library(cli, grammar_roots[language], libraries[language])

        tree_results: dict[str, tuple[bool | None, str]] = {}
        langs = [args.only] if args.only else ["lmscript", "lmcode"]
        for lang in langs:
            tree_results.update(tree_sitter_verdicts(cli, libraries[lang], lang, documents, scratch))

        env = dict(os.environ)
        # Ensure checker source modules/properties do not depend on the runner's profile.
        env.setdefault("LMCTL_NON_INTERACTIVE", "1")
        env["HOME"] = str(scratch / "home")
        Path(env["HOME"]).mkdir()
        env["LMCTL_HOME"] = str(Path(env["HOME"]) / ".lmctl")
        Path(env["LMCTL_HOME"]).mkdir()
        env["LMCTL_DB"] = str(Path(env["HOME"]) / "unused.db")
        lmok_root = os.environ.get("LMOK")
        lmok_schema = Path(lmok_root) / "schema" / "lmok.host.json" if lmok_root else None
        if lmok_schema and lmok_schema.is_file():
            shim_dir = scratch / "bin"
            shim_dir.mkdir()
            shim = shim_dir / "lmok"
            shim.write_text("#!/usr/bin/env python3\nimport pathlib,sys\nif sys.argv[1:] == ['--lmcode-schema','--json']:\n sys.stdout.write(pathlib.Path(" + repr(str(lmok_schema)) + ").read_text())\nelse:\n sys.exit(2)\n")
            shim.chmod(0o755)
            env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
        counts = {"documents": len(documents), "mutated": sum(doc.mutated for doc in documents),
            "valid_sources": 0, "agreement": 0, "divergences": {}, "oracle_unavailable": 0}
        failures: list[str] = []
        report = []
        for doc in documents:
            tree_ok, tree_detail = tree_results[doc.name]
            compiler_ok, message = compiler_verdict(compiler, doc, env)
            if compiler_ok is None:
                counts["oracle_unavailable"] += 1
                failures.append(f"{doc.name}: lmscript oracle failed: {message}")
                continue
            if not doc.mutated and compiler_ok and tree_ok:
                counts["valid_sources"] += 1
            if tree_ok == compiler_ok:
                counts["agreement"] += 1
                continue
            category = divergence_class(doc, message) if not compiler_ok and tree_ok else None
            if category:
                counts["divergences"][category] = counts["divergences"].get(category, 0) + 1
                report.append({"name": doc.name, "origin": doc.origin, "language": doc.language,
                    "tree_sitter": "accept" if tree_ok else "reject", "compiler": "accept" if compiler_ok else "reject",
                    "class": category, "reason": message[:220]})
            else:
                failures.append(f"{doc.name}: tree-sitter={'accept' if tree_ok else 'reject'} compiler={'accept' if compiler_ok else 'reject'}; {message or tree_detail}")
        print(json.dumps({"seed": args.seed, **counts, "sources": source_pins}, sort_keys=True))
        for failure in failures[:25]:
            print("UNCLASSIFIED DIVERGENCE " + failure, file=sys.stderr)
        if failures:
            print(f"RESULT: FAIL ({len(failures)} unclassified accept/reject divergence(s))", file=sys.stderr)
            return 1
        if args.json:
            Path(args.json).write_text(json.dumps({"seed": args.seed, **counts, "sources": source_pins,
                "divergences": report}, indent=2, sort_keys=True) + "\n")
        print(f"RESULT: PASS ({counts['agreement']} agreeing verdicts; {sum(counts['divergences'].values())} documented divergences; {counts['oracle_unavailable']} unavailable schema checks)")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"RESULT: FAIL ({error})", file=sys.stderr)
        sys.exit(1)
