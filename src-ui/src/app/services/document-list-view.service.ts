import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { cloneFilterRules, FilterRule, filterRulesToQueryParams } from '../data/filter-rule';
import { PaperlessDocument } from '../data/paperless-document';
import { SavedViewConfig } from '../data/saved-view-config';
import { DocumentService } from './rest/document.service';

@Injectable({
  providedIn: 'root'
})
export class DocumentListViewService {

  static DEFAULT_SORT_FIELD = 'created'

  static SORT_FIELDS = [
    {field: "correspondent__name", name: "Correspondent"},
    {field: 'title', name: 'Title'},
    {field: 'archive_serial_number', name: 'ASN'},
    {field: 'created', name: 'Created'},
    {field: 'added', name: 'Added'},
    {field: 'modified', name: 'Modified'}
  ]

  documents: PaperlessDocument[] = []
  currentPage = 1
  collectionSize: number

  currentFilterRules: FilterRule[] = []
  currentSortDirection = 'des'
  currentSortField = DocumentListViewService.DEFAULT_SORT_FIELD
  
  viewConfig: SavedViewConfig

  reload(onFinish?) {
    let ordering: string
    let filterRules: FilterRule[]
    if (this.viewConfig) {
      ordering = this.getOrderingQueryParam(this.viewConfig.sortField, this.viewConfig.sortDirection)
      filterRules = this.viewConfig.filterRules
    } else {
      ordering = this.getOrderingQueryParam(this.currentSortField, this.currentSortDirection)
      filterRules = this.currentFilterRules
    }

    this.documentService.list(
      this.currentPage,
      null,
      ordering,
      filterRulesToQueryParams(filterRules)).subscribe(
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

  getOrderingQueryParam(sortField: string, sortDirection: string) {
    if (DocumentListViewService.SORT_FIELDS.find(f => f.field == sortField)) {
      return (sortDirection == 'des' ? '-' : '') + sortField
    } else {
      return DocumentListViewService.DEFAULT_SORT_FIELD
    }
  }

  //TODO: refactor
  setFilterRules(filterRules: FilterRule[]) {
    this.currentFilterRules = cloneFilterRules(filterRules)
  }

  getLastPage(): number {
    return Math.ceil(this.collectionSize / 25)
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

  constructor(private documentService: DocumentService) { }
}
