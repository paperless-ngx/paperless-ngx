import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { Observable } from 'rxjs'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { Folder } from 'src/app/data/folder'
import { FolderDocument } from 'src/app/data/folder-document'

@Injectable({
  providedIn: 'root',
})
export class FolderService extends AbstractNameFilterService<Folder> {
  constructor(http: HttpClient) {
    super(http, 'folders')
  }
  getFolderDocument(id: number): Observable<FolderDocument> {
    return this.http.get<FolderDocument>(this.getResourceUrl(id, 'folders_documents_by_id'))
  }
  
  getFolderDocumentById(id: number): Observable<FolderDocument> {
    return this.http.get<FolderDocument>(this.getResourceUrl(id, 'folders_documents_by_id'))
  }
  
}
