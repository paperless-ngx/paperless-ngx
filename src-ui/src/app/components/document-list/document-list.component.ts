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
import { FilterEditorComponent } from '../filter-editor/filter-editor.component';
import { ConfirmDialogComponent } from '../common/confirm-dialog/confirm-dialog.component';
import { SelectDialogComponent } from '../common/select-dialog/select-dialog.component';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';
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
    this.filterEditor.toggleTag(tagID)
  }

  clickCorrespondent(correspondentID: number) {
    this.filterEditor.toggleCorrespondent(correspondentID)
  }

  clickDocumentType(documentTypeID: number) {
    this.filterEditor.toggleDocumentType(documentTypeID)
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

  bulkSetCorrespondent() {
    let modal = this.modalService.open(SelectDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Select correspondent"
    modal.componentInstance.message = `Select the correspondent you wish to assign to ${this.list.selected.size} selected document(s):`
    this.correspondentService.listAll().subscribe(response => {
      modal.componentInstance.objects = response.results
    })
    modal.componentInstance.selectClicked.subscribe(selectedId => {
      this.executeBulkOperation('set_correspondent', {"correspondent": selectedId}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }

  bulkRemoveCorrespondent() {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Remove correspondent"
    modal.componentInstance.message = `This operation will remove the correspondent from all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('set_correspondent', {"correspondent": null}).subscribe(r => {
        modal.close()
      })
    })
  }

  bulkSetDocumentType() {
    let modal = this.modalService.open(SelectDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Select document type"
    modal.componentInstance.message = `Select the document type you wish to assign to ${this.list.selected.size} selected document(s):`
    this.documentTypeService.listAll().subscribe(response => {
      modal.componentInstance.objects = response.results
    })
    modal.componentInstance.selectClicked.subscribe(selectedId => {
      this.executeBulkOperation('set_document_type', {"document_type": selectedId}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }

  bulkRemoveDocumentType() {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Remove document type"
    modal.componentInstance.message = `This operation will remove the document type from all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('set_document_type', {"document_type": null}).subscribe(r => {
        modal.close()
      })
    })
  }

  bulkAddTag() {
    let modal = this.modalService.open(SelectDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Select tag"
    modal.componentInstance.message = `Select the tag you wish to assign to ${this.list.selected.size} selected document(s):`
    this.tagService.listAll().subscribe(response => {
      modal.componentInstance.objects = response.results
    })
    modal.componentInstance.selectClicked.subscribe(selectedId => {
      this.executeBulkOperation('add_tag', {"tag": selectedId}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }

  bulkRemoveTag() {
    let modal = this.modalService.open(SelectDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Select tag"
    modal.componentInstance.message = `Select the tag you wish to remove from ${this.list.selected.size} selected document(s):`
    this.tagService.listAll().subscribe(response => {
      modal.componentInstance.objects = response.results
    })
    modal.componentInstance.selectClicked.subscribe(selectedId => {
      this.executeBulkOperation('remove_tag', {"tag": selectedId}).subscribe(
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
