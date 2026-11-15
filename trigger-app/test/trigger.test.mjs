// The function on a comment's event, against the tests' Bitbucket (the stub of @forge/api): what it reads, when it
// starts the pipeline and with which body, what it leaves, and what its log holds.
import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it, mock } from 'node:test';

import { app, forge } from './stub/app.mjs';

const WS = '{6d1a0dc3-2eb4-4bdc-952f-af3b8fcbe13d}';
const REPO = '{30cbb1be-00da-425d-b3b1-29695ceb11f9}';
const BASE = `/2.0/repositories/${WS}/${REPO}`;
const PR = `${BASE}/pullrequests/4`;
const OURS = '[//]: # "ironbee f1"';
const SECRET_WORDS = 'a sentence nobody else writes';                 // the texts no log line may hold

function event(over = {}) {
  return { eventType: 'avi:bitbucket:created:pullrequest-comment', selfGenerated: false,
    actor: { type: 'user', accountId: '712020:0c3f941f-fac0-4bbc-bf2f-c808f7748f9a', uuid: '{a43ba83d-f794-4829-9dd4-021aed5adec3}' },
    workspace: { uuid: WS }, repository: { uuid: REPO, slug: 'shop' }, project: { uuid: '{7805fc96-8fee-4a5c-91e5-457368075853}' },
    pullrequest: { id: 4, state: 'OPEN', source: { branch: 'feature/secret-branch', commit: { hash: '1fb1be025070' } },
      destination: { branch: 'main', commit: { hash: '761a90b91dd6' } }, title: { truncated: false, value: SECRET_WORDS } },
    comment: { id: 101 }, ...over };
}

function pull(over = {}) {
  const repository = { uuid: REPO, full_name: 'acme/shop' };
  return { id: 4, state: 'OPEN', title: SECRET_WORDS, source: { branch: { name: 'feature/secret-branch' }, commit: { hash: '1fb1be025070' }, repository },
    destination: { branch: { name: 'main' }, commit: { hash: '761a90b91dd6' }, repository }, ...over };
}

function person(id, raw, parent) {
  return { id, content: { raw: `${raw} ${SECRET_WORDS}` }, user: { type: 'user', account_id: '712020:0c3f941f' }, ...(parent ? { parent: { id: parent } } : {}) };
}

function ours(id, raw = 'A finding.') {
  return { id, content: { raw: `${raw}\n\n${OURS}` }, user: { type: 'app_user', display_name: 'Bitbucket Pipelines' } };
}

// A Bitbucket of one pull request: its comments by id (a comment, or [status, body]), the pull request (or
// [status, body]), and the start's answer (or a function that gives it).
function hub({ comments = {}, pr = pull(), start = [201, { uuid: '{p}', build_number: 23 }] } = {}) {
  forge.bitbucket((call) => {
    const found = call.path.match(/^(.*)\/comments\/([0-9]+)$/);
    if (call.method === 'GET' && found && found[1] === PR) {
      const c = comments[found[2]];
      if (c === undefined) {
        return [404, { type: 'error', error: { message: 'no such comment' } }];
      }
      return Array.isArray(c) ? c : [200, c];
    }
    if (call.method === 'GET' && call.path === PR) {
      return Array.isArray(pr) ? pr : [200, pr];
    }
    if (call.method === 'POST' && call.path === `${BASE}/pipelines/`) {
      return typeof start === 'function' ? start(call) : start;
    }
    return [404, { type: 'error' }];
  });
}

let logged;
beforeEach(() => {
  logged = mock.method(console, 'log', () => {});
});
afterEach(() => {
  mock.restoreAll();
});

function lines() {
  return logged.mock.calls.map((c) => JSON.parse(c.arguments[0]));
}

function said() {
  return lines().map((l) => l.outcome);
}

function paths() {
  return forge.calls.map((c) => `${c.method} ${c.path.replace(BASE, '')}`);
}

describe('a comment that addresses the reviewer', () => {
  it('starts the pipeline with the pull request as its target', async () => {
    hub({ comments: { 101: person(101, '@ironbee-ai review') } });
    await app.onComment(event());
    assert.deepEqual(paths(), ['GET /pullrequests/4/comments/101', 'GET /pullrequests/4', 'POST /pipelines/']);
    const [, , start] = forge.calls;
    assert.deepEqual(start.body, { target: { type: 'pipeline_pullrequest_target', source: 'feature/secret-branch', destination: 'main',
      destination_commit: { hash: '761a90b91dd6' }, commit: { hash: '1fb1be025070' }, pullrequest: { id: 4 },
      selector: { type: 'custom', pattern: 'ironbee-code-review' } } });
    assert.equal(start.headers['Content-Type'], 'application/json');
    assert.deepEqual(lines(), [{ workspace: WS, repository: REPO, pullRequest: '4', comment: '101', outcome: 'started', why: 'addressed', build: 23 }]);
  });

  it('in a reply needs no read of its thread', async () => {
    hub({ comments: { 102: person(102, '@ironbee-ai why?', 101) } });
    await app.onComment(event({ comment: { id: 102 } }));
    assert.deepEqual(paths(), ['GET /pullrequests/4/comments/102', 'GET /pullrequests/4', 'POST /pipelines/']);
  });

  it('only in a quoted line or in code starts nothing', async () => {
    hub({ comments: { 101: person(101, '> @ironbee-ai review\n\n```\n@ironbee-ai review\n```\n') } });
    await app.onComment(event());
    assert.deepEqual(paths(), ['GET /pullrequests/4/comments/101']);
    assert.deepEqual(said(), ['not for us']);
  });
});

describe('a reply', () => {
  it("on a thread of the reviewer's starts the pipeline", async () => {
    hub({ comments: { 101: ours(101), 102: person(102, 'Why is this wrong?', 101) } });
    await app.onComment(event({ comment: { id: 102 } }));
    assert.deepEqual(paths(), ['GET /pullrequests/4/comments/102', 'GET /pullrequests/4/comments/101', 'GET /pullrequests/4', 'POST /pipelines/']);
    assert.equal(lines()[0].why, 'our thread');
  });

  it("to a reply walks up the parents to the thread's first comment", async () => {
    hub({ comments: { 101: ours(101), 102: person(102, 'first', 101), 103: person(103, 'second', 102) } });
    await app.onComment(event({ comment: { id: 103 } }));
    assert.deepEqual(paths(), ['GET /pullrequests/4/comments/103', 'GET /pullrequests/4/comments/102', 'GET /pullrequests/4/comments/101',
      'GET /pullrequests/4', 'POST /pipelines/']);
  });

  it("on a person's thread, or on another app user's without our marker, starts nothing", async () => {
    const roots = [person(101, 'a person asks'), { id: 101, content: { raw: 'Build passed.' }, user: { type: 'app_user' } },
      { ...ours(101), user: { type: 'user' } }];
    for (const root of roots) {
      hub({ comments: { 101: root, 102: person(102, 'agreed', 101) } });
      logged.mock.resetCalls();
      await app.onComment(event({ comment: { id: 102 } }));
      assert.deepEqual(paths(), ['GET /pullrequests/4/comments/102', 'GET /pullrequests/4/comments/101']);
      assert.deepEqual(said(), ['not for us']);
    }
  });

  it('whose thread runs past the bound starts the pipeline, and the run reads the thread', async () => {
    const comments = { 101: person(101, 'a person asks') };
    for (let id = 102; id <= 113; id += 1) {
      comments[id] = person(id, 'more', id - 1);
    }
    hub({ comments });
    await app.onComment(event({ comment: { id: 113 } }));
    assert.equal(forge.calls.length, 13);                                // the comment, ten of its parents, the pull request, the start
    assert.deepEqual(paths().slice(10), ['GET /pullrequests/4/comments/103', 'GET /pullrequests/4', 'POST /pipelines/']);
    assert.ok(!paths().includes('GET /pullrequests/4/comments/102'));
    assert.deepEqual(lines().map((l) => [l.outcome, l.why]), [['started', 'deep thread']]);
  });

  it('whose thread cannot be read starts nothing', async () => {
    hub({ comments: { 101: [403, { type: 'error' }], 102: person(102, 'hm', 101) } });
    await app.onComment(event({ comment: { id: 102 } }));
    assert.deepEqual(paths(), ['GET /pullrequests/4/comments/102', 'GET /pullrequests/4/comments/101']);
    assert.deepEqual(lines().map((l) => [l.outcome, l.status]), [['thread unread', 403]]);
  });
});

describe('what ends a run before the start', () => {
  it("an app user's comment, before any read", async () => {
    hub();
    await app.onComment(event({ actor: { type: 'app_user', accountId: '712020:a1344cb1', uuid: '{x}' } }));
    assert.deepEqual(forge.calls, []);
    assert.deepEqual(said(), ['not a person']);
  });

  it('a comment the read shows to be no person\'s', async () => {
    hub({ comments: { 101: { ...ours(101, '@ironbee-ai review') } } });
    await app.onComment(event({ actor: undefined }));
    assert.deepEqual(paths(), ['GET /pullrequests/4/comments/101']);
    assert.deepEqual(said(), ['not a person']);
  });

  it('an event that names no pull request comment, before any read', async () => {
    hub();
    for (const over of [{ comment: undefined }, { pullrequest: { id: 0 } }, { workspace: { uuid: 'a/b' } }, { repository: {} }, { comment: { id: '1/2' } }]) {
      await app.onComment(event(over));
    }
    assert.deepEqual(forge.calls, []);
    assert.deepEqual(said(), Array(5).fill('not a pull request comment'));
  });

  it('a comment that is not for the reviewer, after its one read', async () => {
    hub({ comments: { 101: person(101, 'Looks good to me') } });
    await app.onComment(event());
    assert.deepEqual(paths(), ['GET /pullrequests/4/comments/101']);
    assert.deepEqual(said(), ['not for us']);
  });

  it('a comment that cannot be read', async () => {
    hub({ comments: { 101: [403, { type: 'error' }] } });
    await app.onComment(event());
    assert.deepEqual(lines().map((l) => [l.outcome, l.status]), [['comment unread', 403]]);
  });

  it('a pull request that is merged or declined', async () => {
    for (const state of ['MERGED', 'DECLINED', 'SUPERSEDED']) {
      hub({ comments: { 101: person(101, '@ironbee-ai review') }, pr: pull({ state }) });
      logged.mock.resetCalls();
      await app.onComment(event());
      assert.deepEqual(paths(), ['GET /pullrequests/4/comments/101', 'GET /pullrequests/4']);
      assert.deepEqual(lines().map((l) => [l.outcome, l.state]), [['pull request not open', state]]);
    }
  });

  it('a pull request from a fork', async () => {
    const fork = { uuid: '{ffffffff-0000-0000-0000-000000000000}', full_name: 'someone/shop' };
    for (const pr of [pull({ source: { ...pull().source, repository: fork } }), pull({ source: { ...pull().source, repository: undefined } }),
      pull({ source: { ...pull().source, repository: { full_name: 'someone/shop' } }, destination: { ...pull().destination, repository: { full_name: 'acme/shop' } } })]) {
      hub({ comments: { 101: person(101, '@ironbee-ai review') }, pr });
      logged.mock.resetCalls();
      await app.onComment(event());
      assert.deepEqual(paths(), ['GET /pullrequests/4/comments/101', 'GET /pullrequests/4']);
      assert.deepEqual(said(), ['pull request from a fork']);
    }
  });

  it('a pull request that cannot be read, or lacks what the start needs', async () => {
    hub({ comments: { 101: person(101, '@ironbee-ai review') }, pr: [500, 'Internal Server Error'] });
    await app.onComment(event());
    hub({ comments: { 101: person(101, '@ironbee-ai review') }, pr: pull({ destination: { branch: { name: 'main' }, repository: pull().destination.repository } }) });
    await app.onComment(event());
    assert.deepEqual(lines().map((l) => [l.outcome, l.status]), [['pull request unread', 500], ['pull request incomplete', undefined]]);
    assert.ok(!forge.calls.some((c) => c.method === 'POST'));
  });
});

describe('the start', () => {
  it('refused is logged with its code and dropped', async () => {
    hub({ comments: { 101: person(101, '@ironbee-ai review') },
      start: [400, { type: 'error', error: { message: `no pipeline on feature/secret-branch: ${SECRET_WORDS}`, data: { key: 'result-service.pipeline.custom-pipeline-not-found', arguments: {} } } }] });
    await app.onComment(event());
    assert.deepEqual(lines(), [{ workspace: WS, repository: REPO, pullRequest: '4', comment: '101', outcome: 'start refused', why: 'addressed', status: 400,
      error: 'result-service.pipeline.custom-pipeline-not-found' }]);
  });

  it('refused with an answer that is no JSON is logged by its status alone', async () => {
    hub({ comments: { 101: person(101, '@ironbee-ai review') }, start: [403, 'Forbidden'] });
    await app.onComment(event());
    assert.deepEqual(lines().map((l) => [l.outcome, l.status, l.error]), [['start refused', 403, undefined]]);
  });

  it('a call that throws is logged by its kind and never rethrown', async () => {
    forge.bitbucket(() => {
      throw new TypeError(`fetch failed: ${SECRET_WORDS}`);
    });
    await app.onComment(event());
    assert.deepEqual(lines().map((l) => [l.outcome, l.error]), [['failed', 'TypeError']]);
  });

  it('takes the ids an event gives as strings too', async () => {
    hub({ comments: { 101: person(101, '@ironbee-ai review') } });
    await app.onComment(event({ pullrequest: { id: '4' }, comment: { id: '101' } }));
    assert.deepEqual(said(), ['started']);
  });
});

describe('the log', () => {
  it('holds ids and outcomes, never a text', async () => {
    const runs = [
      [{ comments: { 101: person(101, '@ironbee-ai review') } }, event()],
      [{ comments: { 101: ours(101), 102: person(102, 'Why?', 101) } }, event({ comment: { id: 102 } })],
      [{ comments: { 101: person(101, 'nothing for us') } }, event()],
      [{ comments: { 101: person(101, '@ironbee-ai review') }, start: [400, { error: { message: SECRET_WORDS, data: { key: SECRET_WORDS } } }] }, event()],
      [{ comments: { 101: person(101, '@ironbee-ai review') }, pr: pull({ state: SECRET_WORDS }) }, event()],
    ];
    for (const [state, ev] of runs) {
      hub(state);
      await app.onComment(ev);
    }
    const text = logged.mock.calls.map((c) => c.arguments.join(' ')).join('\n');
    for (const word of [SECRET_WORDS, 'secret-branch', 'main', 'acme/shop', 'shop', 'ironbee-ai', 'Why?', 'finding']) {
      assert.ok(!text.includes(word), word);
    }
    const allowed = new Set(['workspace', 'repository', 'pullRequest', 'comment', 'outcome', 'why', 'status', 'state', 'build', 'error']);
    assert.deepEqual(lines().flatMap((l) => Object.keys(l)).filter((key) => !allowed.has(key)), []);
    assert.ok(logged.mock.calls.every((c) => c.arguments.length === 1));
  });
});
