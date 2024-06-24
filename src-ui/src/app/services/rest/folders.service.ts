import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AbstractNameFilterService } from './abstract-name-filter-service'; 
import { Folders, Document,Results } from 'src/app/data/folders'; 
import { environment } from 'src/environments/environment';

@Injectable({
  providedIn: 'root'
})
export class FoldersService extends AbstractNameFilterService<Folders> {
  constructor(http: HttpClient) {
    super(http, 'folders');

  }
  getResults(): Observable<{results: Results[]}> {
    return this.http.get<{results: Results[]}>(`${environment.apiBaseUrl}folders/`);
  }

  getFoldersAndDocuments(): Observable<{ folders: Folders[], documents: Document[] }> {
    return this.http.get<{ folders: Folders[], documents: Document[] }>(`${environment.apiBaseUrl}folders/folders_documents/`);
  }
}
