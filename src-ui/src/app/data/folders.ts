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
export interface Results{
  id: number;
  owner_id: number;
  name: string;
  match: string;
  matching_algorithm: number;
  is_insensitive: boolean;
  parent_folder: number | null;
  path: string;
}

export interface Document {
  id: number;
  owner_id: number;
  correspondent_id: number | null;
  storage_path_id: number | null;
  folder_id: number | null;
  warehouse_id: number | null;
  title: string;
  document_type_id: number | null;
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