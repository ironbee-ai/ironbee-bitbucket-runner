// The app's two matches, held to the reviewer's own trigger cases (trigger-cases.json: every case the reviewer takes, the
// app takes), and its readings where they are exact: quoted lines, fenced code, the reviewer's hidden lines, the name's
// case and its edges, and the comments that hold a console icon, read whole.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import { app } from './stub/app.mjs';

const { addresses, isOurs, startBody } = app;
const CASES = JSON.parse(readFileSync(new URL('./trigger-cases.json', import.meta.url), 'utf8')).cases;

function comment(raw, type = 'app_user') {
  return { user: { type }, content: { raw } };
}

describe("the reviewer's trigger cases", () => {
  it('are there to read', () => {
    assert.ok(Array.isArray(CASES) && CASES.length > 0);
    for (const c of CASES) {
      assert.equal(typeof c.raw, 'string');
      assert.equal(typeof c.authorType, 'string');
      assert.equal(typeof c.addressed, 'boolean');
      assert.equal(typeof c.ours, 'boolean');
    }
  });

  it('every comment the reviewer counts as addressed, the app takes', () => {
    const missed = CASES.filter((c) => c.addressed && !addresses(c.raw)).map((c) => c.raw);
    assert.deepEqual(missed, []);
  });

  it("every thread the reviewer counts as its own, the app takes", () => {
    const missed = CASES.filter((c) => c.ours && !isOurs(comment(c.raw, c.authorType))).map((c) => c.raw);
    assert.deepEqual(missed, []);
  });
});

describe('a comment addresses the reviewer', () => {
  it('by its name anywhere on a line of its own words', () => {
    for (const raw of ['@ironbee-ai review', 'Fixed both. @ironbee-ai full review', '@ironbee-ai, why?', 'see (@ironbee-ai)', 'x\n@ironbee-ai pause', '@ironbee-ai']) {
      assert.equal(addresses(raw), true, raw);
    }
  });

  it("with its case ignored as the reviewer's Python ignores it", () => {
    for (const raw of ['@IronBee-AI review', '@IRONBEE-AI', '@\u0130ronbee-a\u0130', '@\u0131ronbee-a\u0131']) {
      assert.equal(addresses(raw), true, raw);
    }
    for (const raw of ['@ironbee\u2010ai', '@ironbee_ai', '@ironbeeai', '@iron bee-ai']) {
      assert.equal(addresses(raw), false, raw);
    }
  });

  it('only at its edges', () => {
    for (const raw of ['x@ironbee-ai', '/@ironbee-ai', '@@ironbee-ai', '-@ironbee-ai', '_@ironbee-ai', '9@ironbee-ai', '@ironbee-ai-bot', '@ironbee-aix', '@ironbee-ai_x', '@ironbee-ai9']) {
      assert.equal(addresses(raw), false, raw);
    }
    for (const raw of ['.@ironbee-ai', '@ironbee-ai.', '@ironbee-ai/x', '@ironbee-ai@', '"@ironbee-ai"', '\u00e9@ironbee-ai']) {
      assert.equal(addresses(raw), true, raw);
    }
  });

  it('never in a quoted line', () => {
    for (const raw of ['> @ironbee-ai review', '   > @ironbee-ai review', '\t> @ironbee-ai', 'ok\r\n> @ironbee-ai review', 'ok\u2028> @ironbee-ai', 'ok\u00a0\n\u00a0> @ironbee-ai']) {
      assert.equal(addresses(raw), false, JSON.stringify(raw));
    }
    assert.equal(addresses('> @ironbee-ai review\n@ironbee-ai resume'), true);
  });

  it('never in fenced code, a fence being any line that starts with three backticks', () => {
    assert.equal(addresses('```\n@ironbee-ai review\n```'), false);
    assert.equal(addresses('```js\n@ironbee-ai review\n```\n@ironbee-ai resume'), true);
    assert.equal(addresses('   ```\n@ironbee-ai review'), false);
    assert.equal(addresses('a ``` b\n@ironbee-ai review'), true);
    assert.equal(addresses('```\n```\n@ironbee-ai review'), true);
    assert.equal(addresses('```\r\n@ironbee-ai review\r\n```'), false);
  });

  it("never in a hidden line of the reviewer's, which is none of the person's words", () => {
    assert.equal(addresses('[//]: # "ironbee x @ironbee-ai"'), false);
    assert.equal(addresses('[//]: # "ironbee-data @ironbee-ai"'), false);
    // a hidden line is one line to the reviewer whatever it holds, so no fence starts inside it
    assert.equal(addresses('[//]: # "ironbee a\u2028```"\n@ironbee-ai review'), true);
    // a line that only looks like one is the person's
    assert.equal(addresses('[//]: # "ironbee"@ironbee-ai'), true);
    assert.equal(addresses('    [//]: # "ironbee x @ironbee-ai"'), true);
  });

  it('read whole where it holds a console icon, which the reviewer reads back as a mark or as nothing', () => {
    const icon = '![x](https://app.ironbee.ai/badges/kind-style-solid.svg)';
    assert.equal(addresses(`@iron${icon}bee-ai review`), true);
    assert.equal(addresses(`x${icon}@ironbee-ai`), true);
    assert.equal(addresses(`> @ironbee-ai ${icon}`), true);
    assert.equal(addresses(`${icon} nothing for us`), false);
  });

  it('never by another name', () => {
    for (const raw of ['', 'review please', '@{712020:a1344cb1-2a52-4e49-9401-19d37092ca81} review', '@ironbee review', 'ironbee-ai review']) {
      assert.equal(addresses(raw), false, raw);
    }
    assert.equal(addresses(null), false);
    assert.equal(addresses(undefined), false);
  });
});

describe("a thread is the reviewer's", () => {
  it("when its first comment is an app user's carrying the identity marker on a line of its own", () => {
    assert.equal(isOurs(comment('A finding.\n\n[//]: # "ironbee f1"')), true);
    assert.equal(isOurs(comment('Body.\r\n\r\n[//]: # "ironbee review:42"\r\n[//]: # "ironbee-data eyJ2IjoxfQ=="')), true);
    assert.equal(isOurs(comment('   [//]: # "ironbee f1"   ')), true);
    assert.equal(isOurs(comment('a\u2028[//]: # "ironbee f1"')), true);
    assert.equal(isOurs(comment('    [//]: # "ironbee f1"')), true);           // the reviewer also reads a marker's line stripped
  });

  it("never a person's, nor one with no marker, nor a marker quoted or inside a line", () => {
    assert.equal(isOurs(comment('A finding.\n\n[//]: # "ironbee f1"', 'user')), false);
    assert.equal(isOurs({ content: { raw: '[//]: # "ironbee f1"' } }), false);
    assert.equal(isOurs(comment('A build note from another pipeline.')), false);
    assert.equal(isOurs(comment('> [//]: # "ironbee f1"')), false);
    assert.equal(isOurs(comment('see [//]: # "ironbee f1"')), false);
    assert.equal(isOurs(comment('[//]: # "ironbee-data eyJ2IjoxfQ=="')), false);
    assert.equal(isOurs(comment('[//]: # "ironbee "')), false);
    assert.equal(isOurs(null), false);
  });
});

describe('the start', () => {
  it("is the pull request's own branches and commits, its id and the custom pipeline", () => {
    const pull = { id: 4, source: { branch: { name: 'feature/x' }, commit: { hash: '1fb1be025070' } }, destination: { branch: { name: 'main' }, commit: { hash: '761a90b91dd6' } } };
    assert.deepEqual(startBody(pull), { target: { type: 'pipeline_pullrequest_target', source: 'feature/x', destination: 'main', destination_commit: { hash: '761a90b91dd6' },
      commit: { hash: '1fb1be025070' }, pullrequest: { id: 4 }, selector: { type: 'custom', pattern: 'ironbee-code-review' } } });
    // a pull request opened through the API may give no destination commit: the head stands in for it
    for (const destination of [{ branch: { name: 'main' } }, { branch: { name: 'main' }, commit: null }, { branch: { name: 'main' }, commit: { hash: '' } }]) {
      assert.deepEqual(startBody({ ...pull, destination }).target.destination_commit, { hash: '1fb1be025070' });
    }
    assert.equal(startBody({ ...pull, source: { branch: { name: 'feature/x' } } }), null);
    assert.equal(startBody({ ...pull, destination: { commit: { hash: '761a90b91dd6' } } }), null);
    assert.equal(startBody({ ...pull, id: '4' }), null);
  });
});
