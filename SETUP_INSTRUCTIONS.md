# 🚀 Project Setup Instructions

## Project Structure Overview

Dự án của bạn được tổ chức theo cấu trúc **Backend-Frontend** chuẩn:

```
cap2_csp_ai/
├── backend/           # Node.js + Express API
├── frontend/          # React + Vite Giao Diện
└── README.md
```

---

## ⚙️ Cấu Hình MySQL

### Bước 1: Cập nhật Backend Database Credentials

Mở file `backend/.env`:

```bash
# Mở backend/.env
# Cập nhật thông tin MySQL của bạn
```

**Nội dung cần cấu hình:**
```env
DB_HOST=localhost          # Địa chỉ MySQL server
DB_USER=root              # Username MySQL của bạn
DB_PASSWORD=your_password # Password MySQL của bạn (nếu có)
DB_NAME=cap2_csp_db       # Tên database
DB_PORT=3306              # Port MySQL (mặc định)

PORT=5000                 # Backend server port
NODE_ENV=development      # Environment
CORS_ORIGIN=http://localhost:5173  # Frontend URL
```

---

## 📦 Cài Đặt Dependencies

### Backend Setup

```bash
cd backend
npm install
```

**Dependencies được cài:**
- express (API framework)
- mysql2 (MySQL client)
- cors (Cross-origin support)
- dotenv (Environment variables)
- nodemon (Auto-restart in development)

### Frontend Setup

```bash
cd frontend
npm install
```

**Dependencies được cài:**
- react (UI library)
- vite (Build tool)
- tailwindcss (CSS framework)
- react-router-dom (Routing)
- lucide-react (Icons)

---

## 🏃 Chạy Project

### Option 1: Chạy Riêng (Recommended)

**Terminal 1 - Backend:**
```bash
cd backend
npm run dev
```
✅ Backend chạy tại: `http://localhost:5000`

Khi thấy dòng: `✅ MySQL connected successfully` - Database đã kết nối!

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```
✅ Frontend chạy tại: `http://localhost:5173`

### Option 2: Chạy Cùng Lúc (Quick Start)

Tạo file `start.sh` (Linux/Mac) hoặc `start.bat` (Windows) ở root folder:

**Windows (start.bat):**
```batch
@echo off
start cmd /k "cd backend && npm run dev"
start cmd /k "cd frontend && npm run dev"
```

**Mac/Linux (start.sh):**
```bash
#!/bin/bash
cd backend && npm run dev &
cd ../frontend && npm run dev
```

---

## 🔧 MySQL Connection Layer

Lớp kết nối MySQL đã được chuẩn bị sẵn tại:
```
backend/src/config/database.js
```

### Cách Sử Dụng

**Trong Controllers hoặc Routes:**

```javascript
import { pool } from '../config/database.js';

// Lấy connection từ pool
const connection = await pool.getConnection();

// Thực thi query
const [users] = await connection.query('SELECT * FROM users WHERE id = ?', [userId]);

// Trả lại connection vào pool
connection.release();

// Gửi response
res.json({ success: true, data: users });
```

### Ví Dụ Sử Dụng

Đã có sẵn ví dụ tại:
- `backend/src/controllers/userController.js` - CRUD operations
- `backend/src/routes/userRoutes.js` - Route definitions
- `backend/src/middleware/authMiddleware.js` - Middleware examples

---

## 🌐 Frontend ↔ Backend Communication

### Gọi API từ React

```javascript
// Fetch từ Frontend
const response = await fetch('http://localhost:5000/api/users');
const data = await response.json();
console.log(data);
```

### POST Request

```javascript
const response = await fetch('http://localhost:5000/api/users', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'John Doe',
    email: 'john@example.com'
  })
});
const data = await response.json();
```

---

## ✅ Testing

### Health Check Backend

```bash
curl http://localhost:5000/api/health
```

**Expected Response:**
```json
{
  "status": "OK",
  "timestamp": "2024-03-23T10:30:00.000Z"
}
```

### Example API Endpoints

```bash
# Get all users
curl http://localhost:5000/api/users

# Get user by ID
curl http://localhost:5000/api/users/1

# Create user
curl -X POST http://localhost:5000/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"John","email":"john@example.com"}'
```

---

## 📝 Thêm Routes Mới

### 1. Tạo Controller
File: `backend/src/controllers/productController.js`

```javascript
import { pool } from '../config/database.js';

export const getProducts = async (req, res) => {
  try {
    const connection = await pool.getConnection();
    const [products] = await connection.query('SELECT * FROM products');
    connection.release();
    
    res.json({ success: true, data: products });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};
```

### 2. Tạo Route
File: `backend/src/routes/productRoutes.js`

```javascript
import express from 'express';
import { getProducts } from '../controllers/productController.js';

const router = express.Router();
router.get('/', getProducts);

export default router;
```

### 3. Thêm vào app.js

```javascript
import productRoutes from './routes/productRoutes.js';
app.use('/api/products', productRoutes);
```

---

## 🐛 Troubleshooting

| Lỗi | Nguyên Nhân | Giải Pháp |
|-----|-----------|----------|
| ❌ MySQL connection failed | MySQL không chạy hoặc DB credentials sai | Kiểm tra MySQL server, cập nhật .env |
| ❌ Port 5000 đang sử dụng | Ứng dụng khác dùng port | Thay PORT trong backend/.env |
| ❌ Port 5173 đang sử dụng | Ứng dụng khác dùng port | Chạy `npm run dev -- --port 3000` |
| ❌ CORS error | Frontend URL không khớp | Kiểm tra CORS_ORIGIN trong backend/.env |
| ❌ Module not found | Dependencies chưa cài | Chạy `npm install` trong folder tương ứng |

---

## 🚀 Production Build

### Frontend Build

```bash
cd frontend
npm run build
```

Output: `frontend/dist/` - Deploy folder này lên web server

### Backend Production

```bash
cd backend
npm start
```

Hoặc dùng process manager:
```bash
npm install -g pm2
cd backend
pm2 start src/app.js --name "csp-backend"
```

---

## 📋 Checklist

- [ ] Cấu hình MySQL credentials trong `backend/.env`
- [ ] Chạy `npm install` trong cả `backend/` và `frontend/`
- [ ] Kiểm tra MySQL server đang chạy
- [ ] Chạy backend: `npm run dev` (port 5000)
- [ ] Chạy frontend: `npm run dev` (port 5173)
- [ ] Test health check: `curl http://localhost:5000/api/health`

---

## 📚 Tài Liệu Tham Khảo

- [Express.js Docs](https://expressjs.com/)
- [React Documentation](https://react.dev/)
- [Vite Guide](https://vitejs.dev/)
- [MySQL2 Documentation](https://github.com/sidorares/node-mysql2)
- [Tailwind CSS](https://tailwindcss.com/)
- [React Router](https://reactrouter.com/)

---

## ✨ Project Ready!

Bây giờ bạn đã có một cấu trúc dự án chuyên nghiệp, sẵn sàng để phát triển! 🎉

**Happy coding!** 💻
