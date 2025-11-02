# Memory-Break Orchestrator UI

Modern React + Vite + TypeScript + Tailwind CSS frontend for the Memory-Break Orchestrator.

## Features

- 🔐 SSO Authentication via APAC Atlas Guard Service
- 🎨 Modern, responsive UI with Tailwind CSS
- 📊 Real-time task monitoring with SSE
- 👥 Multi-tenant support with role-based access control
- 🚀 Fast development with Vite
- 📱 Mobile-friendly design

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **TanStack Query** - Data fetching and caching
- **Zustand** - State management
- **Axios** - HTTP client
- **Lucide React** - Icon library
- **Recharts** - Data visualization

## Getting Started

### Prerequisites

- Node.js 18+ and pnpm (or npm/yarn)

### Installation

```bash
# Install dependencies
pnpm install

# Start development server
pnpm dev
```

The dev server will start at `http://localhost:3000` with proxy to backend at `http://localhost:8000`.

### Environment Variables

Create a `.env.local` file (not tracked in git):

```env
VITE_SSO_SERVICE_URL=https://apac-atlas-guard-svc-264685500362.us-central1.run.app/v1
```

### Build for Production

```bash
# Build the app
pnpm build

# Preview production build
pnpm preview
```

The built files will be in the `dist/` directory.

## Project Structure

```
ui/
├── src/
│   ├── api/           # API client and endpoints
│   ├── components/    # Reusable UI components
│   ├── contexts/      # React contexts (Auth, etc.)
│   ├── hooks/         # Custom React hooks
│   ├── pages/         # Page components
│   ├── types/         # TypeScript type definitions
│   ├── utils/         # Utility functions
│   ├── App.tsx        # Main app component
│   ├── main.tsx       # Entry point
│   └── index.css      # Global styles with Tailwind
├── public/            # Static assets
├── index.html         # HTML template
├── vite.config.ts     # Vite configuration
├── tailwind.config.js # Tailwind configuration
├── tsconfig.json      # TypeScript configuration
└── package.json       # Dependencies and scripts
```

## Authentication Flow

1. User clicks "Sign in with Google" on login page
2. Redirected to SSO service (APAC Atlas Guard)
3. SSO handles Google OAuth authentication
4. User redirected back to `/auth/callback` with token and user data
5. Token stored in localStorage
6. All API requests include token in Authorization header
7. Backend runs behind SSO Gateway which validates token and injects user context

## Available Scripts

- `pnpm dev` - Start development server
- `pnpm build` - Build for production
- `pnpm preview` - Preview production build
- `pnpm lint` - Run ESLint
- `pnpm format` - Format code with Prettier

## Development

### Adding New Pages

1. Create page component in `src/pages/`
2. Add route in `src/App.tsx`
3. Wrap with `<ProtectedRoute>` if authentication required

### Adding New API Endpoints

1. Add types in `src/types/index.ts`
2. Add method in `src/api/client.ts`
3. Use with TanStack Query hooks in components

### Styling

- Use Tailwind utility classes
- Custom utilities defined in `src/index.css`
- Theme colors configured in `tailwind.config.js`

## Deployment

The UI can be deployed:

1. **With Backend** - Build and serve from FastAPI static files
2. **Separately** - Deploy to CDN/static hosting (Vercel, Netlify, etc.)

For deployment with backend:
```bash
pnpm build
# Copy dist/ contents to backend static directory
```

## License

Proprietary - Turing Platform Team

