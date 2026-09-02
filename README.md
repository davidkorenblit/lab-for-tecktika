# lab-for-tecktika

AI Agent Chat — a React + TypeScript front end for querying a SharePoint PDF
library in natural language and managing the files in it.

## Running it

```bash
npm install
cp .env.example .env      # point VITE_DEV_API_PROXY at your backend
npm run dev               # http://localhost:5173
npm run build             # type-check + production bundle into dist/
npm run lint
```

In dev, Vite proxies both `/api` and `/.auth` to `VITE_DEV_API_PROXY`. With no
Easy Auth host available locally, set `VITE_AUTH_DEV_BYPASS=true` to skip the
sign-in gate.

## How the requirements are met

**Everything goes through the conversation.** There is no file dashboard. A PDF
is an attachment on a message, not an upload action: picking one starts pushing
the bytes to storage immediately, so the send stays instant, but nothing happens
to the library until the message is sent and the agent has decided what the file
is for. Add, replace, update and delete are all the agent acting on a turn, and
the client never invents an action the agent did not propose.

**Auth (`src/services/auth.ts`, `src/services/apiClient.ts`).** The session is
read once from `/.auth/me` and cached, with concurrent callers de-duplicated so
first paint issues a single request. Both response shapes are handled: the
Static Web Apps `{ clientPrincipal }` envelope and the App Service token-store
array. `authorizedFetch` is the single choke point every API call goes through —
it attaches `Authorization: Bearer <token>`, sends the Easy Auth cookie, and on a
401 or 403 refreshes the session and replays the request once. If the replay is
also rejected the user is sent to `/.auth/login/aad` rather than shown a status
code. The exception is a 403 for someone who *is* signed in: that is a
permissions problem, and redirecting to a provider that will happily sign them in
again would loop, so it surfaces as an error.

> **Caveat worth reading before the code.** SWA's `/.auth/me` does not expose a
> raw token by default, so `token` is null and requests authenticate with the
> Easy Auth cookie alone — the `Authorization` header is only attached when a
> token actually exists. To get a real bearer token, have the SWA config request
> `id_token`/`access_token` as a claim, or mint an app token in the API. No
> client change is needed either way.

**Streaming chat (`src/lib/sse.ts`, `src/services/chat.ts`, `src/hooks/useChat.ts`).**
`EventSource` cannot POST or set headers, so the stream is read from a `fetch`
POST body through a hand-rolled SSE parser that handles split chunks, CRLF,
keep-alive comments, multi-line `data:` and an unterminated tail. History loads
on mount into the React Query cache and streamed tokens patch that same cache, so
both paths converge on one message list. Deltas are buffered and flushed once per
animation frame rather than re-rendering per token. A backend that answers a
stream request with plain JSON still works.

**Two conversation identities, deliberately separate.** `threadId` is minted on
the client, is stable for the life of a conversation, and is the only thing the
React Query key is built from. `conversationId` is assigned by the backend and
travels in request bodies. Keying the cache on the server id meant the key
changed the moment that id arrived, abandoning the cache entry the stream was
writing into. The stream now reports the conversation id on its `start` and
`done` frames. "New conversation" mints a fresh `threadId` and skips the history
load — asking `/api/chat/history` without an id returns the most recent
conversation, which is the one being left behind — so the first message is what
brings the server-side conversation into existence.

**A reply interrupted by a refresh is not lost.** The in-flight answer is written
to `localStorage` as it streams (at most once a second) and spliced back into the
transcript on the next load, marked as interrupted, if the server does not have
it.

**Non-blocking jobs (`src/providers/JobsProvider.tsx`).** A `jobId` is written to
`localStorage` the moment it appears. Polling lives in a provider mounted above
the app, not in the chat, which is what keeps the composer live throughout. It
backs off from 2s toward 15s, stops on a terminal state, continues while the tab
is in the background, and mirrors across tabs via the `storage` event. Each poll
result is folded back into the persisted record, so a refresh mid-job renders the
last known state immediately and resumes polling.

**Explicit confirmations (`ConfirmationCard.tsx`, `ConfirmationDialog.tsx`).**
Non-destructive asks resolve inline; anything destructive opens a modal. Both
list every affected file by name — never "this file" or a count — and every
destructive action requires typing a file name before the button unlocks, bulk
operations included. An action whose type the client does not recognise is
treated as destructive. Requests queue into a single modal slot, so two
`aria-modal` dialogs can never stack and fight over the focus trap.

**Large uploads (`src/services/blobUpload.ts`, `src/hooks/useFileUpload.ts`).**
Two steps: ask the API for a SAS URL, then PUT the bytes straight to storage, so
50MB+ files never pass through the API. Files over 32MB are staged as 8MB blocks
uploaded three at a time with per-block retry and committed with a block list — a
drop at 48/50MB retries one block, not the file. Progress comes from XHR upload
events. No `Authorization` header is ever sent to storage; the SAS token is the
credential.

**Citations (`CitationList.tsx`).** Numbered chips under the answer, expanding to
the matched snippet and a SharePoint deep link. Relevance is shown relative to
the best source in that answer: `@search.score` is an unbounded relevance score
rather than a probability, so rendering it as `score * 100` turned a score of
12.4 into "1240% match".

**Markdown.** Assistant replies render through `react-markdown` with GFM,
memoised so a stream frame re-parses only the message that is growing. Raw HTML
is off — `rehype-raw` is deliberately not installed, so markup inside a retrieved
document is text, not markup — and an element allowlist backs that up.

## Layout

```
src/
  services/      auth, apiClient (bearer interceptor), chat (SSE), files, jobs, blobUpload
  hooks/         useAuth, useChat, useFileUpload, useConfirmationQueue
  providers/     JobsProvider — persisted job registry + polling
  lib/           sse parser, localStorage helpers, queryClient, formatters
  components/    ChatWindow, MessageList/Bubble/Content, CitationList, Composer,
                 ConfirmationCard/Dialog, JobTray, AppHeader, ErrorBoundary
  types.ts       shared contracts
```

## Backend contract

Where the brief left the shape open, the service layer normalises tolerantly
rather than assuming one:

- **SSE frames** are accepted as typed events (`event: start|delta|citations|
  confirmation|job|error|done`) or untyped `data:` JSON carrying a `type` field;
  `[DONE]` ends the stream. Token deltas are read from `delta`, `text` or
  `content`. `start` and `done` may carry `conversationId`.
- **Job status** accepts `state` or `status`, and maps the usual vocabularies
  (`completed`/`success`/`done` → `succeeded`, `in_progress`/`processing` →
  `running`, …). `progress` may be 0-1 or 0-100.
- **Citations** accept `fileName`/`filename`/`name`, `url`/`webUrl`/`link`,
  `snippet`/`excerpt`/`content`.

Two things to confirm against the real API:

1. `POST /api/chat/message` accepts an `attachments` array of
   `{ fileId, fileName, size, blobPath }` for files already staged in storage,
   and `GET /api/chat/history` echoes them back on the message.
2. Something has to tell the backend the bytes have landed so it can index the
   PDF. This client assumes the agent does it, having been handed the `fileId` on
   the message. If the backend would rather have an explicit call, add a
   `finalize` step in `src/hooks/useFileUpload.ts`; nothing else moves.
   `POST /api/files/confirm-action` is never sent a synthesised
   `confirmationId` — only one the backend issued on a `confirmation` frame.

## Verification

`npm run build` (type-check + bundle) and `npm run lint` both pass clean. The
component tree was rendered once through `react-dom/server` to check that
markdown, attachment chips, citation chips and the confirmation dialog produce
what they should, including that a bulk delete demands a typed file name and that
an unbounded relevance score is not rendered as a percentage.

There is no automated test suite, and the UI has not been exercised against a
live backend.
