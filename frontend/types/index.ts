/**
 * Type definitions for CMO Analyst Agent Frontend
 */

export interface User {
  id: string;
  username: string;
  email: string;
}

export interface Prospectus {
  prospectus_id: string;
  prospectus_name: string;
  prospectus_file: string;
  upload_date: string;
  parse_status: ParseStatus;
  created_by: string;
}

export type ParseStatus =
  | 'pending'
  | 'parsing_index'
  | 'parsing_sections'
  | 'classifying'
  | 'storing'
  | 'completed'
  | 'failed';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  prospectus_id?: string;
}

export interface ChatHistory {
  prospectus_id: string;
  messages: ChatMessage[];
}

export interface UploadResponse {
  prospectus_id: string;
  prospectus_name: string;
  status: string;
  message: string;
}

export interface ApiError {
  error: string;
  detail?: string;
  status?: number;
}
