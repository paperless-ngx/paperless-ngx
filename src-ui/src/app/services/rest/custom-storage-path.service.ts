import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable, filter, map, switchMap, tap } from 'rxjs'
import { FilterRule } from 'src/app/data/filter-rule'
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
  constructor(http: HttpClient) {
    super(http, 'storage_paths')
  }

  getByPath(path: string): Observable<PaperlessStoragePath> {
    return this.list(1, 1, null, null, { path__iexact: path }).pipe(
      map((results) => results.results.pop())
    )
  }

  listFiltered(
    page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    filterRules?: FilterRule[],
    extraParams = {},
    parentStoragePathId?: number
  ): Observable<
    Results<PaperlessStoragePath> & { parentStoragePath?: PaperlessStoragePath }
  > {
    const params = Object.assign(
      extraParams,
      queryParamsFromFilterRules(filterRules)
    )
    if (parentStoragePathId !== null && parentStoragePathId !== undefined) {
      return this.get(parentStoragePathId).pipe(
        switchMap((storagePath) => {
          params.path__istartswith = storagePath.path
          return this.list(page, pageSize, sortField, sortReverse, params).pipe(
            map((results) => {
              results.results = results.results.filter((s) => {
                const isNotParent = s.id !== parentStoragePathId
                const isDirectChild =
                  s.path
                    .replace(storagePath.path, '')
                    .split('/')
                    .filter((s) => !!s).length === 1
                return isNotParent && isDirectChild
              })
              // @ts-ignore
              results.parentStoragePath = storagePath
              return results
            })
          )
        })
      )
    }

    return this.list(page, pageSize, sortField, sortReverse, params).pipe(
      map((results) => {
        results.results = results.results.filter(
          (s) => s.path.split('/').length === 1
        )
        return results
      })
    )
  }

  listAllFilteredIds(filterRules?: FilterRule[]): Observable<number[]> {
    return this.listFiltered(1, 100000, null, null, filterRules, {
      fields: 'id',
    }).pipe(map((response) => response.results.map((doc) => doc.id)))
  }
}
