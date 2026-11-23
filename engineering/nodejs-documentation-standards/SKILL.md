---
name: nodejs-documentation-standards
description: "JSDoc standards for Node.js and TypeScript: syntax by declaration type, tag reference, what to document, common mistakes, and a checklist. Use when writing or auditing JSDoc on exported declarations."
---
# Node.js / TypeScript Documentation Standards

A comprehensive guide to JSDoc documentation comments following the JSDoc
specification and TypeScript best practices. This document serves as the
knowledge base for the nodejs-doc-comments pattern.

## Table of Contents

1. [Core Principles](#core-principles)
2. [Syntax by Declaration Type](#syntax-by-declaration-type)
3. [JSDoc Tags Reference](#jsdoc-tags-reference)
4. [What to Document](#what-to-document)
5. [Common Mistakes](#common-mistakes)
6. [Writing and Auditing Workflow](#writing-and-auditing-workflow)
7. [Quality Checklist](#quality-checklist)

---

## Core Principles

### The Golden Rule

JSDoc blocks appear **immediately before** the export/declaration with **no
intervening blank lines**. All exported names that carry non-obvious meaning
should have JSDoc blocks. Trivial getters/setters and re-exports are
intentionally left undocumented — a block that only restates the name is a
defect, not a fix.

### Philosophy

| Principle | Description |
|-----------|-------------|
| Complete sentences | Start with an action verb or noun phrase |
| Explain what | Not how it works internally |
| User focus | Focus on caller needs, not implementation |
| Searchable | Clear, explicit, searchable text |
| No redundancy | Avoid "processData — processes the data" |
| Add value | Provide info beyond the function signature |

### Line Length

All comment lines should stay within **80 characters** for readability.

---

## Syntax by Declaration Type

### Functions

```ts
/**
 * Fetches the user with the given ID from the database.
 *
 * @param id - The user's UUID
 * @returns The matching user object, or `null` if not found
 * @throws {DatabaseError} If the database is unreachable
 * @example
 * const user = await getUserById('abc-123');
 * if (!user) throw new NotFoundError('User not found');
 */
export async function getUserById(id: string): Promise<User | null> {
  // ...
}
```

**Rules:**

- Start with an imperative verb: "Fetches...", "Creates...", "Returns...",
  "Validates..."
- `@param name - description` (dash separator, not colon)
- `@returns` describes what is returned and when `null`/`undefined` is possible
- Omit TypeScript types in `@param` and `@returns` for `.ts` files — the
  type system is the source of truth

### Classes

```ts
/**
 * Manages a pool of database connections for efficient reuse.
 *
 * All public methods are safe for concurrent use by multiple callers.
 * Call {@link ConnectionPool.close} when done to release all connections.
 */
export class ConnectionPool {
  /**
   * Creates a new connection pool with the given configuration.
   *
   * @param config - Pool settings. `maxConnections` defaults to 10.
   */
  constructor(private readonly config: PoolConfig) {}
}
```

**Rules:**

- Use "Manages...", "Represents...", "Provides..."
- Document concurrency safety explicitly when relevant
- Document cleanup requirements (`.close()`, `.destroy()`)

### Interfaces and Type Aliases

```ts
/**
 * Configuration options for the HTTP client.
 */
export interface HttpClientOptions {
  /** Base URL prepended to all request paths. */
  baseUrl: string;

  /**
   * Request timeout in milliseconds. Defaults to 30 000.
   * Set to 0 to disable timeout.
   */
  timeout?: number;
}

/**
 * Represents a paginated response envelope from the API.
 */
export type PaginatedResponse<T> = {
  data: T[];
  /** Total number of items across all pages. */
  total: number;
  page: number;
};
```

### Constants and Enums

```ts
/** Maximum number of retry attempts for transient failures. */
export const MAX_RETRIES = 3;

/** Retry delay in milliseconds between attempts. */
export const RETRY_DELAY_MS = 500;

/**
 * HTTP status codes used by the API.
 */
export enum HttpStatus {
  /** Request succeeded. */
  OK = 200,
  /** Resource was not found. */
  NotFound = 404,
  /** Internal server error. */
  InternalServerError = 500,
}
```

### Error Variables / Sentinel Errors

```ts
/**
 * Thrown when a requested resource cannot be found.
 * Use `errors.is(err, ErrNotFound)` or `err instanceof NotFoundError` to check.
 */
export class NotFoundError extends Error {}

/**
 * Returned by database operations when a record does not exist.
 */
export const ErrNotFound = new Error('not found');
```

### Boolean Functions

```ts
/**
 * Returns `true` if the email address passes RFC 5322 format validation.
 */
export function isValidEmail(email: string): boolean {}

/**
 * Returns `true` if the user account is active and not suspended.
 */
export function isActiveUser(user: User): boolean {}
```

---

## JSDoc Tags Reference

### Core Tags

| Tag | Usage | Example |
|-----|-------|---------|
| `@param name - desc` | Document a parameter | `@param id - The user UUID` |
| `@returns desc` | Document return value | `@returns The matching user or null` |
| `@throws {Type} desc` | Document thrown errors | `@throws {ValidationError} If input is invalid` |
| `@example` | Code example block | See below |
| `@deprecated desc` | Mark as deprecated | `@deprecated Use createClientV2 instead` |
| `@remarks desc` | Additional context | `@remarks Not safe for concurrent use` |
| `@see` | Cross-reference | `@see {@link getUserById}` |
| `@since version` | Version introduced | `@since 2.0.0` |

### @example Tag

````ts
/**
 * Parses a JWT and returns its payload without verifying the signature.
 *
 * @param token - The encoded JWT string
 * @returns The decoded payload object
 * @throws {SyntaxError} If the token is malformed
 * @example
 * ```ts
 * const payload = decodeJwt(token);
 * console.log(payload.sub); // user ID
 * ```
 */
export function decodeJwt(token: string): JwtPayload {}
````

### @deprecated Tag

```ts
/**
 * Creates an HTTP client using the legacy connection model.
 *
 * @deprecated Use {@link createHttpClientV2} which supports connection
 * pooling. This function will be removed in v3.0.0.
 */
export function createHttpClient(url: string): HttpClient {}
```

### TypeScript-Specific Conventions

For `.ts` files, **omit types** from `@param` and `@returns` — they are
redundant with the TypeScript signature:

```ts
// Good in TypeScript:
/**
 * @param userId - The target user's UUID
 * @returns The user record, or `null` if not found
 */
async function getUser(userId: string): Promise<User | null>

// Bad — redundant types in TypeScript:
/**
 * @param {string} userId - The target user's UUID
 * @returns {Promise<User|null>} The user record
 */
async function getUser(userId: string): Promise<User | null>
```

For `.js` files (no TypeScript), include types:

```js
/**
 * @param {string} userId - The target user's UUID
 * @returns {Promise<User|null>} The user record, or null if not found
 */
async function getUser(userId) {}
```

---

## What to Document

### Async / Promise Behavior

Document when non-standard:

```ts
/**
 * Sends an email to the specified address.
 *
 * This function resolves as soon as the message is queued — delivery
 * is not guaranteed. Listen to the `'delivery'` event for confirmation.
 */
export async function sendEmail(to: string, subject: string): Promise<void> {}
```

### Error Values

Document when the error is thrown on the class, and document every public
property on the error with what its value means to callers handling it (for
example, when or after what delay a rate-limited request may be retried, or
which field failed validation). State units when the code or type establishes
them; when the implementation stores a caller-supplied number without fixing a
unit, explain the property's retry or failure semantics to the caller without
inventing an unverified unit:

```ts
/**
 * Thrown when a rate limit is exceeded.
 *
 * Inspect {@link RateLimitError.retryAfter} to determine when the request
 * may be retried.
 */
export class RateLimitError extends Error {
  /**
   * Caller-supplied retry/backoff value, set by the code that threw this
   * error, indicating when the rate-limited operation may be retried.
   */
  retryAfter: number;
}
```

### Cleanup Requirements

```ts
/**
 * Opens a connection to the message broker.
 *
 * Always call {@link BrokerClient.disconnect} when done to prevent
 * connection leaks, even if an error is thrown during use.
 */
export async function connect(url: string): Promise<BrokerClient> {}
```

### Parameter Constraints

Read the implementation and document caller-observable bounds, defaults,
clamping or rounding, and execution semantics (such as minimum intervals
enforced with `Math.max`, whether the first tick waits one interval, overlap
behavior, or callback rejection handling). Never claim constraints the code
does not enforce:

```ts
/**
 * Schedules a job to run at the specified interval.
 *
 * @param intervalMs - Polling interval in milliseconds; values below 100
 *   are rounded up to 100 to prevent CPU saturation.
 * @param fn - Async callback invoked on each tick.
 */
export function schedule(intervalMs: number, fn: () => Promise<void>): Job {}
```

### Return Value Semantics

```ts
/**
 * Searches for users matching the given filter.
 *
 * @returns A paginated result set. Returns an empty `data` array (not
 *   `null`) when no users match. The `total` field always reflects the
 *   full count across all pages.
 */
export async function searchUsers(filter: UserFilter): Promise<PaginatedResult<User>> {}
```

---

## Common Mistakes

### Redundant Comments

**Bad:**

```ts
/** Gets the user. */
export function getUser(id: string): Promise<User> {}
```

**Good:**

```ts
/**
 * Fetches the user with the given ID, including their profile and roles.
 *
 * @param id - The user's UUID
 * @returns The full user object with profile data populated
 * @throws {NotFoundError} If no user exists with the given ID
 */
export function getUser(id: string): Promise<User> {}
```

**Best (when the name already says it all):** add no block. For trivial
getters/setters or re-exports, leaving the declaration undocumented is
correct — list it as trivial in the skipped table. A lateral rewrite of an
already-adequate block is not an improvement either; leave it alone.

### Implementation Details

**Bad:**

```ts
/** Queries the users table with a prepared statement and maps rows. */
export function getUser(id: string): Promise<User> {}
```

**Good:**

```ts
/** Fetches the user with the given ID. */
export function getUser(id: string): Promise<User> {}
```

### Blank Line Between JSDoc and Declaration

**Bad:**

```ts
/**
 * Fetches a user by ID.
 */

export function getUser(id: string): Promise<User> {} // blank line = JSDoc not attached!
```

**Good:**

```ts
/**
 * Fetches a user by ID.
 */
export function getUser(id: string): Promise<User> {} // no blank line
```

### Missing @throws

**Bad:**

```ts
/**
 * Parses a JSON string and returns the result.
 */
export function parseJson(raw: string): unknown {}
```

**Good:**

```ts
/**
 * Parses a JSON string and returns the typed result.
 *
 * @param raw - The JSON string to parse
 * @returns The parsed value
 * @throws {SyntaxError} If `raw` is not valid JSON
 */
export function parseJson(raw: string): unknown {}
```

---

## Special Syntax

### Deprecation

```ts
/**
 * @deprecated Use {@link createClientV2} instead. This method does not
 * support retries and will be removed in v3.0.0.
 */
export function createClient(): Client {}
```

### Doc Links (TypeDoc / TSDoc)

```ts
/**
 * Creates a new {@link Session} from the given token.
 *
 * @see {@link SessionOptions} for available configuration options
 */
export function createSession(token: string): Session {}
```

### Module-Level Documentation

```ts
/**
 * @module auth
 *
 * Provides authentication utilities including JWT parsing, session
 * management, and permission checks.
 *
 * @example
 * ```ts
 * import { createSession, checkPermission } from './auth';
 * ```
 */
```

---

## Tools and Automation

### TypeDoc

Generate HTML docs from JSDoc + TypeScript types:

```bash
npm install --save-dev typedoc
npx typedoc --entryPoints src/index.ts --out docs
```

### TSDoc Linter

```bash
npm install --save-dev @microsoft/tsdoc @microsoft/tsdoc-config
```

### ESLint JSDoc Plugin

```bash
npm install --save-dev eslint-plugin-jsdoc

# .eslintrc.js
module.exports = {
  plugins: ['jsdoc'],
  rules: {
    'jsdoc/require-jsdoc': ['warn', { publicOnly: true }],
    'jsdoc/require-param-description': 'warn',
    'jsdoc/require-returns-description': 'warn',
  },
};
```

---

## Writing and Auditing Workflow

### Writing JSDoc for Declarations

1. **Read the implementation first.** Inspect every exported declaration and
   its body so comments capture real caller-observable behavior: parameter
   clamping or defaults, `null`/`undefined` return conditions, thrown errors,
   custom `Error` property meanings, async or timer scheduling semantics, and
   idempotent cleanup or cancellation. Do not invent units or runtime
   guarantees the code does not establish.
2. **Modify comments only.** Never alter runtime logic, type annotations,
   signatures, or exports when adding or fixing JSDoc. Place every `/** ... */`
   block immediately above its declaration (and above documented interface
   methods, class properties, and constructors) with **no blank line** between
   the closing `*/` and the declaration.
3. **Omit brace types in TypeScript.** In `.ts` and `.tsx` files, never write
   `{Type}` on `@param` or `@returns` (`@throws {ErrorType}` is the sole tag
   that names a type in braces, because TypeScript signatures do not declare
   thrown error types).
4. **Show the documented code only when the user cannot see the edits.** When
   the documented declarations cannot be written where the user will see them
   (for example, the original file cannot be edited in place, so you write the
   edits to a copy or scratch location instead), or when the user asks for
   them, present them in a code block in your reply
   (the full file when concise, or every documented export with its attached
   JSDoc block and signature) so reviewers can verify block attachment, tag
   syntax, and descriptions directly. If a calling agent or task defines a
   report format, follow that format instead. Note any exported declarations
   intentionally left undocumented as trivial.

### Auditing Existing JSDoc

Group findings by declaration and call out every defect:

- **Detached blocks:** Any blank line between `*/` and the `export` or member
  declaration detaches the comment in TypeScript, TypeDoc, and IDE tooltips.
- **Redundant types in `.ts`:** `{type}` annotations on `@param` or `@returns`
  duplicate the TypeScript signature and can drift out of sync.
- **No-information summaries:** Comments like `/** Gets the user. */` or
  `@returns The user` restate the identifier without adding semantics (such as
  source, `null` conditions, or side effects).
- **Missing `@throws` or caveats:** Functions that call throwing APIs (such as
  `JSON.parse` throwing `SyntaxError` on malformed JSON) or perform unchecked
  `as T` casts without runtime validation must document those hazards.

Provide corrected JSDoc blocks immediately above their declarations so each
fix is ready to apply.

---

## Quality Checklist

### Before Submitting

- [ ] All exported names with non-obvious meaning have JSDoc blocks (trivial getters/setters/re-exports left undocumented)
- [ ] Comments start with an action verb or noun phrase
- [ ] Complete sentences with proper punctuation
- [ ] No blank line between JSDoc block and declaration (including interface methods, class properties, and constructors)
- [ ] Lines within 80 characters
- [ ] `@param` for all non-obvious parameters, with no `{type}` braces in `.ts` files
- [ ] `@returns` describing the return value semantics, with no `{type}` braces in `.ts` files
- [ ] `@throws` for known/documented error types
- [ ] Custom `Error` properties and parameter clamping/bounds documented with caller semantics
- [ ] Async behavior documented when non-obvious
- [ ] Cleanup requirements documented
- [ ] Deprecated exports marked with `@deprecated`
- [ ] Documented declarations shown in the response when the edits cannot be written where the user sees them (including edits written to a copy instead of the original file) or the user asks (a calling agent's report format takes precedence)

### Common Patterns

| Declaration | Pattern |
|-------------|---------|
| `async function` returning value | "Fetches...", "Creates...", "Resolves..." |
| `function` returning bool | "Returns `true` if [condition]" |
| `function` with side effects | "[Action]s [object]..." |
| `class` | "Manages...", "Represents...", "Provides..." |
| Error class/constant | "[Name] is thrown when..." |
| Constant | "[Name] is the [purpose]..." |
| Type alias | "Represents..." |

---

## References

- [JSDoc Reference](https://jsdoc.app/)
- [TSDoc Specification](https://tsdoc.org/)
- [TypeDoc Documentation](https://typedoc.org/)
- [TypeScript JSDoc Reference](https://www.typescriptlang.org/docs/handbook/jsdoc-supported-types.html)
- [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)
- [eslint-plugin-jsdoc](https://github.com/gajus/eslint-plugin-jsdoc)
