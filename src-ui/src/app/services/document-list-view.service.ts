import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { cloneFilterRules, FilterRule } from '../data/filter-rule';
import { PaperlessDocument } from '../data/paperless-document';
import { PaperlessSavedView } from '../data/paperless-saved-view';
import { DOCUMENT_LIST_SERVICE, GENERAL_SETTINGS } from '../data/storage-keys';
import { DocumentService } from './rest/document.service';


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
  currentPageSize: number = +localStorage.getItem(GENERAL_SETTINGS.DOCUMENT_LIST_SIZE) || GENERAL_SETTINGS.DOCUMENT_LIST_SIZE_DEFAULT
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
    if (value) {
      //this is here so that we don't modify value, which might be the actual instance of the saved view.
      this._savedViewConfig = Object.assign({}, value)
    } else {
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
    this.documentService.list(
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
          if (error.error['detail'] == 'Invalid page.') {
            this.currentPage = 1
            this.reload()
          }
          this.isReloading = false
        })
  }

  set filterRules(filterRules: FilterRule[]) {
    //we're going to clone the filterRules object, since we don't
    //want changes in the filter editor to propagate into here right away.
    this.view.filter_rules = cloneFilterRules(filterRules)
    this.reload()
    this.saveDocumentListView()
  }

  get filterRules(): FilterRule[] {
    return cloneFilterRules(this.view.filter_rules)
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

  private saveDocumentListView() {
    sessionStorage.setItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG, JSON.stringify(this.documentListView))
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
    let newPageSize = +localStorage.getItem(GENERAL_SETTINGS.DOCUMENT_LIST_SIZE) || GENERAL_SETTINGS.DOCUMENT_LIST_SIZE_DEFAULT
    if (newPageSize != this.currentPageSize) {
      this.currentPageSize = newPageSize
      //this.reload()
    }
  }

  constructor(private documentService: DocumentService) {
    let documentListViewConfigJson = sessionStorage.getItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
    if (documentListViewConfigJson) {
      try {
        this.documentListView = JSON.parse(documentListViewConfigJson)
      } catch (e) {
        sessionStorage.removeItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
        this.documentListView = null
      }
    }
    if (!this.documentListView) {
      this.documentListView = {
        filter_rules: [],
        sort_reverse: true,
        sort_field: 'created'
      }
    }
  }
}
