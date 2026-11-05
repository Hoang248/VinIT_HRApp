import english from './en.json';

export type Locale = 'vi' | 'en';
export type Arguments = Array<string | number | boolean | null | undefined>;
const translations: Record<string, string> = english;
// This also lets already-displayed validation messages update when switching
// languages. Never apply this function to candidate-authored data.
const reverse = Object.fromEntries(Object.entries(translations).map(([vi, en]) => [en, vi]));

// Recover template arguments from an already displayed message after a switch.
const templates = Object.entries(translations).filter(([vi]) => /\{\d+\}/.test(vi));
function matchTemplate(text: string, template: string): string[] | null {
  const parts = template.split(/(\{\d+\})/);
  const indexes: number[] = [];
  const expression = parts.map(part => {
    const match = /^\{(\d+)\}$/.exec(part);
    if (match) { indexes.push(Number(match[1])); return '(.*?)'; }
    return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }).join('');
  const match = new RegExp(`^${expression}$`, 's').exec(text);
  if (!match) return null;
  const values: string[] = [];
  indexes.forEach((index, i) => { values[index] = match[i + 1]; });
  return values;
}

export function translate(key: string, locale: Locale, ...args: Arguments): string {
  let original = locale === 'vi' ? (reverse[key] || key) : key;
  let values = args;
  if (!args.length && !translations[original] && !reverse[key]) {
    for (const [vi, en] of templates) {
      const matched = matchTemplate(key, locale === 'vi' ? en : vi);
      if (matched) { original = vi; values = matched; break; }
    }
  }
  const value = locale === 'en' ? (translations[original] || key) : original;
  return value.replace(/\{(\d+)\}/g, (_, index: string) => String(values[Number(index)] ?? ''));
}
