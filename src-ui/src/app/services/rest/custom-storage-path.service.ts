import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable, map } from 'rxjs'
import { FilterRule } from 'src/app/data/filter-rule'
import { PaperlessDocument } from 'src/app/data/paperless-document'
import { PaperlessDocumentMetadata } from 'src/app/data/paperless-document-metadata'
import { PaperlessDocumentSuggestions } from 'src/app/data/paperless-document-suggestions'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { Results } from 'src/app/data/results'
import { queryParamsFromFilterRules } from 'src/app/utils/query-params'
import { AbstractPaperlessService } from './abstract-paperless-service'

interface SelectionDataItem {
  id: number
  document_count: number
}

interface SelectionData {
  selected_storage_paths: SelectionDataItem[]
  selected_correspondents: SelectionDataItem[]
  selected_tags: SelectionDataItem[]
  selected_document_types: SelectionDataItem[]
}

@Injectable({
  providedIn: 'root',
})
export class CustomStoragePathService extends AbstractPaperlessService<PaperlessStoragePath> {
  private _searchQuery: string

  constructor(http: HttpClient) {
    super(http, 'storage_paths')
  }

  listFiltered(
    page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    filterRules?: FilterRule[],
    extraParams = {}
  ): Observable<Results<PaperlessStoragePath>> {
    return this.list(
      page,
      pageSize,
      sortField,
      sortReverse,
      Object.assign(extraParams, queryParamsFromFilterRules(filterRules))
    ).pipe(
      map((results) => {
        return results
      })
    )
  }

  listAllFilteredIds(filterRules?: FilterRule[]): Observable<number[]> {
    return this.listFiltered(1, 100000, null, null, filterRules, {
      fields: 'id',
    }).pipe(map((response) => response.results.map((doc) => doc.id)))
  }

  getPreviewUrl(id: number, original: boolean = false): string {
    let url = this.getResourceUrl(id, 'preview')
    if (this._searchQuery) url += `#search="${this._searchQuery}"`
    if (original) {
      url += '?original=true'
    }
    return url
  }

  getThumbUrl(id: number): string {
    return this.getResourceUrl(id, 'thumb')
  }

  getDownloadUrl(id: number, original: boolean = false): string {
    let url = this.getResourceUrl(id, 'download')
    if (original) {
      url += '?original=true'
    }
    return url
  }

  update(o: PaperlessDocument): Observable<PaperlessDocument> {
    // we want to only set created_date
    o.created = undefined
    return super.update(o)
  }

  uploadDocument(formData) {
    return this.http.post(
      this.getResourceUrl(null, 'post_document'),
      formData,
      { reportProgress: true, observe: 'events' }
    )
  }

  getMetadata(id: number): Observable<PaperlessDocumentMetadata> {
    return this.http.get<PaperlessDocumentMetadata>(
      this.getResourceUrl(id, 'metadata')
    )
  }

  bulkEdit(ids: number[], method: string, args: any) {
    return this.http.post(this.getResourceUrl(null, 'bulk_edit'), {
      documents: ids,
      method: method,
      parameters: args,
    })
  }

  getSuggestions(id: number): Observable<PaperlessDocumentSuggestions> {
    return this.http.get<PaperlessDocumentSuggestions>(
      this.getResourceUrl(id, 'suggestions')
    )
  }

  bulkDownload(
    ids: number[],
    content = 'both',
    useFilenameFormatting: boolean = false
  ) {
    return this.http.post(
      this.getResourceUrl(null, 'bulk_download'),
      {
        documents: ids,
        content: content,
        follow_formatting: useFilenameFormatting,
      },
      { responseType: 'blob' }
    )
  }

  public set searchQuery(query: string) {
    this._searchQuery = query
  }
}
