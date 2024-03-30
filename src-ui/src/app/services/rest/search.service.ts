import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { Document } from 'src/app/data/document'
import { DocumentType } from 'src/app/data/document-type'
import { Correspondent } from 'src/app/data/correspondent'
import { CustomField } from 'src/app/data/custom-field'
import { Group } from 'src/app/data/group'
import { MailAccount } from 'src/app/data/mail-account'
import { MailRule } from 'src/app/data/mail-rule'
import { StoragePath } from 'src/app/data/storage-path'
import { Tag } from 'src/app/data/tag'
import { User } from 'src/app/data/user'
import { Workflow } from 'src/app/data/workflow'

export interface GlobalSearchResult {
  total: number
  documents: Document[]
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
  constructor(private http: HttpClient) {}

  autocomplete(term: string): Observable<string[]> {
    return this.http.get<string[]>(
      `${environment.apiBaseUrl}search/autocomplete/`,
      { params: new HttpParams().set('term', term) }
    )
  }

  globalSearch(query: string): Observable<GlobalSearchResult> {
    return this.http.get<GlobalSearchResult>(
      `${environment.apiBaseUrl}search/`,
      { params: new HttpParams().set('query', query) }
    )
  }
}
