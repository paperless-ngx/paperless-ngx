import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { MatchingModel } from './matching-model';

export interface Folders extends MatchingModel {
  id: number;
  owner_id: number;
  name: string;
  match: string;
  matching_algorithm: number;
  is_insensitive: boolean;
  parent_folder: number | null;
  path: string;
}
export interface Results {
  id: number;
  owner_id: number;
  name: string;
  match: string;
  matching_algorithm: number;
  is_insensitive: boolean;
  parent_folder: number | null;
  path: string;
  document_count: number;
  slug: string;
  user_can_change: boolean;
  is_shared_by_requester: boolean;
  child_folder_count: number;
  filesize: number;
  checksum: string;
  owner: number;
}

export interface SRC {
  documents: Document[];
  folders: Folders[];
  // Thêm các thuộc tính khác nếu có
}
export interface Document {
  id: number;
  owner_id: number;
  correspondent_id: number | null;
  storage_path_id: number | null;
  folder: number | null;
  warehouse_id: number | null;
  title: string;
  document_type_id: number | null;
  document: File;
  content: string;
  mime_type: string;
  checksum: string;
  archive_checksum: string;
  created: string;
  modified: string;
  storage_type: string;
  added: string;
  filename: string;
  archive_filename: string;
  original_filename: string;
  archive_serial_number: number | null;
}
