import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { cloneFilterRules, FilterRule } from '../data/filter-rule';
import { PaperlessDocument } from '../data/paperless-document';
import { SavedViewConfig } from '../data/saved-view-config';
import { DOCUMENT_LIST_SERVICE, GENERAL_SETTINGS } from '../data/storage-keys';
import { DocumentService } from './rest/document.service';


@Injectable({
  providedIn: 'root'
})
export class DocumentListViewService {

  static DEFAULT_SORT_FIELD = 'created'

  documents: PaperlessDocument[] = []
  currentPage = 1
  currentPageSize: number = +localStorage.getItem(GENERAL_SETTINGS.DOCUMENT_LIST_SIZE) || GENERAL_SETTINGS.DOCUMENT_LIST_SIZE_DEFAULT
  collectionSize: number
  
  private currentViewConfig: SavedViewConfig
  //TODO: make private
  viewConfigOverride: SavedViewConfig

  get viewId() {
    return this.viewConfigOverride?.id
  }

  reload(onFinish?) {
    let viewConfig = this.viewConfigOverride || this.currentViewConfig

    this.documentService.list(
      this.currentPage,
      this.currentPageSize,
      viewConfig.sortField,
      viewConfig.sortDirection,
      viewConfig.filterRules).subscribe(
        result => {
          this.collectionSize = result.count
          this.documents = result.results
          if (onFinish) {
            onFinish()
          }
        },
        error => {
          if (error.error['detail'] == 'Invalid page.') {
            this.currentPage = 1
            this.reload()
          }
        })
  }

  set filterRules(filterRules: FilterRule[]) {
    this.currentViewConfig.filterRules = cloneFilterRules(filterRules)
    this.saveCurrentViewConfig()
    this.reload()
  }

  get filterRules(): FilterRule[] {
    return cloneFilterRules(this.currentViewConfig.filterRules)
  }

  set sortField(field: string) {
    this.currentViewConfig.sortField = field
    this.saveCurrentViewConfig()
    this.reload()
  }

  get sortField(): string {
    return this.currentViewConfig.sortField
  }

  set sortDirection(direction: string) {
    this.currentViewConfig.sortDirection = direction
    this.saveCurrentViewConfig()
    this.reload()
  }

  get sortDirection(): string {
    return this.currentViewConfig.sortDirection
  }

  loadViewConfig(config: SavedViewConfig) {
    Object.assign(this.currentViewConfig, config)
    this.reload()
  }

  private saveCurrentViewConfig() {
    sessionStorage.setItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG, JSON.stringify(this.currentViewConfig))
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
    let currentViewConfigJson = sessionStorage.getItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
    if (currentViewConfigJson) {
      try {
        this.currentViewConfig = JSON.parse(currentViewConfigJson)
      } catch (e) {
        sessionStorage.removeItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
        this.currentViewConfig = null
      }
    }
    if (!this.currentViewConfig) {
      this.currentViewConfig = {
        filterRules: [],
        sortDirection: 'des',
        sortField: 'created'
      }
      }
  }
}
