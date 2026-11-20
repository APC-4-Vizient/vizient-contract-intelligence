/*
  The open-source notices that architecture-3d.html prints for the libraries bundled into it. The data comes from
  src/standalone/third-party.json, which `python scripts/gen-notices.py` writes from the lockfile and the installed packages.
  Nothing here reads a file: the build passes in what it found, so the pieces can be tested alone.
*/

export interface NoticeData {
  packages: Record<string, { license: string; copyright: string; text: string }>;
  texts: Record<string, { label: string; text: string }>;
}

export interface BundledPackage {
  name: string;
  version: string;
}

export const REGENERATE = 'Run `python scripts/gen-notices.py`.';

const MODULES = '/node_modules/';
const LONG_LIST = 12;

/** The folder of the npm package a module sits in, or null for the project's own code and for virtual modules. */
export function packageFolder(moduleId: string): string | null {
  if (moduleId.startsWith('\0')) return null;
  const id = moduleId.split('?')[0].replace(/\\/g, '/');
  const at = id.lastIndexOf(MODULES);
  if (at < 0) return null;
  const rest = id.slice(at + MODULES.length).split('/');
  const scoped = rest[0].startsWith('@');
  const parts = scoped ? rest.slice(0, 2) : rest.slice(0, 1);
  return parts.length < (scoped ? 2 : 1) || parts.some((part) => part === '') ? null : id.slice(0, at + MODULES.length) + parts.join('/');
}

/** Every package the modules come from, once each, with the version that readVersion finds in its folder. */
export function bundledPackages(moduleIds: Iterable<string>, readVersion: (folder: string) => string): BundledPackage[] {
  const folders = new Set<string>();
  for (const id of moduleIds) {
    const folder = packageFolder(id);
    if (folder) folders.add(folder);
  }
  return [...folders]
    .map((folder) => ({ name: folder.slice(folder.lastIndexOf(MODULES) + MODULES.length), version: readVersion(folder) }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/** The notices as a closed <details> block for the bottom of the page. Throws when a bundled package has no entry, so a new library cannot ship unlisted. */
export function renderNotices(bundled: readonly BundledPackage[], data: NoticeData): string {
  const rows: string[] = [];
  const usedBy = new Map<string, string[]>();
  for (const { name, version } of bundled) {
    const entry = data.packages[`${name}@${version}`];
    if (!entry) throw new Error(`${name}@${version} is in the page but not in src/standalone/third-party.json. ${REGENERATE}`);
    rows.push(`<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(version)}</td><td>${escapeHtml(entry.license)}</td><td>${escapeHtml(entry.copyright)}</td></tr>`);
    usedBy.set(entry.text, [...(usedBy.get(entry.text) ?? []), name]);
  }
  const texts = [...usedBy.entries()]
    .map(([id, names]) => {
      const text = data.texts[id];
      if (!text) throw new Error(`The license text ${id} is missing from src/standalone/third-party.json. ${REGENERATE}`);
      return { id, label: text.label, body: text.text, names };
    })
    .sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id))
    .map(({ label, body, names }) => {
      const applies = names.length > LONG_LIST ? `the ${names.length} packages above whose license is ${label}` : names.join(', ');
      return `<section><h3>${escapeHtml(label)}</h3><p>Applies to: ${escapeHtml(applies)}</p><pre>${escapeHtml(body)}</pre></section>`;
    });
  return [
    '<details id="open-source-notices" class="notices">',
    '<summary>Open-source notices</summary>',
    `<p>This page contains the ${bundled.length} open-source packages below. Each is used under its own license, which follows the table.</p>`,
    '<table><thead><tr><th>Package</th><th>Version</th><th>License</th><th>Copyright</th></tr></thead><tbody>',
    ...rows,
    '</tbody></table>',
    ...texts,
    '</details>',
    '',
  ].join('\n');
}
