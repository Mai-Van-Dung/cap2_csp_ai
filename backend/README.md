# CAP2 CSP Backend (Node.js + Express)

Backend API for CAP2 CSP AI Project with MySQL Database

## Tech Stack
- Node.js + Express.js
- MySQL Database
- Environment Variables (.env)
- CORS Support

## Installation

### Prerequisites
- Node.js (v16 or higher)
- MySQL Server running
- npm

### Steps

1. **Install dependencies**
```bash
npm install
```

2. **Configure Database**
   - Open `.env` file
   - Update MySQL connection details:
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=cap2_csp_db
DB_PORT=3306
```

3. **Start Development Server**
```bash
npm run dev
```

4. **Start Production Server**
```bash
npm start
```

The server will run on `http://localhost:5000`

## API Health Check

```bash
curl http://localhost:5000/api/health
```

## Project Structure

```
backend/
├── src/
│   ├── config/
│   │   └── database.js      # MySQL connection pool
│   ├── routes/              # API routes
│   │   └── userRoutes.js    # Example routes
│   ├── controllers/         # Business logic
│   │   └── userController.js # Example controller
│   ├── models/              # Database models
│   ├── middleware/          # Express middleware
│   │   └── authMiddleware.js # Example middleware
│   └── app.js               # Express app entry point
├── package.json
├── .env                     # Environment variables (not in git)
├── .env.example             # Example .env file
├── .gitignore
└── README.md
```

## Database Connection

MySQL connection is configured in `src/config/database.js` using the `mysql2/promise` library with connection pooling.

### Using Database in Routes/Controllers

```javascript
import { pool } from '../config/database.js';

// Getting a connection from the pool
const connection = await pool.getConnection();

// Execute query
const [rows] = await connection.query('SELECT * FROM users');

// Release connection back to pool
connection.release();
```

## Adding Routes

1. Create controller in `src/controllers/`
2. Create route in `src/routes/`
3. Import and use in `src/app.js`:

```javascript
import userRoutes from './routes/userRoutes.js';
app.use('/api/users', userRoutes);
```

## Environment Variables

Copy `.env.example` to `.env` and configure:
- **DB_HOST**: MySQL server host
- **DB_USER**: MySQL username
- **DB_PASSWORD**: MySQL password
- **DB_NAME**: Database name
- **DB_PORT**: MySQL port (default: 3306)
- **PORT**: Server port (default: 5000)
- **NODE_ENV**: Environment (development/production)
- **CORS_ORIGIN**: Frontend URL

## Example API Endpoints

After setup, you can test with:

```bash
# Health check
curl http://localhost:5000/api/health

# Get all users
curl http://localhost:5000/api/users

# Get user by ID
curl http://localhost:5000/api/users/1

# Create user
curl -X POST http://localhost:5000/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"John","email":"john@example.com"}'
```

## Development

- Use `npm run dev` for development with auto-restart (nodemon)
- Use `npm start` for production mode

## Notes

- Don't commit `.env` file to git
- Database credentials should be kept secret
- Ensure MySQL server is running before starting backend
- Use connection pooling to handle multiple concurrent requests
