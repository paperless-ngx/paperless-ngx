import { Component, OnDestroy, OnInit, QueryList, ViewChild, ViewChildren } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Subscription } from 'rxjs';
import { FilterRule, isFullTextFilterRule } from 'src/app/data/filter-rule';
import { FILTER_FULLTEXT_MORELIKE } from 'src/app/data/filter-rule-type';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { SortableDirective, SortEvent } from 'src/app/directives/sortable.directive';
import { ConsumerStatusService } from 'src/app/services/consumer-status.service';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { DOCUMENT_SORT_FIELDS, DOCUMENT_SORT_FIELDS_FULLTEXT } from 'src/app/services/rest/document.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { ToastService } from 'src/app/services/toast.service';
import { FilterEditorComponent } from './filter-editor/filter-editor.component';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';

@Component({
  selector: 'app-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.scss']
})
export class DocumentListComponent implements OnInit, OnDestroy {

  constructor(
    public list: DocumentListViewService,
    public savedViewService: SavedViewService,
    public route: ActivatedRoute,
    private router: Router,
    private toastService: ToastService,
    private modalService: NgbModal,
    private consumerStatusService: ConsumerStatusService
  ) { }

  @ViewChild("filterEditor")
  private filterEditor: FilterEditorComponent

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>;

  displayMode = 'smallCards' // largeCards, smallCards, details

  unmodifiedFilterRules: FilterRule[] = []

  private consumptionFinishedSubscription: Subscription

  get isFiltered() {
    return this.list.filterRules?.length > 0
  }

  getTitle() {
    return this.list.activeSavedViewTitle || $localize`Documents`
  }

  getSortFields() {
    return isFullTextFilterRule(this.list.filterRules) ? DOCUMENT_SORT_FIELDS_FULLTEXT : DOCUMENT_SORT_FIELDS
  }

  onSort(event: SortEvent) {
    this.list.setSort(event.column, event.reverse)
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
    this.consumptionFinishedSubscription = this.consumerStatusService.onDocumentConsumptionFinished().subscribe(() => {
      this.list.reload()
    })
    this.route.paramMap.subscribe(params => {
      if (params.has('id')) {
        this.savedViewService.getCached(+params.get('id')).subscribe(view => {
          if (!view) {
            this.router.navigate(["404"])
            return
          }
          this.list.activateSavedView(view)
          this.list.reload()
          this.unmodifiedFilterRules = view.filter_rules
        })
      } else {
        this.list.activateSavedView(null)
        this.list.reload()
        this.unmodifiedFilterRules = []
      }
    })
  }

  ngOnDestroy() {
    if (this.consumptionFinishedSubscription) {
      this.consumptionFinishedSubscription.unsubscribe()
    }
  }

  loadViewConfig(view: PaperlessSavedView) {
    this.list.loadSavedView(view)
    this.list.reload()
  }

  saveViewConfig() {
    if (this.list.activeSavedViewId != null) {
      let savedView: PaperlessSavedView = {
        id: this.list.activeSavedViewId,
        filter_rules: this.list.filterRules,
        sort_field: this.list.sortField,
        sort_reverse: this.list.sortReverse
      }
      this.savedViewService.patch(savedView).subscribe(result => {
        this.toastService.showInfo($localize`View "${this.list.activeSavedViewTitle}" saved successfully.`)
        this.unmodifiedFilterRules = this.list.filterRules
      })
    }
  }

  saveViewConfigAs() {
    let modal = this.modalService.open(SaveViewConfigDialogComponent, {backdrop: 'static'})
    modal.componentInstance.defaultName = this.filterEditor.generateFilterName()
    modal.componentInstance.saveClicked.subscribe(formValue => {
      modal.componentInstance.buttonsEnabled = false
      let savedView: PaperlessSavedView = {
        name: formValue.name,
        show_on_dashboard: formValue.showOnDashboard,
        show_in_sidebar: formValue.showInSideBar,
        filter_rules: this.list.filterRules,
        sort_reverse: this.list.sortReverse,
        sort_field: this.list.sortField
      }

      this.savedViewService.create(savedView).subscribe(() => {
        modal.close()
        this.toastService.showInfo($localize`View "${savedView.name}" created successfully.`)
      }, error => {
        modal.componentInstance.error = error.error
        modal.componentInstance.buttonsEnabled = true
      })
    })
  }

  toggleSelected(document: PaperlessDocument, event: MouseEvent): void {
    if (!event.shiftKey) this.list.toggleSelected(document)
    else this.list.selectRangeTo(document)
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

  clickMoreLike(documentID: number) {
    this.list.quickFilter([{rule_type: FILTER_FULLTEXT_MORELIKE, value: documentID.toString()}])
  }

  trackByDocumentId(index, item: PaperlessDocument) {
    return item.id
  }
}
