/** Apply Alembic-generated SQL through Neon's HTTPS driver when TCP is unavailable. */

import { readFile } from "node:fs/promises";
import { neon } from "@neondatabase/serverless";

function splitStatements(source) {
  const statements = [];
  let current = "";
  let quote = null;
  let lineComment = false;
  let blockComment = false;

  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    const next = source[index + 1];

    if (lineComment) {
      if (char === "\n") lineComment = false;
      current += char;
      continue;
    }
    if (blockComment) {
      current += char;
      if (char === "*" && next === "/") {
        current += next;
        blockComment = false;
        index += 1;
      }
      continue;
    }
    if (quote) {
      current += char;
      if (char === quote) {
        if (next === quote) {
          current += next;
          index += 1;
        } else {
          quote = null;
        }
      }
      continue;
    }
    if (char === "-" && next === "-") {
      current += `${char}${next}`;
      lineComment = true;
      index += 1;
      continue;
    }
    if (char === "/" && next === "*") {
      current += `${char}${next}`;
      blockComment = true;
      index += 1;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      current += char;
      continue;
    }
    if (char === ";") {
      const statement = current.trim();
      if (statement) statements.push(statement);
      current = "";
      continue;
    }
    current += char;
  }

  const remainder = current.trim();
  if (remainder) statements.push(remainder);
  return statements.filter(
    (statement) => !["BEGIN", "COMMIT"].includes(statement.toUpperCase()),
  );
}

const [sqlPath] = process.argv.slice(2);
if (!sqlPath) throw new Error("Usage: node scripts/apply_neon_sql.mjs <sql-file>");
if (!process.env.DIRECT_DATABASE_URL) {
  throw new Error("DIRECT_DATABASE_URL is required");
}

const source = await readFile(sqlPath, "utf8");
const statements = splitStatements(source);
const sql = neon(process.env.DIRECT_DATABASE_URL);
await sql.transaction(statements.map((statement) => sql.query(statement)));
console.log(JSON.stringify({ appliedStatements: statements.length }));
