import { createLightTheme, type BrandVariants, type Theme } from '@fluentui/react-components';

/*
  Fluent UI v9 theme for the Contract Review Code App. It mirrors vizient-theme.css, which is
  the source of truth for colors. Copied to contract-review/src/theme: keep both copies in sync.
*/

export const vizientFontFamilySans = '"Haffer", "Segoe UI", system-ui, -apple-system, sans-serif';
export const vizientFontFamilyHeading = '"freight-display-pro", Georgia, "Times New Roman", serif';

// Steps run dark (10) to light (160). Step 80 is Vizient mulberry. Steps 10, 40, 90, 100, 120,
// 140 and 150 are published Vizient mulberry shades; the rest are interpolated between them.
export const vizientBrand: BrandVariants = {
  10: '#0f0308',
  20: '#19050e',
  30: '#220813',
  40: '#2c0a19',
  50: '#340c1d',
  60: '#3b0d21',
  70: '#420e25',
  80: '#4a1029',
  90: '#6e3a52',
  100: '#9c546b',
  110: '#b68a9a',
  120: '#cfc0c8',
  130: '#d8ccd2',
  140: '#e2d8dc',
  150: '#eee8ec',
  160: '#f8f4f6',
};

const eggshell = '#fefcf8';
const ink = '#1d160a';
const inkMuted = '#666458';
const oysterDark = '#4b4a40';
const oysterAccent = '#727062';
const brand = '#4a1029';
// vizient.com fades buttons on hover (opacity .9) and press (.8). Fluent needs solid colors,
// so these are the brand color at 90% and 80% over eggshell.
const brandHover = '#5c283e';
const brandPressed = '#6e3f52';
const link = '#c0420e';
const linkHover = '#983514';

export const vizientTheme: Theme = {
  ...createLightTheme(vizientBrand),

  fontFamilyBase: vizientFontFamilySans,
  fontFamilyNumeric: vizientFontFamilySans,

  borderRadiusSmall: '0.25rem',
  borderRadiusMedium: '0.5rem',
  borderRadiusLarge: '0.75rem',
  borderRadiusXLarge: '1rem',

  colorNeutralBackground1: eggshell,
  colorNeutralBackground1Hover: '#f7f7f7',
  colorNeutralBackground1Pressed: '#efefef',
  colorNeutralBackground1Selected: '#eee8ec',
  colorNeutralBackground2: '#f7f7f7',
  colorNeutralBackground3: '#efefef',
  colorNeutralBackground4: '#e6e6e6',
  colorNeutralBackground5: '#e0e0e0',
  colorNeutralBackground6: '#d9d9d8',
  colorSubtleBackgroundHover: '#eee8ec',
  colorSubtleBackgroundPressed: '#e2d8dc',
  colorSubtleBackgroundSelected: '#e2d8dc',

  colorNeutralForeground1: ink,
  colorNeutralForeground1Hover: ink,
  colorNeutralForeground1Pressed: ink,
  colorNeutralForeground1Selected: ink,
  colorNeutralForeground2: oysterDark,
  colorNeutralForeground2Hover: ink,
  colorNeutralForeground2Pressed: ink,
  colorNeutralForeground2Selected: ink,
  colorNeutralForeground3: inkMuted,
  colorNeutralForeground3Hover: oysterDark,
  colorNeutralForeground3Pressed: oysterDark,
  colorNeutralForeground3Selected: oysterDark,
  colorNeutralForeground4: oysterAccent,
  colorNeutralForegroundOnBrand: eggshell,

  colorNeutralStroke1: '#c9c3b8',
  colorNeutralStroke1Hover: '#ababab',
  colorNeutralStroke1Pressed: oysterAccent,
  colorNeutralStroke1Selected: '#c9c3b8',
  colorNeutralStroke2: '#e0e0e0',
  colorNeutralStroke3: '#efefef',
  colorNeutralStrokeAccessible: inkMuted,
  colorNeutralStrokeAccessibleHover: ink,
  colorNeutralStrokeAccessiblePressed: ink,
  colorNeutralStrokeAccessibleSelected: brand,
  colorStrokeFocus1: eggshell,
  colorStrokeFocus2: '#1a9a59',

  colorBrandBackground: brand,
  colorBrandBackgroundHover: brandHover,
  colorBrandBackgroundPressed: brandPressed,
  colorBrandBackgroundSelected: brandHover,
  colorCompoundBrandBackground: brand,
  colorCompoundBrandBackgroundHover: brandHover,
  colorCompoundBrandBackgroundPressed: brandPressed,
  colorBrandBackground2: '#eee8ec',
  colorBrandBackground2Hover: '#e2d8dc',
  colorBrandBackground2Pressed: '#d8ccd2',
  colorBrandForeground1: brand,
  colorBrandForeground2: '#6e3a52',
  colorBrandForegroundLink: link,
  colorBrandForegroundLinkHover: linkHover,
  colorBrandForegroundLinkPressed: linkHover,
  colorBrandForegroundLinkSelected: link,
  colorCompoundBrandForeground1: brand,
  colorCompoundBrandForeground1Hover: brandHover,
  colorCompoundBrandForeground1Pressed: brandPressed,
  colorBrandStroke1: brand,
  colorCompoundBrandStroke: brand,
  colorCompoundBrandStrokeHover: brandHover,
  colorCompoundBrandStrokePressed: brandPressed,

  colorStatusSuccessBackground1: '#e3e6e4',
  colorStatusSuccessForeground1: '#1d3e28',
  colorStatusSuccessBorder1: '#9aaca0',
  colorStatusWarningBackground1: '#fff5cc',
  colorStatusWarningForeground1: '#56401a',
  colorStatusWarningBorder1: '#ffcc12',
  colorStatusDangerBackground1: '#f8e3e0',
  colorStatusDangerForeground1: '#c10007',
  colorStatusDangerBorder1: '#e9a4a4',
};

export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'outline' | 'brand';

// Labels come from the Dataverse choice sets in the plan (section 5): vz_presence,
// vz_aijudgment, vz_reviewstatus and the contract vz_status. Unknown labels render neutral.
const toneByLabel: Readonly<Record<string, Tone>> = {
  Found: 'success',
  Unclear: 'warning',
  'Not Found': 'neutral',
  Permitted: 'success',
  Prohibited: 'danger',
  Conditional: 'warning',
  'Not Addressed': 'neutral',
  'N/A': 'outline',
  Pending: 'outline',
  Accepted: 'success',
  Corrected: 'info',
  Rejected: 'danger',
  Received: 'neutral',
  Extracting: 'info',
  'Ready for Review': 'brand',
  'In Review': 'info',
  Approved: 'success',
  Failed: 'danger',
};

export function toneFor(label: string): Tone {
  return toneByLabel[label] ?? 'neutral';
}

// States that must not rely on color alone get a warning glyph in place of the chip's dot.
const flaggedLabels: ReadonlySet<string> = new Set(['Not Addressed']);

/** Class names for a status chip, styled by vizient-theme.css. */
export function chipClass(label: string): string {
  const flag = flaggedLabels.has(label) ? ' vz-chip--flag' : '';
  return `vz-chip vz-chip--${toneFor(label)}${flag}`;
}
