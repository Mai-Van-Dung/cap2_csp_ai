# CAP2 CSP AI Project

Professional project structure with separated **Frontend** (React) and **Backend** (Node.js) with MySQL Database.

## Project Structure

```
cap2_csp_ai/
├── frontend/                 # React Frontend (Vite)
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── layouts/         # Layout components
│   │   ├── assets/          # Static assets
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── main.jsx
│   │   └── index.css
│   ├── public/              # Public assets
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── eslint.config.js
│   └── README.md
│
├── backend/                  # Node.js Backend (Express)
│   ├── src/
│   │   ├── config/
│   │   │   └── database.js  # MySQL connection pool ⭐
│   │   ├── routes/          # API routes
│   │   │   └── userRoutes.js
│   │   ├── controllers/     # Business logic
│   │   │   └── userController.js
│   │   ├── models/          # Database models
│   │   ├── middleware/      # Express middleware
│   │   │   └── authMiddleware.js
│   │   └── app.js
│   ├── package.json
│   ├── .env                 # Environment variables (add your MySQL config)
│   ├── .env.example
│   ├── .gitignore
│   └── README.md
│
└── node_modules/
```

## Quick Start

### 1️⃣ Backend Setup

```bash
cd backend

# Install dependencies
npm install

# Configure MySQL credentials in .env file
# DB_HOST=localhost
# DB_USER=root
# DB_PASSWORD=your_password
# DB_NAME=cap2_csp_db

# Start development server
npm run dev
# Server runs at: http://localhost:5000
```

### 2️⃣ Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
# Frontend runs at: http://localhost:5173
```

## Key Features

✅ **Separated Frontend & Backend**  
✅ **React with Vite** - Fast development experience  
✅ **Node.js Express API** - RESTful backend  
✅ **MySQL Database** - With connection pooling  
✅ **Tailwind CSS** - Utility-first CSS framework  
✅ **React Router** - Client-side routing  
✅ **CORS Support** - Frontend-Backend communication  
✅ **Environment Configuration** - .env support  

## Database Connection

The MySQL connection layer is ready in `backend/src/config/database.js`. It uses:
- Connection pooling for efficient resource management
- Async/await pattern with `mysql2/promise`
- Auto-test connection on server startup

### Quick Database Setup

1. **Update backend/.env with your MySQL credentials:**
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=cap2_csp_db
DB_PORT=3306
```

2. **Using the database in your code:**
```javascript
import { pool } from '../config/database.js';

const connection = await pool.getConnection();
const [users] = await connection.query('SELECT * FROM users');
connection.release();
```

## API Testing

### Health Check
```bash
curl http://localhost:5000/api/health
# Response: { "status": "OK", "timestamp": "..." }
```

### Frontend API Calls
```javascript
const response = await fetch('http://localhost:5000/api/users');
const data = await response.json();
console.log(data);
```

## Development Workflow

1. **Terminal 1 - Backend:**
   ```bash
   cd backend && npm run dev
   ```
   Auto-restarts with nodemon on file changes

2. **Terminal 2 - Frontend:**
   ```bash
   cd frontend && npm run dev
   ```
   Hot Module Replacement (HMR) enabled by default

## Production Build

### Frontend
```bash
cd frontend
npm run build
# Output in: frontend/dist/
```

### Backend
```bash
cd backend
npm start
```

## Adding New Features

### Adding a New API Route

1. **Create controller** (`backend/src/controllers/productController.js`):
```javascript
import { pool } from '../config/database.js';

export const getProducts = async (req, res) => {
  const connection = await pool.getConnection();
  const [products] = await connection.query('SELECT * FROM products');
  connection.release();
  res.json({ success: true, data: products });
};
```

2. **Create route** (`backend/src/routes/productRoutes.js`):
```javascript
import express from 'express';
import { getProducts } from '../controllers/productController.js';

const router = express.Router();
router.get('/', getProducts);

export default router;
```

3. **Import in app.js**:
```javascript
import productRoutes from './routes/productRoutes.js';
app.use('/api/products', productRoutes);
```

## Important Notes

📌 **Don't commit credentials** - `.env` should NOT be in git  
📌 **Database required** - Ensure MySQL server is running  
📌 **CORS enabled** - Frontend (localhost:5173) ↔ Backend (localhost:5000)  
📌 **Connection pooling** - Handles multiple concurrent requests efficiently  

## Environment Variables

### Frontend
No additional env variables needed (uses default localhost:5000 for API)

### Backend
Create `.env` from `.env.example`:
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=
DB_NAME=cap2_csp_db
DB_PORT=3306
PORT=5000
NODE_ENV=development
CORS_ORIGIN=http://localhost:5173
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| MySQL connection failed | Check MySQL is running, verify credentials in .env |
| Port 5000 already in use | Change PORT in backend/.env |
| Port 5173 already in use | Run `npm run dev -- --port 3000` in frontend |
| CORS errors | Verify CORS_ORIGIN in backend/.env matches frontend URL |
| nodemon not found | Run `npm install` in backend folder |

## References

- [Express.js Documentation](https://expressjs.com/)
- [React Documentation](https://react.dev/)
- [Vite Guide](https://vitejs.dev/)
- [MySQL2 Documentation](https://github.com/sidorares/node-mysql2)
- [Tailwind CSS](https://tailwindcss.com/)

## License

ISC
