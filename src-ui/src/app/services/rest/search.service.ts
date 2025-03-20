import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { Correspondent } from 'src/app/data/correspondent'
import { CustomField } from 'src/app/data/custom-field'
import { Document } from 'src/app/data/document'
import { DocumentType } from 'src/app/data/document-type'
import { Group } from 'src/app/data/group'
import { MailAccount } from 'src/app/data/mail-account'
import { MailRule } from 'src/app/data/mail-rule'
import { SavedView } from 'src/app/data/saved-view'
import { StoragePath } from 'src/app/data/storage-path'
import { Tag } from 'src/app/data/tag'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { User } from 'src/app/data/user'
import { Workflow } from 'src/app/data/workflow'
import { environment } from 'src/environments/environment'
import { SettingsService } from '../settings.service'

export interface GlobalSearchResult {
  total: number
  documents: Document[]
  saved_views: SavedView[]
  correspondents: Correspondent[]
  document_types: DocumentType[]
  storage_paths: StoragePath[]
  tags: Tag[]
  users: User[]
  groups: Group[]
  mail_accounts: MailAccount[]
  mail_rules: MailRule[]
  custom_fields: CustomField[]
  workflows: Workflow[]
}

@Injectable({
  providedIn: 'root',
})
export class SearchService {
  public readonly searchResultObjectLimit: number = 3 // documents/views.py GlobalSearchView > OBJECT_LIMIT

  constructor(
    private http: HttpClient,
    private settingsService: SettingsService
  ) {}

  autocomplete(term: string): Observable<string[]> {
    return this.http.get<string[]>(
      `${environment.apiBaseUrl}search/autocomplete/`,
      { params: new HttpParams().set('term', term) }
    )
  }

  globalSearch(query: string): Observable<GlobalSearchResult> {
    let params = new HttpParams().set('query', query)
    if (this.searchDbOnly) {
      params = params.set('db_only', true)
    }
    return this.http.get<GlobalSearchResult>(
      `${environment.apiBaseUrl}search/`,
      { params }
    )
  }

  public get searchDbOnly(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.SEARCH_DB_ONLY)
  }
}
