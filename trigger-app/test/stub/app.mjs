// The app as its tests load it: @forge/api resolved to the tests' stub before the app's source is read.
import { register } from 'node:module';

register('./hooks.mjs', import.meta.url);

export const forge = await import('./forge-api.mjs');
export const app = await import('../../src/index.js');
