import { Injectable } from '@angular/core';
import { PaperlessDocument } from '../data/paperless-document';
import { OPEN_DOCUMENT_SERVICE } from '../data/storage-keys';
import { DocumentService } from './rest/document.service';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ConfirmDialogComponent } from 'src/app/components/common/confirm-dialog/confirm-dialog.component';
import { Observable, Subject, of } from 'rxjs';
import { take } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class OpenDocumentsService {

  private MAX_OPEN_DOCUMENTS = 5

  constructor(private documentService: DocumentService, private modalService: NgbModal) {
    if (sessionStorage.getItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS)) {
      try {
        this.openDocuments = JSON.parse(sessionStorage.getItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS))
      } catch (e) {
        sessionStorage.removeItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS)
        this.openDocuments = []
      }
    }
  }

  private openDocuments: PaperlessDocument[] = []
  private dirtyDocuments: Set<number> = new Set<number>()

  refreshDocument(id: number) {
    let index = this.openDocuments.findIndex(doc => doc.id == id)
    if (index > -1) {
      this.documentService.get(id).subscribe(doc => {
        this.openDocuments[index] = doc
      }, error => {
        this.openDocuments.splice(index, 1)
        this.save()
      })
    }
  }

  getOpenDocuments(): PaperlessDocument[] {
    return this.openDocuments
  }

  getOpenDocument(id: number): PaperlessDocument {
    return this.openDocuments.find(d => d.id == id)
  }

  openDocument(doc: PaperlessDocument) {
    if (this.openDocuments.find(d => d.id == doc.id) == null) {
      this.openDocuments.unshift(doc)
      if (this.openDocuments.length > this.MAX_OPEN_DOCUMENTS) {
        this.openDocuments.pop()
      }
      this.save()
    }
  }

  setDirty(documentId: number, dirty: boolean) {
    if (dirty) this.dirtyDocuments.add(documentId)
    else this.dirtyDocuments.delete(documentId)
  }

  closeDocument(doc: PaperlessDocument) {
    let index = this.openDocuments.findIndex(d => d.id == doc.id)
    if (index > -1) {
      this.openDocuments.splice(index, 1)
      this.save()
    }
  }

  closeAll(): Observable<boolean> {
    if (this.dirtyDocuments.size) {
      let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
      modal.componentInstance.title = $localize`Unsaved Changes`
      modal.componentInstance.messageBold = $localize`You have unsaved changes.`
      modal.componentInstance.message = $localize`Are you sure you want to close all documents?`
      modal.componentInstance.btnClass = "btn-warning"
      modal.componentInstance.btnCaption = $localize`Close documents`
      modal.componentInstance.confirmClicked.pipe(take(1)).subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        modal.close()
        this.openDocuments.splice(0, this.openDocuments.length)
        this.save()
      })
      const subject = new Subject<boolean>()
      modal.componentInstance.subject = subject
      return subject.asObservable()
    } else {
      this.openDocuments.splice(0, this.openDocuments.length)
      this.save()
      return of(true)
    }
  }

  save() {
    sessionStorage.setItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS, JSON.stringify(this.openDocuments))
  }

}
