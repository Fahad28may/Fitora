import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";

/**
 * Static guard for §44. Rendering every screen to check this would need each
 * one's data dependencies mocked; scanning the source catches the same
 * regression — a new button shipped without an accessible name — at a
 * fraction of the cost, and it fails on the file that introduced it.
 */

const ROOTS = ["app", "src"];
const IGNORED_DIRS = new Set(["node_modules", "__tests__", ".expo", "dist"]);

/** Elements a screen reader announces only if we give them a name. */
const INTERACTIVE = /<(TouchableOpacity|Pressable|TextInput|Switch)\b/g;
const ACCESSIBLE_PROP = /accessibilityLabel|accessibilityRole|accessibilityState|accessible\b/;

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (!IGNORED_DIRS.has(entry)) out.push(...sourceFiles(full));
    } else if (entry.endsWith(".tsx")) {
      out.push(full);
    }
  }
  return out;
}

/** The JSX element starting at `start`, up to its closing bracket. */
function elementAt(source: string, start: number): string {
  let depth = 0;
  for (let i = start; i < source.length; i += 1) {
    const char = source[i];
    if (char === "{") depth += 1;
    else if (char === "}") depth -= 1;
    else if (char === ">" && depth === 0) return source.slice(start, i + 1);
  }
  return source.slice(start);
}

describe("accessibility", () => {
  const files = ROOTS.flatMap((root) => sourceFiles(root));

  it("finds source files to check", () => {
    expect(files.length).toBeGreaterThan(5);
  });

  it.each(files)("%s labels every interactive element", (file) => {
    const source = readFileSync(file, "utf8");
    const unlabelled: string[] = [];

    for (const match of source.matchAll(INTERACTIVE)) {
      const element = elementAt(source, match.index);
      if (!ACCESSIBLE_PROP.test(element)) {
        const line = source.slice(0, match.index).split("\n").length;
        unlabelled.push(`${match[1]} at ${file}:${line}`);
      }
    }

    expect(unlabelled).toEqual([]);
  });
});
