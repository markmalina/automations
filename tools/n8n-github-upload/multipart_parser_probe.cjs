// Task17 read-only diagnosis: real n8n parser, no workflow/upload/retry.
const path = require('node:path');
const { Readable } = require('node:stream');
const fs = require('node:fs');
const crypto = require('node:crypto');
const root = path.resolve(process.argv[2]);
const { createMultiFormDataParser } = require(path.join(root, 'node_modules/n8n/dist/webhooks/webhook-form-data.js'));
async function main() {
  const boundary = 'synthetic-task17-parser-boundary';
  // Same manifest part headers as the accepted work_upload.py. No uploadId/grant.
  const packetMode = process.argv[3] === '--packet';
  let raw, config;
  if (packetMode) {
    // Private stdin frame: 4-byte JSON length, safe metadata JSON, actual client body.
    const input = fs.readFileSync(0);
    if (input.length < 4 || input.length > 1024 * 1024) throw Error('packet size');
    const size = input.readUInt32BE(0);
    if (size < 1 || size > 65536 || 4 + size > input.length) throw Error('metadata size');
    config = JSON.parse(input.subarray(4, 4 + size));
    raw = input.subarray(4 + size);
    if (raw.length !== config.contentLength) throw Error('length mismatch');
  } else {
    raw = Buffer.from('--' + boundary + '\r\nContent-Disposition: form-data; name="manifest"\r\nContent-Type: application/json\r\n\r\n{}\r\n--' + boundary + '--\r\n');
  }
  const req = Readable.from([raw]);
  req.headers = { 'content-type': packetMode ? config.contentType : 'multipart/form-data; boundary=' + boundary, 'content-length': String(raw.length) };
  req.encoding = 'utf-8';
  const parsed = await createMultiFormDataParser(1)(req);
  try {
    const summary = { nativeParser: true, dataKeys: Object.keys(parsed.body.data), fileKeys: Object.keys(parsed.body.files), manifestFieldType: typeof parsed.body.data.manifest };
    if (packetMode) {
      summary.manifestExact = parsed.body.data.manifest === config.manifest;
      summary.filesVerified = 0;
      if (!summary.manifestExact || summary.dataKeys.length !== 1 || summary.manifestFieldType !== 'string' || summary.fileKeys.length !== config.files.length) {
        console.log(JSON.stringify(summary));
        process.exitCode = 1;
        return;
      }
      for (const expected of config.files) {
        const file = parsed.body.files[expected.field];
        if (!file || Array.isArray(file)) throw Error('file field mismatch');
        const bytes = fs.readFileSync(file.filepath);
        if (bytes.length !== expected.bytes || crypto.createHash('sha256').update(bytes).digest('hex') !== expected.sha256) throw Error('binary mismatch');
        summary.filesVerified++;
      }
    } else if (summary.manifestFieldType !== 'undefined' || !summary.fileKeys.includes('manifest')) throw Error('unexpected parser evidence');
    console.log(JSON.stringify(summary));
  } finally { await parsed.cleanup(); }
}
main().catch(() => { console.log(JSON.stringify({ parserProbe: 'UNAVAILABLE' })); process.exitCode = 1; });
