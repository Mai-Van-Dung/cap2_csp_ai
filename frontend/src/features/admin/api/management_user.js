import axios from "axios";
import { USER_API_URL } from "../../../config/serviceUrls";

const API_URL = USER_API_URL;

// Lấy danh sách tất cả users
export const getAllUsers = async () => {
  const res = await axios.get(API_URL);
  return res.data;
};

// Xóa user theo id
export const deleteUser = async (id) => {
  const res = await axios.delete(`${API_URL}/${id}`);
  return res.data;
};

// Cập nhật trạng thái user (nếu cần sau này)
export const updateUserStatus = async (id, status) => {
  const res = await axios.put(`${API_URL}/${id}/status`, { status });
  return res.data;
};
