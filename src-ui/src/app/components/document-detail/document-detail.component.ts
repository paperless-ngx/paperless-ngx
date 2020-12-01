import { Component, OnInit } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessDocumentMetadata } from 'src/app/data/paperless-document-metadata';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { DocumentService } from 'src/app/services/rest/document.service';
import { DeleteDialogComponent } from '../common/delete-dialog/delete-dialog.component';
import { CorrespondentEditDialogComponent } from '../manage/correspondent-list/correspondent-edit-dialog/correspondent-edit-dialog.component';
import { DocumentTypeEditDialogComponent } from '../manage/document-type-list/document-type-edit-dialog/document-type-edit-dialog.component';

@Component({
  selector: 'app-document-detail',
  templateUrl: './document-detail.component.html',
  styleUrls: ['./document-detail.component.scss']
})
export class DocumentDetailComponent implements OnInit {

  documentId: number
  document: PaperlessDocument
  metadata: PaperlessDocumentMetadata
  title: string
  previewUrl: string
  downloadUrl: string
  downloadOriginalUrl: string

  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]

  documentForm: FormGroup = new FormGroup({
    title: new FormControl(''),
    content: new FormControl(''),
    created: new FormControl(),
    correspondent_id: new FormControl(),
    document_type_id: new FormControl(),
    archive_serial_number: new FormControl(),
    tags_id: new FormControl([])
  })

  constructor(
    private documentsService: DocumentService, 
    private route: ActivatedRoute,
    private correspondentService: CorrespondentService,
    private documentTypeService: DocumentTypeService,
    private router: Router,
    private modalService: NgbModal,
    private openDocumentService: OpenDocumentsService,
    private documentListViewService: DocumentListViewService) { }

  ngOnInit(): void {
    this.documentForm.valueChanges.subscribe(wow => {
      Object.assign(this.document, this.documentForm.value)
    })

    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)

    this.route.paramMap.subscribe(paramMap => {
      this.documentId = +paramMap.get('id')
      this.previewUrl = this.documentsService.getPreviewUrl(this.documentId)
      this.downloadUrl = this.documentsService.getDownloadUrl(this.documentId)
      this.downloadOriginalUrl = this.documentsService.getDownloadUrl(this.documentId, true)
      if (this.openDocumentService.getOpenDocument(this.documentId)) {
        this.updateComponent(this.openDocumentService.getOpenDocument(this.documentId))
      } else {
        this.documentsService.get(this.documentId).subscribe(doc => {
          this.openDocumentService.openDocument(doc)
          this.updateComponent(doc)
        }, error => {this.router.navigate(['404'])})
      }
    })

  }

  updateComponent(doc: PaperlessDocument) {
    this.document = doc
    this.documentsService.getMetadata(doc.id).subscribe(result => {
      this.metadata = result
    })
    this.title = doc.title
    this.documentForm.patchValue(doc)
  }

  createDocumentType() {
    var modal = this.modalService.open(DocumentTypeEditDialogComponent, {backdrop: 'static'})
    modal.componentInstance.dialogMode = 'create'
    modal.componentInstance.success.subscribe(newDocumentType => {
      this.documentTypeService.listAll().subscribe(documentTypes => {
        this.documentTypes = documentTypes.results
        this.documentForm.get('document_type_id').setValue(newDocumentType.id)
      })
    })
  }

  createCorrespondent() {
    var modal = this.modalService.open(CorrespondentEditDialogComponent, {backdrop: 'static'})
    modal.componentInstance.dialogMode = 'create'
    modal.componentInstance.success.subscribe(newCorrespondent => {
      this.correspondentService.listAll().subscribe(correspondents => {
        this.correspondents = correspondents.results
        this.documentForm.get('correspondent_id').setValue(newCorrespondent.id)
      })
    })
  }

  discard() {
    this.documentsService.get(this.documentId).subscribe(doc => {
      Object.assign(this.document, doc)
      this.title = doc.title
      this.documentForm.patchValue(doc)
    }, error => {this.router.navigate(['404'])})
  }

  save() {    
    this.documentsService.update(this.document).subscribe(result => {
      this.close()
    })
  }

  saveEditNext() {
    this.documentsService.update(this.document).subscribe(result => {
      this.documentListViewService.getNext(this.document.id).subscribe(nextDocId => {
        if (nextDocId) {
          this.openDocumentService.closeDocument(this.document)
          this.router.navigate(['documents', nextDocId])
        }
      })
    })
  }

  close() {
    this.openDocumentService.closeDocument(this.document)
    if (this.documentListViewService.savedViewId) {
      this.router.navigate(['view', this.documentListViewService.savedViewId])
    } else {
      this.router.navigate(['documents'])
    }
  }

  delete() {
    let modal = this.modalService.open(DeleteDialogComponent, {backdrop: 'static'})
    modal.componentInstance.message = `Do you really want to delete document '${this.document.title}'?`
    modal.componentInstance.message2 = `The files for this document will be deleted permanently. This operation cannot be undone.`
    modal.componentInstance.deleteClicked.subscribe(() => {
      this.documentsService.delete(this.document).subscribe(() => {
        modal.close()  
        this.close()
      })
    })

  }

  hasNext() {
    return this.documentListViewService.hasNext(this.documentId)
  }
}
