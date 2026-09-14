import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
test("runtime palette matches the maintained DESIGN.md adapter", () => {
  const doc = readFileSync(new URL("../../DESIGN.md", import.meta.url), "utf8");
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );
  const colors = doc.split("colors:\n")[1].split("typography:")[0];
  for (const [, name, value] of colors.matchAll(
    /^  ([\w-]+): "(#[A-Fa-f0-9]+)"/gm,
  )) {
    const variable =
      name === "text-muted" ? "muted" : name === "success" ? "accent" : name;
    assert.match(
      css,
      new RegExp(`--${variable}:\\s*${value}`, "i"),
      `${name} has drifted`,
    );
  }
});
