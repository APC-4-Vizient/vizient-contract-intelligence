/*
  Turns the page that Vite builds, with its script and stylesheet files, into one HTML string that needs nothing else:
  the code and the styles sit inside the page, so it opens from a folder, an e-mail attachment or a file share, with
  no server and no network. Pure string work, so a test can run it without a build.
*/

export interface BuiltFile {
  /** The file's path in the build output, such as `assets/standalone-AbC123.js`. */
  name: string;
  content: string;
}

const regexEscape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/*
  A script element ends at the first closing tag the parser meets, even inside a string, and `<!--` changes how it
  reads the rest. Both are respelled so that they mean the same to the code and nothing to the page.
*/
const scriptSafe = (code: string) => code.replace(/<\/(script)/gi, '<\\/$1').replace(/<!--/g, '<\\x21--');
const styleSafe = (css: string) => css.replace(/<\/(style)/gi, '<\\/$1');

const isInternal = (url: string) => url === '' || url.startsWith('data:') || url.startsWith('#');

// A character from the private-use area, which no page contains, marks where a file's contents will go.
const PLACEHOLDER = '\uE000';

// Plain LF everywhere, so the page is the same text on every machine and Git does not take a stray CR for a binary file.
const lf = (text: string) => text.replace(/\r\n?/g, '\n');

/** Every file or host that the text would make a browser fetch: script and link elements, `@import` and `url()`. */
export function externalReferences(text: string): string[] {
  const found: string[] = [];
  const collect = (pattern: RegExp) => {
    for (const match of text.matchAll(pattern)) {
      const url = (match[1] ?? match[2] ?? match[3] ?? '').trim();
      if (!isInternal(url) && !found.includes(url)) found.push(url);
    }
  };
  collect(/<(?:script|img|iframe|source|video|audio|embed|track)\b[^>]*?\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)')/gi);
  collect(/<link\b[^>]*?\bhref\s*=\s*(?:"([^"]*)"|'([^']*)')/gi);
  collect(/@import\s+(?:url\(\s*)?(?:"([^"]*)"|'([^']*)'|([^)\s"';]+))/gi);
  collect(/\burl\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s"']+))/gi);
  return found;
}

/**
  Replaces the page's script and stylesheet tags with the files' contents. It throws instead of guessing when a file has
  no tag, when a file is not a script or a stylesheet, or when anything in the result would still be fetched.
*/
export function inlineAssets(html: string, files: readonly BuiltFile[]): string {
  if (html.includes(PLACEHOLDER)) throw new Error('The page already holds the character that marks where a file goes.');
  const blocks: string[] = [];
  const stillNeeded: string[] = [];
  let skeleton = lf(html);
  for (const file of files) {
    const base = regexEscape(file.name.split('/').pop() ?? file.name);
    const content = lf(file.content);
    let tag: RegExp;
    let block: string;
    if (file.name.endsWith('.js')) {
      tag = new RegExp(`<script\\b[^>]*\\bsrc="(?:[^"]*/)?${base}"[^>]*></script>`);
      block = `<script type="module">\n${scriptSafe(content)}\n</script>`;
    } else if (file.name.endsWith('.css')) {
      tag = new RegExp(`<link\\b[^>]*\\bhref="(?:[^"]*/)?${base}"[^>]*>`);
      block = `<style>\n${styleSafe(content)}\n</style>`;
      stillNeeded.push(...externalReferences(content));
    } else {
      throw new Error(`Cannot put ${file.name} in the page: only scripts and stylesheets can be inlined.`);
    }
    if (!tag.test(skeleton)) throw new Error(`The page does not point at ${file.name}.`);
    // A placeholder keeps the code out of the checks below and out of String.replace's $ patterns.
    skeleton = skeleton.replace(tag, () => `${PLACEHOLDER}${blocks.length}${PLACEHOLDER}`);
    blocks.push(block);
  }
  stillNeeded.push(...externalReferences(skeleton));
  if (stillNeeded.length > 0) throw new Error(`The page would still fetch ${[...new Set(stillNeeded)].join(', ')}.`);
  return skeleton.replace(new RegExp(`${PLACEHOLDER}(\\d+)${PLACEHOLDER}`, 'g'), (_match, index: string) => blocks[Number(index)]);
}
