// Optional native n8n2.46.6 syntax check; no workflow, credentials or HTTP.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(process.argv[2]);
const { extendSyntax } = require(path.join(root, 'node_modules/n8n-workflow/dist/cjs/extensions/expression-extension.js'));
function inspect(file) {
  const workflow = JSON.parse(fs.readFileSync(file, 'utf8'));
  const failures = [];
  let count = 0;
  function visit(value, parameter, node) {
    if (typeof value === 'string' && value.startsWith('=')) {
      count++;
      try { extendSyntax(value.slice(1)); }
      catch (error) {
        assert.equal(error.name, 'ExpressionExtensionError');
        assert.equal(error.message, 'invalid syntax');
        failures.push({ node, parameter, error: 'ExpressionExtensionError:invalid syntax' });
      }
    } else if (value && typeof value === 'object') {
      for (const [key, child] of Object.entries(value)) visit(child, parameter + '/' + key, node);
    }
  }
  workflow.nodes.forEach((node, index) => visit(node.parameters, '/nodes/' + index + '/parameters', node.name));
  return { count, failures };
}
const baseline = inspect(process.argv[3]);
const candidate = inspect(process.argv[4]);
assert.equal(baseline.count, 28);
assert.deepEqual(baseline.failures, [{ node: 'Issue installation token', parameter: '/nodes/11/parameters/jsonBody', error: 'ExpressionExtensionError:invalid syntax' }]);
assert.equal(candidate.count, baseline.count);
assert.deepEqual(candidate.failures, []);
console.log(JSON.stringify({ nativeExpressionSyntax: true, baseline, candidate }));
