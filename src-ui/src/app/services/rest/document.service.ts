import { Injectable } from '@angular/core';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { AbstractPaperlessService } from './abstract-paperless-service';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Results } from 'src/app/data/results';
import { FilterRule } from 'src/app/data/filter-rule';


export const DOCUMENT_SORT_FIELDS = [
  { field: "correspondent__name", name: "Correspondent" },
  { field: "document_type__name", name: "Document type" },
  { field: 'title', name: 'Title' },
  { field: 'archive_serial_number', name: 'ASN' },
  { field: 'created', name: 'Created' },
  { field: 'added', name: 'Added' },
  { field: 'modified', name: 'Modified' }
]

export const SORT_DIRECTION_ASCENDING = "asc"
export const SORT_DIRECTION_DESCENDING = "des"


@Injectable({
  providedIn: 'root'
})
export class DocumentService extends AbstractPaperlessService<PaperlessDocument> {

  constructor(http: HttpClient) {
    super(http, 'documents')
  }

  private filterRulesToQueryParams(filterRules: FilterRule[]) {
    if (filterRules) {
      let params = {}
      for (let rule of filterRules) {
        if (rule.type.multi) {
          params[rule.type.filtervar] = params[rule.type.filtervar] ? params[rule.type.filtervar] + "," + rule.value : rule.value
        } else {
          params[rule.type.filtervar] = rule.value
        }
      }
      return params
    } else {
      return null
    }
  }

  list(page?: number, pageSize?: number, sortField?: string, sortDirection?: string, filterRules?: FilterRule[]): Observable<Results<PaperlessDocument>> {
    return super.list(page, pageSize, sortField, sortDirection, this.filterRulesToQueryParams(filterRules))
  }

  getPreviewUrl(id: number): string {
    return this.getResourceUrl(id, 'preview')
  }

  getThumbUrl(id: number): string {
    return this.getResourceUrl(id, 'thumb')
  }

  getDownloadUrl(id: number): string {
    return this.getResourceUrl(id, 'download')
  }

  uploadDocument(formData) {
    return this.http.post(this.getResourceUrl(null, 'post_document'), formData)
  }

  bulk_edit(ids: number[], method: string, args: any[]) {
    return this.http.post(this.getResourceUrl(null, 'bulk_edit'), {
      'ids': ids,
      'method': method,
      'args': args
    })
  }

}
