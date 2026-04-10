import axios from "axios";
import { ALERTS_API_URL } from "../../../config/serviceUrls";

const ALERTS_API_BASE = ALERTS_API_URL;

export const getAlertHistory = async (params = {}) => {
  const response = await axios.get(ALERTS_API_BASE, { params });
  return response.data;
};

export const resolveAlertById = async (id) => {
  const response = await axios.patch(`${ALERTS_API_BASE}/${id}/resolve`);
  return response.data;
};
