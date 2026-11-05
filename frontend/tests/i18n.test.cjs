const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');

// Test the actual TypeScript helper without adding a separate test framework.
const source = path.join(__dirname, '../src/i18n/translate.ts');
const transpiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true, target: ts.ScriptTarget.ES2020 },
}).outputText;
const loaded = new Module(source, module);
loaded.filename = source;
loaded.paths = Module._nodeModulePaths(path.dirname(source));
loaded._compile(transpiled, source);
const { translate } = loaded.exports;

test('Vietnamese defaults and English translations keep API-independent labels', () => {
  assert.equal(translate('Vị trí tuyển dụng', 'vi'), 'Vị trí tuyển dụng');
  assert.equal(translate('Vị trí tuyển dụng', 'en'), 'Recruitment positions');
  assert.equal(translate('Đang xem', 'en'), 'In review');
  assert.equal(translate('Nguồn dữ liệu người dùng', 'en'), 'Nguồn dữ liệu người dùng');
});

test('interpolation and existing alerts switch languages in both directions', () => {
  const vi = 'Đã chọn {0} hồ sơ để chia sẻ';
  // Use a dictionary template that is also used by the interface.
  assert.equal(translate('Trang {0} · Đã xác minh', 'en', 3), 'Page 3 · Verified');
  assert.equal(translate('Page 3 · Verified', 'vi'), 'Trang 3 · Đã xác minh');
  assert.equal(translate('Trang 3 · Đã xác minh', 'en'), 'Page 3 · Verified');
  assert.equal(translate('You do not have permission to access this position', 'vi'), 'Bạn không có quyền truy cập vị trí này.');
  assert.equal(translate('Bạn không có quyền truy cập vị trí này.', 'en'), 'You do not have permission to access this position');
  assert.equal(translate(vi, 'vi', 2), 'Đã chọn 2 hồ sơ để chia sẻ');
});

test('all literal UI translation keys have an English entry', () => {
  const dictionary = require('../src/i18n/en.json');
  const root = path.join(__dirname, '../src');
  const missing = [];
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) { walk(file); continue; }
      if (!/\.tsx$/.test(file) || file.includes(`${path.sep}i18n${path.sep}`)) continue;
      const content = fs.readFileSync(file, 'utf8');
      for (const match of content.matchAll(/\bt\(("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g)) {
        let key;
        try { key = match[1][0] === '"' ? JSON.parse(match[1]) : match[1].slice(1, -1); } catch { continue; }
        if (!(key in dictionary)) missing.push(`${path.relative(root, file)}: ${key}`);
      }
    }
  }
  walk(root);
  assert.deepEqual(missing, []);
});
