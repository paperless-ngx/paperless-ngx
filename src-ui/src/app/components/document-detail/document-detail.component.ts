import { DatePipe, formatDate } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { DocumentService } from 'src/app/services/rest/document.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { DeleteDialogComponent } from '../common/delete-dialog/delete-dialog.component';
import { CorrespondentEditDialogComponent } from '../manage/correspondent-list/correspondent-edit-dialog/correspondent-edit-dialog.component';
import { DocumentTypeEditDialogComponent } from '../manage/document-type-list/document-type-edit-dialog/document-type-edit-dialog.component';
import { TagEditDialogComponent } from '../manage/tag-list/tag-edit-dialog/tag-edit-dialog.component';
@Component({
  selector: 'app-document-detail',
  templateUrl: './document-detail.component.html',
  styleUrls: ['./document-detail.component.css']
})
export class DocumentDetailComponent implements OnInit {

  documentId: number
  document: PaperlessDocument
  title: string
  previewUrl: string
  downloadUrl: string

  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]
  tags: PaperlessTag[]

  documentForm: FormGroup = new FormGroup({
    title: new FormControl(''),
    content: new FormControl(''),
    created_date: new FormControl(),
    created_time: new FormControl(),
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
    private tagService: TagService,
    private datePipe: DatePipe,
    private router: Router,
    private modalService: NgbModal,
    private openDocumentService: OpenDocumentsService,
    private documentListViewService: DocumentListViewService) { }

  ngOnInit(): void {
    this.correspondentService.list().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.list().subscribe(result => this.documentTypes = result.results)
    this.tagService.list().subscribe(result => this.tags = result.results)

    this.route.paramMap.subscribe(paramMap => {
      this.documentId = +paramMap.get('id')
      this.previewUrl = this.documentsService.getPreviewUrl(this.documentId)
      this.downloadUrl = this.documentsService.getDownloadUrl(this.documentId)
      this.documentsService.get(this.documentId).subscribe(doc => {
        this.openDocumentService.openDocument(doc)
        this.document = doc
        this.title = doc.title
        this.documentForm.patchValue(doc)
        this.documentForm.get('created_date').patchValue(this.datePipe.transform(doc.created, 'yyyy-MM-dd'))
        this.documentForm.get('created_time').patchValue(this.datePipe.transform(doc.created, 'HH:mm:ss'))
      }, error => {this.router.navigate(['404'])})
    })

  }

  createTag() {
    var modal = this.modalService.open(TagEditDialogComponent, {backdrop: 'static'})
    modal.componentInstance.dialogMode = 'create'
    modal.componentInstance.success.subscribe(newTag => {
      this.tagService.list().subscribe(tags => {
        this.tags = tags.results
        this.documentForm.get('tags_id').setValue(this.documentForm.get('tags_id').value.concat([newTag.id]))
      })
    })
  }

  createDocumentType() {
    var modal = this.modalService.open(DocumentTypeEditDialogComponent, {backdrop: 'static'})
    modal.componentInstance.dialogMode = 'create'
    modal.componentInstance.success.subscribe(newDocumentType => {
      this.documentTypeService.list().subscribe(documentTypes => {
        this.documentTypes = documentTypes.results
        this.documentForm.get('document_type_id').setValue(newDocumentType.id)
      })
    })
  }

  createCorrespondent() {
    var modal = this.modalService.open(CorrespondentEditDialogComponent, {backdrop: 'static'})
    modal.componentInstance.dialogMode = 'create'
    modal.componentInstance.success.subscribe(newCorrespondent => {
      this.correspondentService.list().subscribe(correspondents => {
        this.correspondents = correspondents.results
        this.documentForm.get('correspondent_id').setValue(newCorrespondent.id)
      })
    })
  }

  getTag(id: number): PaperlessTag {
    return this.tags.find(tag => tag.id == id)
  }

  getColour(id: number) {
    return PaperlessTag.COLOURS.find(c => c.id == this.getTag(id).colour)
  }

  addTag(id: number) {
    if (this.documentForm.value.tags.indexOf(id) == -1) {
      this.documentForm.value.tags.push(id)
    }
  }

  removeTag(id: number) {
    let index = this.documentForm.value.tags.indexOf(id)
    if (index > -1) {
      this.documentForm.value.tags.splice(index, 1)
    }
  }

  getDateCreated() {
    let newDate = this.documentForm.value.created_date
    let newTime = this.documentForm.value.created_time
    return formatDate(newDate + "T" + newTime,"yyyy-MM-ddTHH:mm:ssZZZZZ", "en-us", "UTC")
    
  }

  save() {
    let newDocument = Object.assign(Object.assign({}, this.document), this.documentForm.value)

    newDocument.created = this.getDateCreated()
    
    this.documentsService.update(newDocument).subscribe(result => {
      this.close()
    })
  }

  saveEditNext() {
    let newDocument = Object.assign(Object.assign({}, this.document), this.documentForm.value)

    newDocument.created = this.getDateCreated()

    this.documentsService.update(newDocument).subscribe(result => {
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
    this.router.navigate(['documents'])
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
