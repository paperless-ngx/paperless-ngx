import { AfterViewInit, Component, OnDestroy, OnInit, QueryList, ViewChild, ViewChildren } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Subscription } from 'rxjs';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { SortableDirective, SortEvent } from 'src/app/directives/sortable.directive';
import { ConsumerStatusService } from 'src/app/services/consumer-status.service';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { DOCUMENT_SORT_FIELDS } from 'src/app/services/rest/document.service';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { Toast, ToastService } from 'src/app/services/toast.service';
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

  filterRulesModified: boolean = false

  private consumptionFinishedSubscription: Subscription

  get isFiltered() {
    return this.list.filterRules?.length > 0
  }

  getTitle() {
    return this.list.savedViewTitle || $localize`Documents`
  }

  getSortFields() {
    return DOCUMENT_SORT_FIELDS
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
      this.list.clear()
      if (params.has('id')) {
        this.savedViewService.getCached(+params.get('id')).subscribe(view => {
          if (!view) {
            this.router.navigate(["404"])
            return
          }
          this.list.savedView = view
          this.list.reload()
          this.rulesChanged()
        })
      } else {
        this.list.savedView = null
        this.list.reload()
        this.rulesChanged()
      }
    })
  }

  ngOnDestroy() {
    if (this.consumptionFinishedSubscription) {
      this.consumptionFinishedSubscription.unsubscribe()
    }
  }

  loadViewConfig(view: PaperlessSavedView) {
    this.list.load(view)
    this.list.reload()
    this.rulesChanged()
  }

  saveViewConfig() {
    this.savedViewService.update(this.list.savedView).subscribe(result => {
      this.toastService.showInfo($localize`View "${this.list.savedView.name}" saved successfully.`)
    })

  }

  saveViewConfigAs() {
    let modal = this.modalService.open(SaveViewConfigDialogComponent, {backdrop: 'static'})
    modal.componentInstance.defaultName = this.filterEditor.generateFilterName()
    modal.componentInstance.saveClicked.subscribe(formValue => {
      modal.componentInstance.buttonsEnabled = false
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
        this.toastService.showInfo($localize`View "${savedView.name}" created successfully.`)
      }, error => {
        modal.componentInstance.error = error.error
        modal.componentInstance.buttonsEnabled = true
      })
    })
  }

  resetFilters(): void {
    this.filterRulesModified = false
    if (this.list.savedViewId) {
      this.savedViewService.getCached(this.list.savedViewId).subscribe(viewUntouched => {
        this.list.filterRules = viewUntouched.filter_rules
        this.list.reload()
      })
    } else {
      this.list.filterRules = []
      this.list.reload()
    }
  }

  rulesChanged() {
    let modified = false
    if (this.list.savedView == null) {
      modified = this.list.filterRules.length > 0 // documents list is modified if it has any filters
    } else {
      // compare savedView current filters vs original
      this.savedViewService.getCached(this.list.savedViewId).subscribe(view => {
        let filterRulesInitial = view.filter_rules

        if (this.list.filterRules.length !== filterRulesInitial.length) modified = true
        else {
          modified = this.list.filterRules.some(rule => {
            return (filterRulesInitial.find(fri => fri.rule_type == rule.rule_type && fri.value == rule.value) == undefined)
          })

          if (!modified) {
            // only check other direction if we havent already determined is modified
            modified = filterRulesInitial.some(rule => {
              this.list.filterRules.find(fr => fr.rule_type == rule.rule_type && fr.value == rule.value) == undefined
            })
          }
        }
      })
    }
    this.filterRulesModified = modified
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

  trackByDocumentId(index, item: PaperlessDocument) {
    return item.id
  }
}
