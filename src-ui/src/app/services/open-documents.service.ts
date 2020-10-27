import { Injectable } from '@angular/core';
import { Observable, Subject } from 'rxjs';
import { PaperlessDocument } from '../data/paperless-document';

@Injectable({
  providedIn: 'root'
})
export class OpenDocumentsService {

  constructor() { }

  private openDocuments: PaperlessDocument[] = []

  private openDocumentsSubject: Subject<PaperlessDocument[]> = new Subject()

  getOpenDocuments(): Observable<PaperlessDocument[]> {
    return this.openDocumentsSubject
  }

  openDocument(doc: PaperlessDocument) {
    if (this.openDocuments.find(d => d.id == doc.id) == null) {
      this.openDocuments.push(doc)
      this.openDocumentsSubject.next(this.openDocuments)
    }
  }

  closeDocument(doc: PaperlessDocument) {
    let index = this.openDocuments.findIndex(d => d.id == doc.id)
    if (index > -1) {
      this.openDocuments.splice(index, 1)
      this.openDocumentsSubject.next(this.openDocuments)
    }
  }

}
