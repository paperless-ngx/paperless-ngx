import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { cloneFilterRules, FilterRule } from '../data/filter-rule';
import { PaperlessDocument } from '../data/paperless-document';
import { SavedViewConfig } from '../data/saved-view-config';
import { GENERAL_SETTINGS } from '../data/storage-keys';
import { DocumentService, SORT_DIRECTION_DESCENDING } from './rest/document.service';


@Injectable({
  providedIn: 'root'
})
export class DocumentListViewService {

  static DEFAULT_SORT_FIELD = 'created'

  documents: PaperlessDocument[] = []
  currentPage = 1
  currentPageSize: number = +localStorage.getItem(GENERAL_SETTINGS.DOCUMENT_LIST_SIZE) || GENERAL_SETTINGS.DOCUMENT_LIST_SIZE_DEFAULT
  collectionSize: number

  currentFilterRules: FilterRule[] = []
  currentSortDirection = SORT_DIRECTION_DESCENDING
  currentSortField = DocumentListViewService.DEFAULT_SORT_FIELD
  
  viewConfig: SavedViewConfig

  reload(onFinish?) {
    let sortField: string
    let sortDirection: string
    let filterRules: FilterRule[]
    if (this.viewConfig) {
      sortField = this.viewConfig.sortField
      sortDirection = this.viewConfig.sortDirection
      filterRules = this.viewConfig.filterRules
    } else {
      sortField = this.currentSortField
      sortDirection = this.currentSortDirection
      filterRules = this.currentFilterRules
    }

    this.documentService.list(
      this.currentPage,
      this.currentPageSize,
      sortField,
      sortDirection,
      filterRules).subscribe(
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


  setFilterRules(filterRules: FilterRule[]) {
    this.currentFilterRules = cloneFilterRules(filterRules)
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

  constructor(private documentService: DocumentService) { }
}
