import { Component, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { FILTER_CORRESPONDENT } from 'src/app/data/filter-rule-type';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { DOCUMENT_SORT_FIELDS } from 'src/app/services/rest/document.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { Toast, ToastService } from 'src/app/services/toast.service';
import { FilterEditorComponent } from '../filter-editor/filter-editor.component';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';

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
    public modalService: NgbModal) { }

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

}
