// A stand-in for @forge/api in the app's tests: `route` as Forge builds a path (a parameter that would change the path
// is refused), and `asApp().requestBitbucket` answered by the test's own Bitbucket, every call recorded. No network.

export const calls = [];
let answer = () => [404, { type: 'error' }];

// bitbucket(fn): each call is answered by fn({method, path, body}), which gives [status, body] or throws.
export function bitbucket(fn) {
  answer = fn;
  calls.length = 0;
}

class Route {
  constructor(value) {
    this.value = value;
  }
}

export function route(strings, ...values) {
  let path = strings[0];
  values.forEach((value, i) => {
    if (value instanceof Route) {
      path += value.value;
    } else {
      const text = String(value);
      if (/\.\.|[/\\?#]/.test(text)) {
        throw new Error('Disallowing path manipulation attempt');
      }
      path += text;
    }
    path += strings[i + 1];
  });
  return new Route(path);
}

function response(status, body) {
  const text = typeof body === 'string' ? body : JSON.stringify(body);
  return { status, ok: status >= 200 && status < 300, json: async () => JSON.parse(text), text: async () => text };
}

const app = {
  async requestBitbucket(path, options = {}) {
    if (!(path instanceof Route)) {
      throw new Error('a path made with route alone');
    }
    const call = { method: options.method ?? 'GET', path: path.value, headers: options.headers ?? {}, body: options.body === undefined ? undefined : JSON.parse(options.body) };
    calls.push(call);
    const [status, body] = answer(call);
    return response(status, body);
  },
};

export function asApp() {
  return app;
}

export default { asApp, route };
