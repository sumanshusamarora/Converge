# Converge Frontend

Next.js-based web UI for managing Converge tasks.

## Features

- **Task List View**: Browse all tasks with filtering by status
- **Task Detail View**: View complete task information and execution details
- **Task Creation**: Create new coordination tasks with custom parameters
- **HITL Resolution**: Resolve tasks requiring human-in-the-loop decisions
- **Artifact Viewer**: View summaries and download handoff pack files

## Development

Install dependencies:
```bash
npm install
```

Start development server:
```bash
npm run dev
```

Build for production:
```bash
npm run build
```

Start production server:
```bash
npm start
```

## Environment Variables

Create a `.env.local` file:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
```

## Project Structure

```
src/frontend/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout with navigation
│   ├── page.tsx           # Home page (redirects to /tasks)
│   ├── globals.css        # Global styles
│   └── tasks/             # Tasks feature
│       ├── page.tsx       # Task list page
│       └── [id]/          # Task detail page
│           └── page.tsx
├── lib/                   # Utilities
│   └── api.ts            # API client functions
├── package.json
├── tsconfig.json
└── next.config.js
```

## API Integration

The frontend communicates with the Converge API server. All API calls are defined in `lib/api.ts`:

- `fetchTasks()` - Get list of tasks
- `fetchTask(id)` - Get task details
- `createTask(request)` - Create new task
- `resolveTask(id, resolution)` - Resolve HITL task
- `cancelTask(id)` - Cancel task
- `fetchRunFiles(runId)` - List artifacts
- `fetchRunFile(runId, path)` - Download artifact

## Styling

The app uses minimal CSS without heavy component libraries. All styles are in `globals.css` for easy customization.

Key style classes:
- `.badge-*` - Status badges with color coding
- `.bg-*`, `.text-*` - Utility classes for colors
- `.px-*`, `.py-*`, `.m-*` - Spacing utilities

## Docker

Build and run with Docker:

```bash
docker build -t converge-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_BASE_URL=http://api:8080 converge-frontend
```

Or use docker-compose from the repository root.
