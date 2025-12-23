# CMO Analyst Agent - Frontend

ChatGPT-like interface for CMO prospectus parsing and analysis.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: React Hooks
- **File Upload**: react-dropzone
- **API Client**: Fetch API

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Landing/Login page
│   └── chat/
│       └── page.tsx            # Main chat interface
├── components/
│   ├── Header.tsx              # App header with logout
│   ├── LoginButton.tsx         # Mock login button
│   ├── FileUpload.tsx          # PDF upload with drag-and-drop
│   ├── ChatInterface.tsx       # Main chat container
│   ├── MessageList.tsx         # Chat message history
│   └── MessageInput.tsx        # Message input box
├── lib/
│   ├── api.ts                  # Django API client functions
│   └── utils.ts                # Utility functions
├── types/
│   └── index.ts                # TypeScript type definitions
└── .env.local                  # Environment variables
```

## Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

The `.env.local` file is already created with:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Implementation Status

### ✅ Completed (Skeleton Code)

All components and API functions are created with:
- TypeScript type definitions
- Component structure and UI
- Detailed TODO comments with implementation steps
- Example code snippets in comments

### ⏳ To Implement (Your Task)

All files contain `TODO` markers with implementation instructions. Search for "TODO" to find them.

#### Priority 1: Backend API (Django)

1. **Authentication** (`backend/api/views.py`)
   - `login_view` - Mock authentication
   - `logout_view` - Clear session
   - `get_current_user` - Get user info

2. **Prospectus Management**
   - `upload_prospectus` - Handle file upload, trigger parsing agent
   - `get_prospectus_list` - List user's prospectuses
   - `get_prospectus_status` - Polling endpoint for parsing progress

3. **Chat Interface**
   - `send_chat_message` - Process messages (mock response for now)
   - `get_chat_history` - Return chat history

#### Priority 2: Frontend API Client (`lib/api.ts`)

Implement all API functions:
- `login()` - Call Django `/api/auth/login`
- `uploadProspectus()` - FormData POST to `/api/prospectus/upload`
- `sendChatMessage()` - POST to `/api/chat/message`
- `getChatHistory()` - GET from `/api/chat/history/{id}`
- etc.

#### Priority 3: Frontend Components

Implement TODO sections in:
- `components/LoginButton.tsx` - `handleLogin()`
- `components/FileUpload.tsx` - `onDrop()` with polling
- `components/ChatInterface.tsx` - `handleSendMessage()`, `loadChatHistory()`
- `components/MessageInput.tsx` - `handleSend()`, `handleKeyPress()`
- `components/Header.tsx` - `handleLogout()`

#### Priority 4: Utility Functions (`lib/utils.ts`)

Implement helper functions:
- `formatTimestamp()` - Format ISO dates
- `validatePdfFile()` - File validation
- etc.

## User Flow

### 1. Login (Mock)
1. User visits `/` (landing page)
2. Clicks "Login as testuser"
3. Frontend calls `login()`
4. Backend creates/returns testuser + token
5. Redirect to `/chat`

### 2. Upload Prospectus
1. User drags/drops PDF file
2. Frontend calls `uploadProspectus(file)`
3. Backend saves to DB, triggers `run_agent(prospectus)`
4. Frontend polls `getProspectusStatus()` every 2 seconds
5. Shows status: "Parsing Index..." → "Parsing Sections..." → "Completed"
6. Chat interface becomes active

### 3. Chat Interaction
1. User types message
2. Frontend calls `sendChatMessage(prospectusId, message)`
3. Backend processes with query agent (future)
4. Frontend displays user message + agent response
5. Auto-scrolls to latest message

## Key Design Decisions

1. **Skeleton Code Only** - All functions have TODOs, you implement
2. **Mock Authentication** - Simple testuser login, no real auth
3. **Polling for Status** - Not WebSockets (simpler for MVP)
4. **Single Prospectus** - One active prospectus per session
5. **Mobile Responsive** - Tailwind responsive classes included

## API Endpoints (Django Backend)

### Authentication
- `POST /api/auth/login` - Mock login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Current user

### Prospectus
- `POST /api/prospectus/upload` - Upload PDF
- `GET /api/prospectus/list` - List all
- `GET /api/prospectus/{id}/status` - Get parsing status

### Chat
- `POST /api/chat/message` - Send message
- `GET /api/chat/history/{id}` - Get history

## Development Tips

### Finding TODOs

```bash
# Search all TODOs in frontend
grep -r "TODO:" app/ components/ lib/

# Search all TODOs in backend API
grep -r "TODO:" ../../backend/api/
```

### Testing Frontend Without Backend

You can run the frontend even if backend isn't ready - buttons will work but API calls will fail. This lets you test UI/UX.

### Running Frontend and Backend Together

```bash
# Terminal 1: Backend
cd backend
python manage.py runserver

# Terminal 2: Frontend
cd frontend
npm run dev
```

## Next Steps After Implementation

1. Implement authentication (replace AllowAny with IsAuthenticated)
2. Add chat message persistence to database
3. Implement query agent for answering questions
4. Add file upload progress bar
5. Add error handling and user feedback
6. Add loading states
7. Add unit tests

## Troubleshooting

### CORS Issues

If you get CORS errors, check:
1. Backend `settings.py` has `corsheaders` in INSTALLED_APPS
2. `CORS_ALLOWED_ORIGINS` includes `http://localhost:3000`
3. `CorsMiddleware` is in MIDDLEWARE (should be near top)

### API Connection Issues

Check:
1. Backend is running on `http://localhost:8000`
2. `.env.local` has correct `NEXT_PUBLIC_API_URL`
3. Browser console for actual error messages
