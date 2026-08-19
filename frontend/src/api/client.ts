import axios, { type AxiosError } from "axios";
import type { ApiErrorBody } from "@/types/api";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const apiClient = axios.create({
  baseURL,
  timeout: 30_000,
});

/** Human-readable message extracted from the backend's structured error envelope. */
export function apiErrorMessage(error: unknown): string {
  const axiosError = error as AxiosError<ApiErrorBody>;
  const body = axiosError?.response?.data;
  if (body && "error" in body) {
    return body.error.message;
  }
  if (axiosError?.message) {
    return axiosError.message;
  }
  return "An unexpected error occurred.";
}
