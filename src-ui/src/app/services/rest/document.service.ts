import { Injectable } from '@angular/core'
import { Document } from 'src/app/data/document'
import { DocumentMetadata } from 'src/app/data/document-metadata'
import { AbstractEdocService } from './abstract-edoc-service'
import { HttpClient } from '@angular/common/http'
import { Observable } from 'rxjs'
import { Results } from 'src/app/data/results'
import { FilterRule } from 'src/app/data/filter-rule'
import { map, tap } from 'rxjs/operators'
import { CorrespondentService } from './correspondent.service'
import { DocumentTypeService } from './document-type.service'
import { ArchiveFontService } from './archive-font.service'
import { TagService } from './tag.service'
import { DocumentSuggestions } from 'src/app/data/document-suggestions'
import { queryParamsFromFilterRules } from '../../utils/query-params'
import { StoragePathService } from './storage-path.service'



import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from '../permissions.service'
import { SettingsService } from '../settings.service'
import { SETTINGS, SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { WarehouseService } from './warehouse.service'

export const DOCUMENT_SORT_FIELDS = [
  { field: 'archive_serial_number', name: $localize`ASN` },
  // { field: 'correspondent__name', name: $localize`Correspondent` },
  { field: 'title', name: $localize`Title` },
  { field: 'document_type__name', name: $localize`Document type` },
  { field: 'warehouse__name', name: $localize`Warehouse` },
  { field: 'created', name: $localize`Created` },
  { field: 'added', name: $localize`Added` },
  { field: 'modified', name: $localize`Modified` },
  { field: 'num_notes', name: $localize`Notes` },
  { field: 'owner', name: $localize`Owner` },
]

export const DOCUMENT_SORT_FIELDS_FULLTEXT = [
  ...DOCUMENT_SORT_FIELDS,
  // {
  //   field: 'score',
  //   name: $localize`:Score is a value returned by the full text search engine and specifies how well a result matches the given query:Search score`,
  // },
]

export interface SelectionDataItem {
  id: number
  document_count: number
}

export interface SelectionData {
  selected_storage_paths: SelectionDataItem[]
  selected_correspondents: SelectionDataItem[]
  selected_tags: SelectionDataItem[]
  selected_document_types: SelectionDataItem[]
  selected_archive_fonts: SelectionDataItem[]
  selected_warehouses: SelectionDataItem[]
  selected_shelfs: SelectionDataItem[]
  selected_boxcases: SelectionDataItem[]


}

@Injectable({
  providedIn: 'root',
})
export class DocumentService extends AbstractEdocService<Document> {
  private _searchQuery: string

  constructor(
    http: HttpClient,
    private correspondentService: CorrespondentService,
    private documentTypeService: DocumentTypeService,
    private archiveFontService: ArchiveFontService,
    private tagService: TagService,
    private storagePathService: StoragePathService,
    private warehouseService: WarehouseService,
    private permissionsService: PermissionsService,
    private settingsService: SettingsService
  ) {
    super(http, 'documents')
  }

  addObservablesToDocument(doc: Document) {
    if (
      doc.correspondent &&
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Correspondent
      )
    ) {
      doc.correspondent$ = this.correspondentService.getCached(
        doc.correspondent
      )
    }
    if (
      doc.document_type &&
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.DocumentType
      )
    ) {
      doc.document_type$ = this.documentTypeService.getCached(doc.document_type)
    }
    if (
      doc.archive_font &&
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.ArchiveFont
      )
    ) {
      doc.archive_font$ = this.archiveFontService.getCached(doc.archive_font)
    }
    if (
      doc.tags &&
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Tag
      )
    ) {
      doc.tags$ = this.tagService
        .getCachedMany(doc.tags)
        .pipe(
          tap((tags) =>
            tags.sort((tagA, tagB) => tagA.name.localeCompare(tagB.name))
          )
        )
    }
    if (
      doc.storage_path &&
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.StoragePath
      )
    ) {
      doc.storage_path$ = this.storagePathService.getCached(doc.storage_path)
    }
    if (
      doc.warehouse &&
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Warehouse
      )
    ) {
      doc.warehouse$ = this.warehouseService.getCached(doc.warehouse)
    }
    return doc
  }

  listFiltered(
    page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    filterRules?: FilterRule[],
    extraParams = {}
  ): Observable<Results<Document>> {
    return this.list(
      page,
      pageSize,
      sortField,
      sortReverse,
      Object.assign(extraParams, queryParamsFromFilterRules(filterRules))
    ).pipe(
      map((results) => {
        results.results.forEach((doc) => this.addObservablesToDocument(doc))
        return results
      })
    )
  }

  listAllFilteredIds(filterRules?: FilterRule[]): Observable<number[]> {
    return this.listFiltered(1, 100000, null, null, filterRules, {
      fields: 'id',
    }).pipe(map((response) => response.results.map((doc) => doc.id)))
  }

  get(id: number): Observable<Document> {
    return this.http.get<Document>(this.getResourceUrl(id), {
      params: {
        full_perms: true,
      },
    })
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
  getDownloadExcel(id: number): string {
    let url = this.getResourceUrl(id, 'export_excel')
    return url
  }

  getNextAsn(): Observable<number> {
    return this.http.get<number>(this.getResourceUrl(null, 'next_asn'))
  }

  update(o: Document): Observable<Document> {
    // we want to only set created_date
    o.created = undefined
    o.remove_inbox_tags = !!this.settingsService.get(
      SETTINGS_KEYS.DOCUMENT_EDITING_REMOVE_INBOX_TAGS
    )
    return super.update(o)
  }

  uploadDocument(formData) {
    return this.http.post(
      this.getResourceUrl(null, 'post_document'),
      formData,
      { reportProgress: true, observe: 'events' }
    )
  }

  getMetadata(id: number): Observable<DocumentMetadata> {
    return this.http.get<DocumentMetadata>(this.getResourceUrl(id, 'metadata'))
  }

  bulkEdit(ids: number[], method: string, args: any) {
    return this.http.post(this.getResourceUrl(null, 'bulk_edit'), {
      documents: ids,
      method: method,
      parameters: args,
    })
  }

  getSelectionData(ids: number[]): Observable<SelectionData> {
    return this.http.post<SelectionData>(
      this.getResourceUrl(null, 'selection_data'),
      { documents: ids }
    )
  }

  getSuggestions(id: number): Observable<DocumentSuggestions> {
    return this.http.get<DocumentSuggestions>(
      this.getResourceUrl(id, 'suggestions')
    )
  }

  bulkExportExcels(
    ids: number[]
  ) {
    return this.http.post(
      this.getResourceUrl(null, 'bulk_export_excel'),
      {
        documents: ids,
      },
      { responseType: 'blob' }
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

