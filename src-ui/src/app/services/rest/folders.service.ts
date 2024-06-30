import { Injectable } from '@angular/core';
import { HttpClient , HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AbstractNameFilterService } from './abstract-name-filter-service';
import { Folders, Document, Results,SRC  } from 'src/app/data/folders';
import { environment } from 'src/environments/environment';

@Injectable({
  providedIn: 'root'
})
export class FoldersService extends AbstractNameFilterService<Document> {
  constructor(http: HttpClient) {
    super(http, 'documents');
  }

  getresults(id: number): Observable<SRC> {
    return this.http.get<SRC>(`${environment.apiBaseUrl}folders/${id}/folders_documents_by_id/`);
  }  
  getResults(): Observable<{ results: Results[] }> {
    return this.http.get<{ results: Results[] }>(`${environment.apiBaseUrl}folders/`);
  }  
  getFolders(id: number): Observable<{ folders: Folders[] }> {
    return this.http.get<{ folders: Folders[] }>(`${environment.apiBaseUrl}folders/${id}`);
  }
  getdocument(): Observable<{ thesis: Document[] }> {
    return this.http.get<{ thesis: Document[] }>(`${environment.apiBaseUrl}documents/`);
  }

  getFoldersAndDocuments(): Observable<{ folders: Folders[], documents: Document[] }> {
    return this.http.get<{ folders: Folders[], documents: Document[] }>(`${environment.apiBaseUrl}folders/folders_documents/`);
  }

  createFolder(folderData: any): Observable<Results> {
    return this.http.post<Results>(`${environment.apiBaseUrl}folders/`, folderData);
  }

  updateFolder(id: number, updateData: Partial<Results>): Observable<Results> {
    return this.http.patch<Results>(`${environment.apiBaseUrl}folders/${id}/`, updateData);
  }
  updateFile(id: number, updateData: Partial<Document>): Observable<Document> {
    return this.http.patch<Document>(`${environment.apiBaseUrl}documents/${id}/`, updateData);
  }
  deleteFolder(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiBaseUrl}folders/${id}/`);
  }
  deleteFileById(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiBaseUrl}documents/${id}/`);
  }
  bulkDeleteFolders(ids: number[]): Observable<void> {
    const payload = {
      objects: ids,
      object_type: 'folders',
      operation: 'delete'
    };
    return this.http.post<void>(`${environment.apiBaseUrl}bulk_edit_objects/`, payload);
  }
  fetchfolderandDocuments(folderId: number): Observable<{ documents: Document[], folders: Folders[] }> {
    return this.http.get<{ documents: Document[], folders: Folders[] }>(`${environment.apiBaseUrl}folders/${folderId}/folders_documents_by_id/`);
  }
  uploadDocument(formData: FormData): Observable<Document> {
    return this.http.post<Document>(`${environment.apiBaseUrl}documents/post_document/`, formData);
  }
  searchFolders(searchTerm: string): Observable<{ results: Results[] }> {
    const params = new HttpParams().set('name__icontains', searchTerm);
    return this.http.get<{ results: Results[] }>(`${environment.apiBaseUrl}folders/`, { params });
  }  
}
