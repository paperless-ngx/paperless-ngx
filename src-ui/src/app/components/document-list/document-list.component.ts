import { Component, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { DOCUMENT_SORT_FIELDS } from 'src/app/services/rest/document.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { Toast, ToastService } from 'src/app/services/toast.service';
import { FilterEditorComponent } from './filter-editor/filter-editor.component';
import { SelectDialogComponent } from '../common/select-dialog/select-dialog.component';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';
import { ChangedItems } from './bulk-editor/bulk-editor.component';

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
    private modalService: NgbModal,
    private correspondentService: CorrespondentService,
    private documentTypeService: DocumentTypeService,
    private tagService: TagService) { }

  @ViewChild("filterEditor")
  private filterEditor: FilterEditorComponent

  displayMode = 'smallCards' // largeCards, smallCards, details

  get isFiltered() {
    return this.list.filterRules?.length > 0
  }

  getTitle() {
    return this.list.savedViewTitle || $localize`Documents`
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
      this.toastService.showToast(Toast.make("Information", $localize`View "${this.list.savedView.name}" saved successfully.`))
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
        this.toastService.showToast(Toast.make("Information", $localize`View "${savedView.name}" created successfully.`))
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
}
