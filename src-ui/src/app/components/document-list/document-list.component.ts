import { Component, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { PaperlessDocument } from 'src/app/data/paperless-document';
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
import { ChangedItems } from './bulk-editor/bulk-editor.component';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';

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
    private documentService: DocumentService,
    private openDocumentService: OpenDocumentsService) { }

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

  trackByDocumentId(index, item: PaperlessDocument) {
    return item.id
  }

  private executeBulkOperation(method: string, args): Observable<any> {
    return this.documentService.bulkEdit(Array.from(this.list.selected), method, args).pipe(
      tap(() => {
        this.list.reload()
        this.list.selected.forEach(id => {
          this.openDocumentService.refreshDocument(id)
        })
        this.list.selectNone()
      })
    )
  }

  bulkSetTags(changedTags: ChangedItems) {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Tags Assignment"
    let action = 'set_tags'
    let tags
    let messageFragment = ''
    let both = changedTags && changedTags.itemsToAdd.length > 0 && changedTags.itemsToRemove.length > 0
    if (!changedTags) {
      messageFragment = `remove all tags from`
    } else {
      if (changedTags.itemsToAdd.length > 0) {
        tags = changedTags.itemsToAdd
        messageFragment = `assign the tag(s) ${changedTags.itemsToAdd.map(t => t.name).join(', ')} to`
      }
      if (changedTags.itemsToRemove.length > 0) {
        if (!both) {
          action = 'remove_tags'
          tags = changedTags.itemsToRemove
        } else {
          messageFragment += ' and '
        }
        messageFragment += `remove the tag(s) ${changedTags.itemsToRemove.map(t => t.name).join(', ')} from`
      }
    }
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      // TODO: API endpoints for add/remove multiple tags
      this.executeBulkOperation(action, {"tags": tags ? tags.map(t => t.id) : null}).subscribe(
        response => {
          if (!both) modal.close()
          else {
            this.executeBulkOperation('remove_tags', {"tags": changedTags.itemsToRemove.map(t => t.id)}).subscribe(
              response => {
                modal.close()
              })
          }
        }
      )
    })
  }

  bulkSetCorrespondents(changedCorrespondents: ChangedItems) {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Correspondent Assignment"
    let correspondent
    let messageFragment = 'remove all correspondents from'
    if (changedCorrespondents && changedCorrespondents.itemsToAdd.length > 0) {
      correspondent = changedCorrespondents.itemsToAdd[0]
      messageFragment = `assign the correspondent ${correspondent.name} to`
    }
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

  bulkSetDocumentTypes(changedDocumentTypes: ChangedItems) {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Document Type Assignment"
    let documentType
    let messageFragment = 'remove all document types from'
    if (changedDocumentTypes && changedDocumentTypes.itemsToAdd.length > 0) {
      documentType = changedDocumentTypes.itemsToAdd[0]
      messageFragment = `assign the document type ${documentType.name} to`
    }
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
