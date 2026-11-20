import { describe, expect, it } from 'vitest';
import { externalReferences, inlineAssets } from './inlineHtml';

const PAGE = [
  '<!doctype html>',
  '<html lang="en"><head>',
  '<link rel="icon" href="data:," />',
  '<script type="module" crossorigin src="./assets/standalone-AbC123.js"></script>',
  '<link rel="stylesheet" crossorigin href="./assets/standalone-XyZ789.css">',
  '</head><body><div id="root"></div></body></html>',
].join('\n');

const SCRIPT = { name: 'assets/standalone-AbC123.js', content: 'console.log("hello");' };
const STYLE = { name: 'assets/standalone-XyZ789.css', content: 'body{margin:0}' };

/** The code of the one inline script in a page. */
function scriptCode(html: string): string {
  const match = /<script type="module">\n([\s\S]*)\n<\/script>/.exec(html);
  if (!match) throw new Error('No inline script found.');
  return match[1];
}

describe('inlineAssets', () => {
  it('puts the script and the stylesheet inside the page and leaves nothing to fetch', () => {
    const html = inlineAssets(PAGE, [SCRIPT, STYLE]);
    expect(html).toContain('<script type="module">\nconsole.log("hello");\n</script>');
    expect(html).toContain('<style>\nbody{margin:0}\n</style>');
    expect(externalReferences(html.replace(SCRIPT.content, '').replace(STYLE.content, ''))).toEqual([]);
    expect(html).not.toContain('./assets/');
    expect(html).toContain('<link rel="icon" href="data:," />');
  });

  it('keeps the dollar sequences of minified code as they are', () => {
    const code = 'const a="$&$1$\'$`$$";';
    const html = inlineAssets(PAGE, [{ ...SCRIPT, content: code }, STYLE]);
    expect(scriptCode(html)).toBe(code);
  });

  it('breaks up closing tags and comment openers without changing what the code means', () => {
    const code = 'const text = "a</script><!--b</SCRIPT>c"; const rx = /<!--/u;';
    const inlined = scriptCode(inlineAssets(PAGE, [{ ...SCRIPT, content: code }, STYLE]));
    expect(inlined.toLowerCase()).not.toContain('</script');
    expect(inlined).not.toContain('<!--');
    const run = (source: string) => new Function(`${source}; return [text, rx.test('<!--')];`)() as [string, boolean];
    expect(run(inlined)).toEqual(run(code));
    expect(run(inlined)).toEqual(['a</script><!--b</SCRIPT>c', true]);
  });

  it('also protects a stylesheet from a closing style tag', () => {
    const css = '.a::before{content:"</style>"}';
    const html = inlineAssets(PAGE, [SCRIPT, { ...STYLE, content: css }]);
    expect(html.match(/<\/style/gi)).toHaveLength(1);
  });

  it('writes plain line feeds, whatever line endings the page and the files came with', () => {
    const crlfPage = PAGE.replace(/\n/g, '\r\n');
    const script = { ...SCRIPT, content: 'const a = 1;\r\nconst b = `x\r\ny`;\rconst c = "\\r";' };
    const style = { ...STYLE, content: 'a{}\r\nb{}\rc{}' };
    const html = inlineAssets(`${crlfPage}\r`, [script, style]);
    expect(html).not.toContain('\r');
    expect(scriptCode(html)).toBe('const a = 1;\nconst b = `x\ny`;\nconst c = "\\r";');
  });

  it('refuses a file that the page does not point at', () => {
    expect(() => inlineAssets(PAGE, [SCRIPT, STYLE, { name: 'assets/other-Q1.js', content: '1' }])).toThrow(/other-Q1\.js/);
  });

  it('refuses a file type it cannot put in a page', () => {
    expect(() => inlineAssets(PAGE, [SCRIPT, STYLE, { name: 'assets/font-Q1.woff2', content: '1' }])).toThrow(/woff2/);
  });

  it('refuses a page that already holds the character it uses to mark places', () => {
    expect(() => inlineAssets(PAGE.replace('<div', '\uE000<div'), [SCRIPT, STYLE])).toThrow(/marks where a file goes/);
  });

  it('refuses a page that still points at another file or at a host', () => {
    const preload = PAGE.replace('</head>', '<link rel="modulepreload" href="./assets/chunk-1.js"></head>');
    expect(() => inlineAssets(preload, [SCRIPT, STYLE])).toThrow(/chunk-1\.js/);
    const remote = PAGE.replace('</head>', '<script src="https://cdn.example.org/lib.js"></script></head>');
    expect(() => inlineAssets(remote, [SCRIPT, STYLE])).toThrow(/cdn\.example\.org/);
    const imported = PAGE.replace('</head>', '<style>@import url("https://fonts.example.org/f.css");</style></head>');
    expect(() => inlineAssets(imported, [SCRIPT, STYLE])).toThrow(/fonts\.example\.org/);
  });
});

describe('externalReferences', () => {
  it('lists scripts, links, imports and urls, and ignores data URIs', () => {
    const html =
      '<link rel="icon" href="data:,"><script src="a.js"></script><link href=\'b.css\'>' +
      '<style>@import "c.css"; .x{background:url(data:image/png;base64,AAAA)} .y{background:url(d.png)}</style>';
    expect(externalReferences(html)).toEqual(['a.js', 'b.css', 'c.css', 'd.png']);
  });
});
