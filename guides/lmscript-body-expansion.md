# Lmscript-owned body formatting

Lmscript compiles higher-level constructs into ordinary lmcode before the inner
compiler runs. A formatted string in an `_lmcode_` body is such a construct;
standalone lmcode has no formatted-string syntax. `${}` values and `with=[...]`
fragments remain outer-layer features as well. Strings never become code.

```lmscript
program = _lmcode_ cli="lmcode-cpp-sample";
let name = "LMCODE";
print(f"{name} has {str_len(name)} chars");
end _lmcode_
result = run_lmcode(program);
print(json_stringify(result));
```

The body lowers to ordinary `print(name + " has " + str(str_len(name)) + " chars");`.
Fields evaluate once, left to right when the VM executes; checking/compiling does
not execute them. String and enum fields retain their bytes, numeric/bool fields
use the existing conversions (including the existing float text). Ordinary
`str(string)` is still an error; the wrapper does not relax inner typing.

Use doubled braces for literal braces and the normal short-string escapes.
Empty fields, objects/void, unmatched braces, format specifiers and nested body
formatted strings are rejected at their original body positions. Bind an inner
formatted value first. Comments, ordinary strings and raw heredoc data are not
rewritten. Values spliced into expression fields remain literals.

The compiler emits the same bytecode, including original source locations, as
before the layering move. Runtime implementations and host schemas do not change.
