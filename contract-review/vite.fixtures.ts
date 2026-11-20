import { existsSync, readFileSync, readdirSync } from 'node:fs';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { join } from 'node:path';
import type { Plugin } from 'vite';

const ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;
const FILE_PATTERN = /^([a-z0-9][a-z0-9-]{0,63})\.(json|pdf)$/;

/** Sample contracts that have both a saved analysis and the PDF it came from. */
function listIds(samples: string): string[] {
  const results = join(samples, 'results');
  if (!existsSync(results)) return [];
  return readdirSync(results)
    .filter((file) => file.endsWith('.json'))
    .map((file) => file.slice(0, -'.json'.length))
    .filter((id) => ID_PATTERN.test(id) && !id.startsWith('probe') && existsSync(join(samples, `${id}.pdf`)))
    .sort();
}

function send(res: ServerResponse, status: number, type: string, body: string | Uint8Array): void {
  res.statusCode = status;
  res.setHeader('Content-Type', type);
  res.setHeader('Cache-Control', 'no-store');
  res.end(body);
}

/** Dev server only: serves the saved synthetic contracts at /__fixtures__ for `vite --mode mock`. */
export function mockFixtures(repoRoot: string): Plugin {
  const samples = join(repoRoot, 'samples');
  const checklist = join(repoRoot, 'checklist', 'checklist.json');

  function handle(req: IncomingMessage, res: ServerResponse): void {
    const name = new URL(req.url ?? '/', 'http://localhost').pathname.slice(1);
    const match = FILE_PATTERN.exec(name);

    if (name === 'index.json') {
      send(res, 200, 'application/json', JSON.stringify(listIds(samples)));
    } else if (name === 'checklist.json' && existsSync(checklist)) {
      send(res, 200, 'application/json', readFileSync(checklist));
    } else if (match && listIds(samples).includes(match[1])) {
      const isJson = match[2] === 'json';
      const file = isJson ? join(samples, 'results', `${match[1]}.json`) : join(samples, `${match[1]}.pdf`);
      send(res, 200, isJson ? 'application/json' : 'application/pdf', readFileSync(file));
    } else {
      send(res, 404, 'text/plain', 'Not found');
    }
  }

  return {
    name: 'vz-mock-fixtures',
    configureServer(server) {
      server.middlewares.use('/__fixtures__', handle);
    },
  };
}
