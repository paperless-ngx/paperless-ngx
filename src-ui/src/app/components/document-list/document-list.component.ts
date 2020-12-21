import { Component, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { DocumentService, DOCUMENT_SORT_FIELDS } from 'src/app/services/rest/document.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { Toast, ToastService } from 'src/app/services/toast.service';
import { FilterEditorComponent } from './filter-editor/filter-editor.component';
import { ConfirmDialogComponent } from '../common/confirm-dialog/confirm-dialog.component';
import { SelectDialogComponent } from '../common/select-dialog/select-dialog.component';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';

@Component({
  selector: 'app-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.scss']
})
export class DocumentListComponent implements OnInit {

  constructor(
    public list: DocumentListViewService,
    public savedViewService: SavedViewService,
    public route: ActivatedRoute,
    private router: Router,
    private toastService: ToastService,
    public modalService: NgbModal,
    private correspondentService: CorrespondentService,
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private documentService: DocumentService) { }

  @ViewChild("filterEditor")
  private filterEditor: FilterEditorComponent

  displayMode = 'smallCards' // largeCards, smallCards, details

  get isFiltered() {
    return this.list.filterRules?.length > 0
  }

  getTitle() {
    return this.list.savedViewTitle || "Documents"
  }

  getSortFields() {
    return DOCUMENT_SORT_FIELDS
  }

  get isBulkEditing(): boolean {
    return this.list.selected.size > 0
  }

  saveDisplayMode() {
    localStorage.setItem('document-list:displayMode', this.displayMode)
  }

  ngOnInit(): void {
    if (localStorage.getItem('document-list:displayMode') != null) {
      this.displayMode = localStorage.getItem('document-list:displayMode')
    }
    this.route.paramMap.subscribe(params => {
      this.list.clear()
      if (params.has('id')) {
        this.savedViewService.getCached(+params.get('id')).subscribe(view => {
          if (!view) {
            this.router.navigate(["404"])
            return
          }

          this.list.savedView = view
          this.list.reload()
        })
      } else {
        this.list.savedView = null
        this.list.reload()
      }
    })
  }


  loadViewConfig(view: PaperlessSavedView) {
    this.list.load(view)
    this.list.reload()
  }

  saveViewConfig() {
    this.savedViewService.update(this.list.savedView).subscribe(result => {
      this.toastService.showToast(Toast.make("Information", `View "${this.list.savedView.name}" saved successfully.`))
    })

  }

  saveViewConfigAs() {
    let modal = this.modalService.open(SaveViewConfigDialogComponent, {backdrop: 'static'})
    modal.componentInstance.defaultName = this.filterEditor.generateFilterName()
    modal.componentInstance.saveClicked.subscribe(formValue => {
      let savedView = {
        name: formValue.name,
        show_on_dashboard: formValue.showOnDashboard,
        show_in_sidebar: formValue.showInSideBar,
        filter_rules: this.list.filterRules,
        sort_reverse: this.list.sortReverse,
        sort_field: this.list.sortField
      }
      this.savedViewService.create(savedView).subscribe(() => {
        modal.close()
        this.toastService.showToast(Toast.make("Information", `View "${savedView.name}" created successfully.`))
      })
    })
  }

  clickTag(tagID: number) {
    this.list.selectNone()
    setTimeout(() => {
      this.filterEditor.toggleTag(tagID)
    })
  }

  clickCorrespondent(correspondentID: number) {
    this.list.selectNone()
    setTimeout(() => {
      this.filterEditor.toggleCorrespondent(correspondentID)
    })
  }

  clickDocumentType(documentTypeID: number) {
    this.list.selectNone()
    setTimeout(() => {
      this.filterEditor.toggleDocumentType(documentTypeID)
    })
  }

  private executeBulkOperation(method: string, args): Observable<any> {
    return this.documentService.bulkEdit(Array.from(this.list.selected), method, args).pipe(
      map(r => {

        this.list.reload()
        this.list.selectNone()

        return r
      })
    )
  }

  bulkSetCorrespondent(correspondent: PaperlessCorrespondent) {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm correspondent assignment"
    let messageFragment = correspondent ? `assign the correspondent ${correspondent.name} to` : `remove all correspondents from`
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('set_correspondent', {"correspondent": correspondent ? correspondent.id : null}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }

  bulkSetDocumentType(documentType: PaperlessDocumentType) {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Document Type assignment"
    let messageFragment = documentType ? `assign the document type ${documentType.name} to` : `remove all document types from`
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('set_document_type', {"document_type": documentType ? documentType.id : null}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }

  bulkSetTags(tags: PaperlessTag[]) {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Tags assignment"
    let messageFragment = tags ? `assign the tag(s) ${tags.map(t => t.name).join(', ')} to` : `remove all tags from`
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      // TODO: API endpoint for set multiple tags
      this.executeBulkOperation('set_tags', {"document_type": tags ? tags.map(t => t.id) : null}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }

  bulkDelete() {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.delayConfirm(5)
    modal.componentInstance.title = "Delete confirm"
    modal.componentInstance.messageBold = `This operation will permanently delete all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.message = `This operation cannot be undone.`
    modal.componentInstance.btnClass = "btn-danger"
    modal.componentInstance.btnCaption = "Delete document(s)"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation("delete", {}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }
}
