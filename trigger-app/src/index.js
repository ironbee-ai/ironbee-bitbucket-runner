import api, { route } from '@forge/api';

// IronBee's trigger app. Bitbucket starts no pipeline on a comment, so for a person's comment that addresses the
// reviewer, or answers a thread of the reviewer's, on an open pull request of the repository itself, this function
// starts the repository's custom pipeline ironbee-code-review with the pull request as its target. It hands the run
// nothing: the run finds the comment and decides, by the reviewer's own rules, what is due. The app may take a comment
// the reviewer then turns away, never leave one the reviewer would take. Its log holds ids and outcomes, never a text.

const PIPELINE = 'ironbee-code-review';
const MAX_PARENTS = 10;                                   // a reply's way up to its thread's first comment, bounded

// What the reviewer's Python reads as whitespace (str.isspace) and as the end of a line (str.splitlines).
const SPACE = '\\t\\n\\x0b\\x0c\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const LINE_END = /\r\n|[\n\x0b\x0c\r\x1c-\x1e\x85\u2028\u2029]/;
const LEADING = new RegExp(`^[${SPACE}]+`);
const EDGES = new RegExp(`^[${SPACE}]+|[${SPACE}]+$`, 'g');

// The reviewer's mention of its name, @ironbee-ai: its case ignored as Python ignores it (an i matches a dotted capital
// I and a dotless i too), no word character, /, @ or - before it, no word character or - after it. Word characters are
// ASCII here and Unicode there, so the app's edges hold wherever the reviewer's do.
const NAME = ['@', '[iI\u0130\u0131]', '[rR]', '[oO]', '[nN]', '[bB]', '[eE]', '[eE]', '-', '[aA]', '[iI\u0130\u0131]'];
const MENTION = new RegExp(`(?<![\\w/@-])${NAME.join('')}(?![\\w-])`);
// A hidden line of ours, which the reviewer leaves out of a comment before it reads it.
const HIDDEN = new RegExp(`^ {0,3}\\[//\\]: # "ironbee[^${SPACE}]* [^\\n]+?" *$`);
// The identity marker every text of the reviewer's carries.
const MARKER = /^ {0,3}\[\/\/\]: # "ironbee [^\n]+?" *$/;
// A console icon, which the reviewer reads back as its mark or as nothing. A comment holding one is read whole, quoted
// lines and code included, each icon taken for a gap the mention may span or for an edge.
const ICON = new RegExp(`!\\[[^\\]\\n]*\\]\\([^${SPACE})]*/badges/(?:severity|kind|label)-[a-z-]+-(?:light|solid)\\.svg[^${SPACE})]*\\)`, 'g');
const GAP = '\u0000';
const SPREAD = new RegExp(`(?<![\\w/@-])${NAME.join(`${GAP}*`)}(?![\\w-])`);

// Whether a comment's raw text addresses the reviewer: its mention on a line that is neither quoted nor fenced code.
export function addresses(raw) {
  const text = String(raw ?? '');
  if (text.includes('/badges/')) {
    return SPREAD.test(text.replace(ICON, GAP));
  }
  const unhidden = text.split('\n').map((line) => (HIDDEN.test(line) ? '' : line)).join('\n');
  let fenced = false;
  for (const line of unhidden.split(LINE_END)) {
    const lead = line.replace(LEADING, '');
    if (lead.startsWith('```')) {
      fenced = !fenced;
      continue;
    }
    if (fenced || lead.startsWith('>')) {
      continue;
    }
    if (MENTION.test(line)) {
      return true;
    }
  }
  return false;
}

// Whether a comment is the reviewer's: an app user's, carrying the identity marker on a line of its own.
export function isOurs(comment) {
  if (comment?.user?.type !== 'app_user') {
    return false;
  }
  const raw = String(comment.content?.raw ?? '');
  const lines = raw.split(LINE_END);
  return [...raw.split('\n'), ...lines, ...lines.map((line) => line.replace(EDGES, ''))].some((line) => MARKER.test(line));
}

// A person, as the reviewer counts one: an author of no other kind than a user.
function isPerson(comment) {
  const type = comment?.user?.type;
  return !type || type === 'user';
}

// The start of the custom pipeline with the pull request as its target, from the pull request's own branches and
// commits: Bitbucket asks for the head and the destination's commit with them.
export function startBody(pull) {
  const source = pull?.source?.branch?.name;
  const destination = pull?.destination?.branch?.name;
  const head = pull?.source?.commit?.hash;
  const base = pull?.destination?.commit?.hash;
  if (![source, destination, head, base].every((value) => typeof value === 'string' && value !== '') || !Number.isSafeInteger(pull.id)) {
    return null;
  }
  return { target: { type: 'pipeline_pullrequest_target', source, destination, destination_commit: { hash: base }, commit: { hash: head },
    pullrequest: { id: pull.id }, selector: { type: 'custom', pattern: PIPELINE } } };
}

function idOf(value) {
  if (Number.isSafeInteger(value) && value > 0) {
    return String(value);
  }
  return typeof value === 'string' && /^[1-9][0-9]{0,15}$/.test(value) ? value : null;
}

function uuidOf(value) {
  return typeof value === 'string' && /^[{}0-9A-Za-z-]{1,64}$/.test(value) ? value : null;
}

// A pull request from a fork runs no pipeline of the repository's, so its comments start nothing either.
function ownRepository(pull) {
  const source = pull?.source?.repository;
  const destination = pull?.destination?.repository;
  if (!source || !destination) {
    return false;
  }
  if (source.uuid && destination.uuid) {
    return source.uuid === destination.uuid;
  }
  return Boolean(source.full_name) && source.full_name === destination.full_name;
}

// The thread's first comment, or `deep` where the walk reached its bound: the reviewer walks a thread whole, so such a
// reply is taken, and the run tells whether the thread is ours.
async function rootOf(read, pull, comment) {
  let current = comment;
  for (let reads = 0; current.parent?.id !== undefined && current.parent?.id !== null; reads += 1) {
    if (reads === MAX_PARENTS) {
      return { deep: true };
    }
    const parent = idOf(current.parent.id);
    if (!parent) {
      return { outcome: 'thread unread' };
    }
    const next = await read(route`${pull}/comments/${parent}`);
    if (!next.data) {
      return { outcome: 'thread unread', status: next.status };
    }
    current = next.data;
  }
  return { root: current };
}

// The fixed code of Bitbucket's refusal, never its message.
async function refusal(answer) {
  try {
    const key = JSON.parse(await answer.text())?.error?.data?.key;
    return typeof key === 'string' && /^[A-Za-z0-9._-]{1,100}$/.test(key) ? key : undefined;
  } catch {
    return undefined;
  }
}

async function handle(event, ids, log) {
  if (event?.actor?.type && event.actor.type !== 'user') {
    log('not a person');
    return;
  }
  const workspace = uuidOf(ids.workspace);
  const repository = uuidOf(ids.repository);
  const number = idOf(ids.pullRequest);
  const id = idOf(ids.comment);
  if (!workspace || !repository || !number || !id) {
    log('not a pull request comment');
    return;
  }
  const bitbucket = api.asApp();
  const read = async (path) => {
    const answer = await bitbucket.requestBitbucket(path);
    return answer.status === 200 ? { status: 200, data: await answer.json() } : { status: answer.status };
  };
  const pull = route`/2.0/repositories/${workspace}/${repository}/pullrequests/${number}`;
  const comment = await read(route`${pull}/comments/${id}`);
  if (!comment.data) {
    log('comment unread', { status: comment.status });
    return;
  }
  if (!isPerson(comment.data)) {
    log('not a person');
    return;
  }
  let why = addresses(comment.data.content?.raw) ? 'addressed' : '';
  if (!why && comment.data.parent) {
    const thread = await rootOf(read, pull, comment.data);
    if (thread.deep) {
      why = 'deep thread';
    } else if (!thread.root) {
      log(thread.outcome, { status: thread.status });
      return;
    } else {
      why = isOurs(thread.root) ? 'our thread' : '';
    }
  }
  if (!why) {
    log('not for us');
    return;
  }
  const pr = await read(pull);
  if (!pr.data) {
    log('pull request unread', { why, status: pr.status });
    return;
  }
  if (pr.data.state !== 'OPEN') {
    log('pull request not open', { why, state: /^[A-Z_]{1,20}$/.test(String(pr.data.state)) ? pr.data.state : undefined });
    return;
  }
  if (!ownRepository(pr.data)) {
    log('pull request from a fork', { why });
    return;
  }
  const body = startBody(pr.data);
  if (!body) {
    log('pull request incomplete', { why });
    return;
  }
  const answer = await bitbucket.requestBitbucket(route`/2.0/repositories/${workspace}/${repository}/pipelines/`,
    { method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (answer.status === 201) {
    const run = await answer.json().catch(() => ({}));
    log('started', { why, build: Number.isSafeInteger(run?.build_number) ? run.build_number : undefined });
    return;
  }
  log('start refused', { why, status: answer.status, error: await refusal(answer) });
}

export async function onComment(event) {
  const ids = { workspace: event?.workspace?.uuid, repository: event?.repository?.uuid, pullRequest: event?.pullrequest?.id, comment: event?.comment?.id };
  const log = (outcome, more = {}) => {
    console.log(JSON.stringify({ workspace: uuidOf(ids.workspace) ?? undefined, repository: uuidOf(ids.repository) ?? undefined,
      pullRequest: idOf(ids.pullRequest) ?? undefined, comment: idOf(ids.comment) ?? undefined, outcome, ...more }));
  };
  try {
    await handle(event, ids, log);
  } catch (error) {
    log('failed', { error: typeof error?.name === 'string' ? error.name.slice(0, 40) : undefined });
  }
}
