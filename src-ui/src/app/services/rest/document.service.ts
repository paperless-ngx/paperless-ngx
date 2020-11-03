import { Injectable } from '@angular/core';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { AbstractPaperlessService } from './abstract-paperless-service';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../auth.service';
import { Observable } from 'rxjs';
import { Results } from 'src/app/data/results';
import { FilterRule } from 'src/app/data/filter-rule';


export const DOCUMENT_SORT_FIELDS = [
  { field: "correspondent__name", name: "Correspondent" },
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

  constructor(http: HttpClient, private auth: AuthService) {
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

  private getOrderingQueryParam(sortField: string, sortDirection: string) {
    if (DOCUMENT_SORT_FIELDS.find(f => f.field == sortField)) {
      return (sortDirection == SORT_DIRECTION_DESCENDING ? '-' : '') + sortField
    } else {
      return null
    }
  }

  list(page?: number, pageSize?: number, sortField?: string, sortDirection?: string, filterRules?: FilterRule[]): Observable<Results<PaperlessDocument>> {
    return super.list(page, pageSize, this.getOrderingQueryParam(sortField, sortDirection), this.filterRulesToQueryParams(filterRules))
  }

  getPreviewUrl(id: number): string {
    return this.getResourceUrl(id, 'preview') + `?auth_token=${this.auth.getToken()}`
  }

  getThumbUrl(id: number): string {
    return this.getResourceUrl(id, 'thumb') + `?auth_token=${this.auth.getToken()}`
  }

  getDownloadUrl(id: number): string {
    return this.getResourceUrl(id, 'download') + `?auth_token=${this.auth.getToken()}`
  }

  uploadDocument(formData) {
    return this.http.post(this.getResourceUrl(null, 'post_document'), formData)
  }

}
