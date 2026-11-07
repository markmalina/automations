// Task17 read-only diagnosis: real n8n parser, no workflow/upload/retry.
const path = require('node:path');
const { Readable } = require('node:stream');
const root = path.resolve(process.argv[2]);
const { createMultiFormDataParser } = require(path.join(root, 'node_modules/n8n/dist/webhooks/webhook-form-data.js'));
async function main() {
  const boundary = 'synthetic-task17-parser-boundary';
  // Same manifest part headers as the accepted work_upload.py. No uploadId/grant.
  const raw = Buffer.from('--' + boundary + '\r\nContent-Disposition: form-data; name="manifest"\r\nContent-Type: application/json\r\n\r\n{}\r\n--' + boundary + '--\r\n');
  const req = Readable.from([raw]);
  req.headers = { 'content-type': 'multipart/form-data; boundary=' + boundary, 'content-length': String(raw.length) };
  req.encoding = 'utf-8';
  const parsed = await createMultiFormDataParser(1)(req);
  try {
    const summary = { nativeParser: true, dataKeys: Object.keys(parsed.body.data), fileKeys: Object.keys(parsed.body.files), manifestFieldType: typeof parsed.body.data.manifest };
    if (summary.manifestFieldType !== 'undefined' || !summary.fileKeys.includes('manifest')) throw Error('unexpected parser evidence');
    console.log(JSON.stringify(summary));
  } finally { await parsed.cleanup(); }
}
main().catch(() => { console.log(JSON.stringify({ parserProbe: 'UNAVAILABLE' })); process.exitCode = 1; });
