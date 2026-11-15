// The tests' module hooks: @forge/api is the tests' stub, and the app's own source is read as the ES module Forge's
// bundler takes it for.
const STUB = new URL('./forge-api.mjs', import.meta.url).href;

export async function resolve(specifier, context, next) {
  if (specifier === '@forge/api') {
    return { url: STUB, shortCircuit: true };
  }
  const resolved = await next(specifier, context);
  return resolved.url.endsWith('/src/index.js') ? { ...resolved, format: 'module' } : resolved;
}
