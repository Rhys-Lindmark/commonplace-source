"""Regression: public quote provenance must not carry document-access credentials."""
import ast
from pathlib import Path
source=Path(__file__).resolve().parents[1]/'scripts/import_quotekg.py'
tree=ast.parse(source.read_text())
nodes=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module=='urllib.parse' or isinstance(n,ast.FunctionDef) and n.name=='sanitize_citation_url']
namespace={};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
clean=namespace['sanitize_citation_url']
assert clean('https://example.com/doc?access_key=example-only')=='https://example.com/doc'
assert clean('https://example.com/doc?a=1&access_key=example-only&b=2#p3')=='https://example.com/doc?a=1&b=2#p3'
assert clean('https://example.com/doc?token=example-only&api_key=example-only')=='https://example.com/doc'
assert clean('https://example.com/doc?X-Amz-Signature=example-only&format=pdf')=='https://example.com/doc?format=pdf'
assert clean('https://example.com/doc?a=1#p3')=='https://example.com/doc?a=1#p3'
print('PASS: citation URLs strip access credentials and preserve normal query parameters/fragments.')
