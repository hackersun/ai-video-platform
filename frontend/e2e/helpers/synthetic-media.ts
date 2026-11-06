import { test as base, expect } from '@playwright/test';
import { deflateSync } from 'node:zlib';

// Build a valid 2x2 PNG at test runtime. No generated-media checkout or backend.
function pngChunk(type: string, data: Buffer): Buffer {
  const body = Buffer.concat([Buffer.from(type), data]);
  let crc = 0xffffffff;
  for (const byte of body) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  const size = Buffer.alloc(4);
  size.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
  return Buffer.concat([size, body, checksum]);
}

function tinyPng(): Buffer {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(2, 0);
  header.writeUInt32BE(2, 4);
  header[8] = 8;
  header[9] = 2;
  const row = Buffer.from([0, 42, 120, 210, 42, 120, 210]);
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    pngChunk('IHDR', header), pngChunk('IDAT', deflateSync(Buffer.concat([row, row]))),
    pngChunk('IEND', Buffer.alloc(0)),
  ]);
}

// Opt-in only for mocked UI specs. Real-backend pipeline/media tests use base
// Playwright directly so a missing real output cannot be hidden by this fixture.
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route(/\/static\/generated\/.*\.(png|jpe?g|webp)(?:\?.*)?$/, (route) =>
      route.fulfill({ contentType: 'image/png', body: tinyPng() }));
    await use(page);
  },
});
export { expect };
