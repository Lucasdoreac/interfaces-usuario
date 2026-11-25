import assert from 'node:assert/strict';
import { test } from 'node:test';
import { existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer } from 'vite';

test('schedule invalidates room and date on changed period/date using the real UI', { timeout: 60000 }, async t => {
  const chrome = [process.env.CHROME_BIN, '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome'].find(p => p && existsSync(p));
  if (!chrome) return t.skip('Chrome/Chromium is required; set CHROME_BIN');
  const server = await createServer({ configFile: false, root: new URL('..', import.meta.url).pathname, cacheDir: '/tmp/schedule-selection-vite', server: { host: '127.0.0.1', port: 0, hmr: false }, optimizeDeps: { include: ['react', 'react-dom/client', 'react-router'] } });
  try {
    await server.listen();
    const url = `http://127.0.0.1:${server.httpServer.address().port}/tests/schedule-selection-browser.html`;
    const { code, stdout, stderr } = await new Promise((resolve, reject) => {
      const child = spawn(chrome, ['--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--disable-background-networking', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1', '--dump-dom', '--virtual-time-budget=15000', url], { timeout: 45000, killSignal: 'SIGKILL' });
      let stdout = '', stderr = '';
      child.stdout.on('data', x => stdout += x); child.stderr.on('data', x => stderr += x);
      child.on('error', reject); child.on('close', code => resolve({ code, stdout, stderr }));
    });
    assert.equal(code, 0, stderr); assert.match(stdout, /<pre id="result">PASS<\/pre>/, stdout);
  } finally { await server.close(); }
});
