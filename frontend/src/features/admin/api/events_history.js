import axios from "axios";

const ALERTS_API_BASE =
  import.meta.env.VITE_ALERTS_API_URL || "http://localhost:5000/api/alerts";

export const getAlertHistory = async (params = {}) => {
  const response = await axios.get(ALERTS_API_BASE, { params });
  return response.data;
};

export const resolveAlertById = async (id) => {
  const response = await axios.patch(`${ALERTS_API_BASE}/${id}/resolve`);
  return response.data;
};
