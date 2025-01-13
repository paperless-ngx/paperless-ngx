import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { DocumentNote } from 'src/app/data/document-note'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class DocumentNotesService extends AbstractPaperlessService<DocumentNote> {
  constructor(http: HttpClient) {
    super(http, 'documents')
  }

  getNotes(documentId: number): Observable<DocumentNote[]> {
    return this.http.get<DocumentNote[]>(
      this.getResourceUrl(documentId, 'notes')
    )
  }

  addNote(id: number, note: string): Observable<DocumentNote[]> {
    return this.http.post<DocumentNote[]>(this.getResourceUrl(id, 'notes'), {
      note: note,
    })
  }

  deleteNote(documentId: number, noteId: number): Observable<DocumentNote[]> {
    return this.http.delete<DocumentNote[]>(
      this.getResourceUrl(documentId, 'notes'),
      { params: new HttpParams({ fromString: `id=${noteId}` }) }
    )
  }
}
