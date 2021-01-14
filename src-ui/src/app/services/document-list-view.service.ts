import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { Observable } from 'rxjs';
import { cloneFilterRules, FilterRule } from '../data/filter-rule';
import { PaperlessDocument } from '../data/paperless-document';
import { PaperlessSavedView } from '../data/paperless-saved-view';
import { DOCUMENT_LIST_SERVICE } from '../data/storage-keys';
import { DocumentService } from './rest/document.service';
import { SettingsService, SETTINGS_KEYS } from './settings.service';


/**
 * This service manages the document list which is displayed using the document list view.
 *
 * This service also serves saved views by transparently switching between the document list
 * and saved views on request. See below.
 */
@Injectable({
  providedIn: 'root'
})
export class DocumentListViewService {

  static DEFAULT_SORT_FIELD = 'created'

  isReloading: boolean = false
  documents: PaperlessDocument[] = []
  currentPage = 1
  currentPageSize: number = this.settings.get(SETTINGS_KEYS.DOCUMENT_LIST_SIZE)
  collectionSize: number

  /**
   * This is the current config for the document list. The service will always remember the last settings used for the document list.
   */
  private _documentListViewConfig: PaperlessSavedView
  /**
   * Optionally, this is the currently selected saved view, which might be null.
   */
  private _savedViewConfig: PaperlessSavedView

  get savedView(): PaperlessSavedView {
    return this._savedViewConfig
  }

  set savedView(value: PaperlessSavedView) {
    if (value && !this._savedViewConfig || value && value.id != this._savedViewConfig.id) {
      //saved view inactive and should be active now, or saved view active, but a different view is requested
      //this is here so that we don't modify value, which might be the actual instance of the saved view.
      this.selectNone()
      this._savedViewConfig = Object.assign({}, value)
    } else if (this._savedViewConfig && !value) {
      //saved view active, but document list requested
      this.selectNone()
      this._savedViewConfig = null
    }
  }

  get savedViewId() {
    return this.savedView?.id
  }

  get savedViewTitle() {
    return this.savedView?.name
  }

  get documentListView() {
    return this._documentListViewConfig
  }

  set documentListView(value) {
    if (value) {
      this._documentListViewConfig = Object.assign({}, value)
      this.saveDocumentListView()
    }
  }

  /**
   * This is what switches between the saved views and the document list view. Everything on the document list uses
   * this property to determine the settings for the currently displayed document list.
   */
  get view() {
    return this.savedView || this.documentListView
  }

  load(view: PaperlessSavedView) {
    this.documentListView.filter_rules = cloneFilterRules(view.filter_rules)
    this.documentListView.sort_reverse = view.sort_reverse
    this.documentListView.sort_field = view.sort_field
    this.saveDocumentListView()
  }

  clear() {
    this.collectionSize = null
    this.documents = []
    this.currentPage = 1
  }

  reload(onFinish?) {
    this.isReloading = true
    this.documentService.listFiltered(
      this.currentPage,
      this.currentPageSize,
      this.view.sort_field,
      this.view.sort_reverse,
      this.view.filter_rules).subscribe(
        result => {
          this.collectionSize = result.count
          this.documents = result.results
          if (onFinish) {
            onFinish()
          }
          this.isReloading = false
        },
        error => {
          if (this.currentPage != 1 && error.status == 404) {
            // this happens when applying a filter: the current page might not be available anymore due to the reduced result set.
            this.currentPage = 1
            this.reload()
          }
          this.isReloading = false
        })
  }

  set filterRules(filterRules: FilterRule[]) {
    //we're going to clone the filterRules object, since we don't
    //want changes in the filter editor to propagate into here right away.
    this.view.filter_rules = filterRules
    this.reload()
    this.reduceSelectionToFilter()
    this.saveDocumentListView()
  }

  get filterRules(): FilterRule[] {
    return this.view.filter_rules
  }

  set sortField(field: string) {
    this.view.sort_field = field
    this.saveDocumentListView()
    this.reload()
  }

  get sortField(): string {
    return this.view.sort_field
  }

  set sortReverse(reverse: boolean) {
    this.view.sort_reverse = reverse
    this.saveDocumentListView()
    this.reload()
  }

  get sortReverse(): boolean {
    return this.view.sort_reverse
  }

  setSort(field: string, reverse: boolean) {
    this.view.sort_field = field
    this.view.sort_reverse = reverse
    this.saveDocumentListView()
    this.reload()
  }

  private saveDocumentListView() {
    sessionStorage.setItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG, JSON.stringify(this.documentListView))
  }

  quickFilter(filterRules: FilterRule[]) {
    this.savedView = null
    this.view.filter_rules = filterRules
    this.reduceSelectionToFilter()
    this.saveDocumentListView()
    this.router.navigate(["documents"])
  }

  getLastPage(): number {
    return Math.ceil(this.collectionSize / this.currentPageSize)
  }

  hasNext(doc: number) {
    if (this.documents) {
      let index = this.documents.findIndex(d => d.id == doc)
      return index != -1 && (this.currentPage < this.getLastPage() || (index + 1) < this.documents.length)
    }
  }

  getNext(currentDocId: number): Observable<number> {
    return new Observable(nextDocId => {
      if (this.documents != null) {

        let index = this.documents.findIndex(d => d.id == currentDocId)

        if (index != -1 && (index + 1) < this.documents.length) {
          nextDocId.next(this.documents[index+1].id)
          nextDocId.complete()
        } else if (index != -1 && this.currentPage < this.getLastPage()) {
          this.currentPage += 1
          this.reload(() => {
            nextDocId.next(this.documents[0].id)
            nextDocId.complete()
          })
        } else {
          nextDocId.complete()
        }
      } else {
        nextDocId.complete()
      }
    })
  }

  updatePageSize() {
    let newPageSize = this.settings.get(SETTINGS_KEYS.DOCUMENT_LIST_SIZE)
    if (newPageSize != this.currentPageSize) {
      this.currentPageSize = newPageSize
    }
  }

  selected = new Set<number>()

  selectNone() {
    this.selected.clear()
  }

  reduceSelectionToFilter() {
    if (this.selected.size > 0) {
      this.documentService.listAllFilteredIds(this.filterRules).subscribe(ids => {
        let subset = new Set<number>()
        for (let id of ids) {
          if (this.selected.has(id)) {
            subset.add(id)
          }
        }
        this.selected = subset
      })
    }
  }

  selectAll() {
    this.documentService.listAllFilteredIds(this.filterRules).subscribe(ids => ids.forEach(id => this.selected.add(id)))
  }

  selectPage() {
    this.selected.clear()
    this.documents.forEach(doc => {
      this.selected.add(doc.id)
    })
  }

  isSelected(d: PaperlessDocument) {
    return this.selected.has(d.id)
  }

  setSelected(d: PaperlessDocument, value: boolean) {
    if (value) {
      this.selected.add(d.id)
    } else if (!value) {
      this.selected.delete(d.id)
    }
  toggleSelected(d: PaperlessDocument): void {
    if (this.selected.has(d.id)) this.selected.delete(d.id)
    else this.selected.add(d.id)
  }

  constructor(private documentService: DocumentService, private settings: SettingsService, private router: Router) {
    let documentListViewConfigJson = sessionStorage.getItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
    if (documentListViewConfigJson) {
      try {
        this.documentListView = JSON.parse(documentListViewConfigJson)
      } catch (e) {
        sessionStorage.removeItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
        this.documentListView = null
      }
    }
    if (!this.documentListView || this.documentListView.filter_rules == null || this.documentListView.sort_reverse == null || this.documentListView.sort_field == null) {
      this.documentListView = {
        filter_rules: [],
        sort_reverse: true,
        sort_field: 'created'
      }
    }
  }
}
