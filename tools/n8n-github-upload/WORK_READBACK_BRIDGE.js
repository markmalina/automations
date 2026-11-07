// Run as a functions.exec cell after setting store('work-readback-config', ...).
// Uses the existing GitHub connector; never prints tool responses or file bytes.
// This is a local verifier driver, not an uploader or a new auth mechanism.
const cfg = load('work-readback-config');
if (!cfg || !['helper', 'bundle', 'receipt', 'output'].every(k =>
  typeof cfg[k] === 'string' && cfg[k].startsWith('/') && !/[\u0000\r\n]/u.test(cfg[k]))) {
  throw Error('E_BRIDGE_CONFIG');
}
const quote = s => "'" + s.replaceAll("'", "'\\''") + "'";
const sha = s => typeof s === 'string' && /^[a-f0-9]{40}$/u.test(s);
const repo = s => typeof s === 'string' && /^markmalina\/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/u.test(s);
const parse = result => {
  if (result.isError) throw Error('E_CONNECTOR');
  const value = result.structuredContent?.content;
  if (typeof value !== 'string') throw Error('E_CONNECTOR_SHAPE');
  return JSON.parse(value);
};
const start = await tools.exec_command({
  cmd: ['python', quote(cfg.helper), '--bundle', quote(cfg.bundle), '--receipt', quote(cfg.receipt),
    '--output', quote(cfg.output)].join(' '), tty: true, yield_time_ms: 1000, max_output_tokens: 3000
});
let state = start, buffer = '', sequence = 0, ready = false, result = null;
const deadline = Date.now() + 125000;
while (Date.now() < deadline) {
  buffer += state.output || '';
  // Never forward unparsed PTY output: a transport failure must not echo data.
  if (buffer.length > 65536) throw Error('E_BRIDGE_OUTPUT');
  let request = null;
  while (buffer.includes('\n')) {
    const end = buffer.indexOf('\n');
    const line = buffer.slice(0, end).replace(/\r$/u, '');
    buffer = buffer.slice(end + 1);
    if (line === 'READY_FOR_GRANT') { ready = true; continue; }
    if (line.startsWith('READBACK_RESULT ')) {
      const candidate = JSON.parse(line.slice(16));
      if (!['VERIFIED', 'MISMATCH', 'UNAVAILABLE'].includes(candidate.status)) throw Error('E_BRIDGE_RESULT');
      result = candidate;
      break;
    }
    if (!ready || !line.startsWith('READBACK_REQUEST ')) throw Error('E_BRIDGE_PROTOCOL');
    request = JSON.parse(line.slice(17));
    if (request.sequence !== ++sequence || !repo(request.repository)) throw Error('E_BRIDGE_REQUEST');
    break;
  }
  if (result) break;
  if (!state.session_id) throw Error('E_BRIDGE_INCOMPLETE');
  if (!request) {
    state = await tools.write_stdin({session_id: state.session_id, chars: '', yield_time_ms: 1000, max_output_tokens: 3000});
    continue;
  }
  let response;
  try {
    const base = 'https://api.github.com/repos/' + request.repository;
    let data;
    if (request.kind === 'repository') data = parse(await tools.mcp__codex_apps__github_fetch({url: base}));
    else if (request.kind === 'commit' && sha(request.sha)) {
      data = parse(await tools.mcp__codex_apps__github_fetch({url: base + '/git/commits/' + request.sha}));
    } else if (request.kind === 'tree' && sha(request.sha)) {
      data = parse(await tools.mcp__codex_apps__github_fetch({url: base + '/git/trees/' + request.sha}));
    } else if (request.kind === 'file' && sha(request.ref) && typeof request.path === 'string' &&
      request.path.length <= 2048 && !request.path.startsWith('/') &&
      !request.path.split('/').some(p => !p || p === '.' || p === '..' || p.toLowerCase() === '.git') &&
      !/[\\\u0000-\u001f\u007f]/u.test(request.path)) {
      const fetched = await tools.mcp__codex_apps__github_fetch_file({repository_full_name: request.repository,
        path: request.path, ref: request.ref, encoding: 'base64'});
      if (fetched.isError) throw Error('E_CONNECTOR');
      const file = fetched.structuredContent;
      if (!file || file.encoding !== 'base64' || typeof file.content !== 'string') throw Error('E_BYTES_UNAVAILABLE');
      data = {sha: file.sha, encoding: file.encoding, content: file.content};
    } else throw Error('E_BRIDGE_REQUEST');
    response = {sequence, ok: true, data};
  } catch {
    response = {sequence, ok: false, error: 'unavailable'};
  }
  const line = JSON.stringify(response) + '\n';
  if (line.length > 44000000) throw Error('E_BRIDGE_RESPONSE_SIZE');
  let bytes = 0;
  for (const character of line) {
    const point = character.codePointAt(0);
    bytes += point < 128 ? 1 : point < 2048 ? 2 : point < 65536 ? 3 : 4;
    if (bytes > 44000000) throw Error('E_BRIDGE_RESPONSE_SIZE');
  }
  // Programmatic stdin only. Do not print line, response, data or fetched.
  state = await tools.write_stdin({session_id: state.session_id, chars: line,
    yield_time_ms: 1000, max_output_tokens: 3000});
  response = null;
}
if (!result) throw Error('E_BRIDGE_TIMEOUT');
const exitDeadline = Date.now() + 5000;
while (state.session_id && state.exit_code === undefined && Date.now() < exitDeadline) {
  state = await tools.write_stdin({session_id: state.session_id, chars: '', yield_time_ms: 1000, max_output_tokens: 1000});
}
if (state.exit_code !== {VERIFIED: 0, MISMATCH: 1, UNAVAILABLE: 2}[result.status]) throw Error('E_BRIDGE_EXIT');
// The helper emits only its bounded report. File contents/URLs from providers are excluded.
store('work-readback-result', result);
text(result);
