import { Injectable } from '@angular/core'
import {
  PaperlessShareLink,
  PaperlessFileVersion,
} from 'src/app/data/paperless-share-link'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { HttpClient } from '@angular/common/http'
import { Observable } from 'rxjs'

@Injectable({
  providedIn: 'root',
})
export class ShareLinkService extends AbstractNameFilterService<PaperlessShareLink> {
  constructor(http: HttpClient) {
    super(http, 'share_links')
  }

  getLinksForDocument(documentId: number): Observable<PaperlessShareLink[]> {
    return this.http.get<PaperlessShareLink[]>(
      `${this.baseUrl}documents/${documentId}/${this.resourceName}/`
    )
  }

  createLinkForDocument(
    documentId: number,
    file_version: PaperlessFileVersion = PaperlessFileVersion.Archive,
    expiration: Date = null
  ) {
    this.clearCache()
    return this.http.post<PaperlessShareLink>(this.getResourceUrl(), {
      document: documentId,
      file_version,
      expiration: expiration?.toISOString(),
    })
  }
}
