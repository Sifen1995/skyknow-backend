# Seeder and evaluation-page importer

This guide explains how the development seeder creates the baseline organization
and users, and how the evaluation-page importer turns Markdown files into
database records. The implementations are
[`scripts/seed/seed.py`](../scripts/seed/seed.py) and
[`scripts/helper/import_eval_pages.py`](../scripts/helper/import_eval_pages.py).

## What each script does

| Script | Creates or updates | Input |
|---|---|---|
| `scripts.seed.seed` | Languages, organization units, users, organization heads, and role assignments | `SEED_USER_PASSWORD` plus constants in `seed.py` |
| `scripts.helper.import_eval_pages` | Pages, audiences, language tracks, and initial versions | Markdown files in `eval/pages/` |

The seeder does not import content. The importer expects the seeder (or
equivalent records) to have created active author, reviewer, and publisher
accounts first.

## Prerequisites

1. Start the Docker Compose services with `make dev`.
2. Apply the database migrations with `make migrate`.
3. Seed the baseline records before importing pages.

The API container mounts the repository at `/app`, so both scripts can read the
repository files there. Run the importer from the repository root because its
input directory is the relative path `eval/pages`.

## Running the seeder

The Makefile runs the seeder inside the API container:

```sh
SEED_USER_PASSWORD='<your-development-password>' make seed
```

`SEED_USER_PASSWORD` is required. It must contain at least 8 characters and no
more than 72 UTF-8 bytes, which is the bcrypt input limit. The script hashes it
with bcrypt (12 rounds); it never stores the plaintext password.

### Records seeded

The values are declared in `LANGUAGES`, `ORG_UNITS`, `USERS`,
`PAGE_AUTHOR_ASSIGNMENT`, and `ROLE_ASSIGNMENTS` in `seed.py`.

- **Languages:** English (`en`), Amharic (`am`), and Oromo (`om`), each with
  display and native names and a sort order.
- **Organization units:** a tree rooted at `ceo`, with Customer Service,
  Back Office, Front Office, Digital Channels, Call Center, two supervisors,
  and Coach 1's team. Units are inserted in parent-before-child order. The
  database trigger builds each full `ltree` path from its parent and label.
- **Users:** eight example accounts attached to those units. Their stable
  `external_id` values use the `seed:` prefix.
- **Organization heads:** the script attempts to clear and assign heads by
  comparing each stored path to the unit's single label. Since nested units
  have full hierarchical paths, only the root `ceo` path matches; only the
  CEO head is reliably assigned, and existing nested head assignments are not
  cleared by this loop.
- **Roles:** Coach 1 is an author on the Coach 1 unit; two supervisors are
  reviewers on their respective units; and the Call Center manager is a
  publisher on the Call Center unit.

Roles are scoped to an organization unit. In the schema's hierarchy checks, a
role granted on an ancestor unit covers descendant units as well.

### Repeat runs and side effects

The seeder is designed to be repeatable for the same baseline data:

- Languages are inserted or updated by language code.
- Organization units are inserted or updated by their path. The path is derived
  by the database from the parent and label.
- Users are inserted or updated by email. A rerun sets them active, refreshes
  their name, organization, flags, and password hash, and restores the
  `seed:<key>` external ID.
- Role assignments are inserted only when the same user, role, and unit
  assignment does not already exist. Existing assignments are not removed.

Consequently, rerunning the seeder with a different password resets the seeded
users' passwords. The script does not delete records absent from its constants,
and does not deactivate unlisted users or organization units. All its database
work is inside one transaction; the engine is disposed in a `finally` block.

## Preparing Markdown pages

The importer reads only files matching `eval/pages/*.md` (not nested folders),
in sorted filename order. It reads YAML front matter and the remaining
Markdown body separately. Front matter is optional; the existing files without
front matter use the defaults below.

Example:

```markdown
---
title: Roaming activation
summary: Enable international roaming before a customer travels.
template: howto
language: en
visibility: restricted
customer_visible: false
published: true
---

Customers who travel abroad must have roaming enabled before leaving.

## Steps
1. Check that the SIM is registered.
2. Enable international roaming for the number.
```

| Metadata key | Default | Effect |
|---|---|---|
| `title` | Filename converted from underscores to title case | Version title |
| `summary` | Empty string | Version summary |
| `template` | `howto` | Page template: `howto`, `faq`, or `policy` |
| `language` | `en` | Language code for the page's language track; it must exist in `languages` |
| `visibility` | `restricted` | Page visibility: `restricted` or `all_staff` |
| `customer_visible` | `false` | Whether the page is customer-visible |
| `published` | `true` | `true` creates a published version; `false` creates a draft |

An unrecognized `template` falls back to `howto`; an unrecognized `visibility`
falls back to `restricted`. Other values are not fully validated by the
importer. In particular, use a real language code and YAML booleans (`true` or
`false`) for boolean metadata.

## Running the importer

There is no dedicated Makefile target for importing the Markdown pages. Run the
module from the repository root:

```sh
docker compose exec api python -m scripts.helper.import_eval_pages
```

For a local Python environment, the equivalent is:

```sh
python -m scripts.helper.import_eval_pages
```

The runtime settings load the database URL from the environment or `.env`.
The importer prints a message and exits without importing if `eval/pages` does
not exist. Otherwise, it prints the number of matching files and the name of
each file as it processes it.

## Importer workflow

1. **Find a page owner.** The importer chooses the first active user with an
   active organization unit and an `author` assignment, ordered by user email
   and then organization path. This user's assigned unit is the owner unit for
   every imported page in that run.
2. **Read each file.** The file's front matter supplies metadata; the Markdown
   after the front matter becomes the body.
3. **Create the page.** Each file creates a new `Page` with the selected
   owner's unit and user, the configured template and visibility, and the
   `customer_visible` flag.
4. **Create its audience.** A `PageAudience` row targets the owner unit and
   includes descendants.
5. **Create a language track.** A `PageLanguage` row associates the page with
   the configured language code.
6. **Create version 1.** The version title and summary come from metadata.
   `content` wraps the Markdown body in one paragraph block, while
   `content_text` stores the body as plain text for downstream processing.
   The version starts in `published` state by default, or `draft` when
   `published: false` is set.
7. **Fill publication workflow fields.** Published versions get a common
   current UTC timestamp for submission, approval, and publication. The
   importer looks up an active reviewer and publisher whose role scopes cover
   the page owner's unit, choosing the first user by email for each role. If
   either role cannot be found, import fails rather than publishing without
   workflow identities. Draft versions do not need those lookups.
8. **Commit.** The importer commits after all files have been processed. If an
   exception occurs before the commit, the session closes with its pending
   transaction uncommitted.

The importer does not create `VersionReview` rows; it records the approver and
timestamps on the version itself. It also does not chunk or index the content.

## Important operational caveats

- **Each run creates new pages.** The importer does not match filenames to
  existing pages, update prior versions, or skip previously imported files.
  Running it again imports another page for every Markdown file.
- **A published import needs the full role chain.** The selected author must
  have an active reviewer and publisher with assignments scoped to the owner
  unit or one of its ancestors. The default seed provides those roles for its
  Coach 1 owner unit.
- **The chosen author may change.** If the database has multiple eligible
  authors, the lowest email/unit ordering determines the owner. This also
  determines which reviewer and publisher scopes are required.
- **A bad language code can fail the database insert.** The language must
  already be present in `languages`; seed first or add the language through an
  appropriate database change.
- **The batch is committed at the end.** A failure in a later file prevents the
  script from reaching its final commit, so the run should not be treated as a
  partial-import workflow.
