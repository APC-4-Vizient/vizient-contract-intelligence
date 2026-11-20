import { describe, expect, it } from 'vitest';
import { bundledPackages, escapeHtml, packageFolder, renderNotices } from './notices';
import type { NoticeData } from './notices';

const DATA: NoticeData = {
  packages: {
    'react@19.0.0': { license: 'MIT', copyright: 'Copyright (c) Meta Platforms, Inc. and affiliates.', text: 'standard-mit' },
    '@scope/ui@2.1.0': { license: 'MIT', copyright: 'Copyright (c) <Someone> & "Co"', text: 'standard-mit' },
    'tslib@2.8.1': { license: '0BSD', copyright: 'Copyright (c) Microsoft Corporation.', text: 'abc12345' },
  },
  texts: {
    'standard-mit': { label: 'MIT', text: 'MIT License\n\nPermission is hereby granted, free of charge' },
    abc12345: { label: '0BSD', text: 'Zero-clause <BSD>' },
  },
};

describe('packageFolder', () => {
  it('finds the package a module sits in, on Windows and POSIX paths', () => {
    expect(packageFolder('C:\\work\\app\\node_modules\\react\\index.js')).toBe('C:/work/app/node_modules/react');
    expect(packageFolder('/work/app/node_modules/react-dom/cjs/react-dom.production.js?commonjs-es-import')).toBe('/work/app/node_modules/react-dom');
  });

  it('keeps a scope with its package and takes the innermost node_modules', () => {
    expect(packageFolder('/a/node_modules/@fluentui/react-button/lib/Button.js')).toBe('/a/node_modules/@fluentui/react-button');
    expect(packageFolder('/a/node_modules/x/node_modules/y/index.js')).toBe('/a/node_modules/x/node_modules/y');
  });

  it('ignores the project\'s own code and virtual modules', () => {
    expect(packageFolder('/work/app/src/standalone/main.tsx')).toBeNull();
    expect(packageFolder('\0vite/preload-helper.js')).toBeNull();
    expect(packageFolder('/a/node_modules/@scope')).toBeNull();
  });
});

describe('bundledPackages', () => {
  it('lists each package once, sorted, with the version read from its folder', () => {
    const ids = ['/a/node_modules/three/build/three.module.js', '/a/node_modules/react/index.js', '/a/node_modules/react/jsx-runtime.js', '/a/src/x.ts'];
    const versions: Record<string, string> = { '/a/node_modules/three': '0.186.1', '/a/node_modules/react': '19.0.0' };
    expect(bundledPackages(ids, (folder) => versions[folder])).toEqual([
      { name: 'react', version: '19.0.0' },
      { name: 'three', version: '0.186.1' },
    ]);
  });
});

describe('renderNotices', () => {
  const html = renderNotices(
    [
      { name: '@scope/ui', version: '2.1.0' },
      { name: 'react', version: '19.0.0' },
      { name: 'tslib', version: '2.8.1' },
    ],
    DATA,
  );

  it('prints a row for each package and each license text once', () => {
    expect(html).toContain('<tr><td>react</td><td>19.0.0</td><td>MIT</td>');
    expect(html.match(/Permission is hereby granted/g)).toHaveLength(1);
    expect(html).toContain('Applies to: @scope/ui, react');
    expect(html).toContain('3 open-source packages');
  });

  it('escapes everything that comes from a package', () => {
    expect(html).toContain('Copyright (c) &lt;Someone&gt; &amp; &quot;Co&quot;');
    expect(html).toContain('Zero-clause &lt;BSD&gt;');
    expect(html.toLowerCase()).not.toContain('<script');
  });

  it('refuses a package it has no notice for, and says how to fix it', () => {
    expect(() => renderNotices([{ name: 'left-pad', version: '1.0.0' }], DATA)).toThrow(/left-pad@1\.0\.0.*gen-notices\.py/);
    expect(() => renderNotices([{ name: 'tslib', version: '2.8.1' }], { ...DATA, texts: {} })).toThrow(/abc12345 is missing/);
  });

  it('shortens a long list of packages that share a text', () => {
    const many: NoticeData = { packages: {}, texts: { 'standard-mit': DATA.texts['standard-mit'] } };
    const names = Array.from({ length: 13 }, (_, index) => `pkg-${String(index).padStart(2, '0')}`);
    for (const name of names) many.packages[`${name}@1.0.0`] = { license: 'MIT', copyright: 'Copyright (c) A', text: 'standard-mit' };
    expect(renderNotices(names.map((name) => ({ name, version: '1.0.0' })), many)).toContain('the 13 packages above whose license is MIT');
  });
});

describe('escapeHtml', () => {
  it('escapes the five characters that matter', () => {
    expect(escapeHtml(`<a href="x">&'</a>`)).toBe('&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
  });
});
