# CAP2 CSP Frontend

React + Vite Frontend application with Tailwind CSS and React Router

## Tech Stack
- React 19.2.4
- Vite 8.0.0
- Tailwind CSS
- React Router
- Lucide React Icons

## Installation

```bash
npm install
```

## Development

```bash
npm run dev
```

- Runs on http://localhost:5173
- Hot Module Replacement (HMR) enabled
- Auto-reload on file changes

## Building

```bash
npm run build
```

Outputs optimized build to `dist/` folder

## Linting

```bash
npm run lint
```

Checks code quality with ESLint

## Preview

```bash
npm run preview
```

Preview the production build locally

## Project Structure

```
src/
├── pages/              # Page components
│   ├── LiveMonitor.jsx
│   ├── UserManagementPage.jsx
│   ├── ZoneConfig.jsx
│   └── PlaceholderPage.jsx
├── layouts/            # Layout components
│   └── MainLayout.jsx
├── assets/             # Static assets (images, etc.)
│   ├── hero.png
│   ├── react.svg
│   └── vite.svg
├── App.jsx             # Root component
├── App.css
├── main.jsx            # Entry point
└── index.css
```

## API Integration

To connect to the backend API:

```javascript
const response = await fetch('http://localhost:5000/api/users');
const data = await response.json();
```

Backend runs on `http://localhost:5000` (configured in .env if needed)

## Key Features

✅ Fast development with Vite  
✅ Responsive design with Tailwind CSS  
✅ Client-side routing with React Router  
✅ Icon library (Lucide React)  
✅ ESLint configuration for code quality  

## Notes

- Frontend CORS automatically configured to connect to backend
- Make sure backend is running on port 5000
- All API calls should go to `http://localhost:5000`

## Further Documentation

- [React Documentation](https://react.dev)
- [Vite Documentation](https://vitejs.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [React Router](https://reactrouter.com)
