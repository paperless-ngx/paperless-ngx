import { Injectable } from '@angular/core'
import { ShareLink, FileVersion } from 'src/app/data/share-link'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { HttpClient } from '@angular/common/http'
import { Observable } from 'rxjs'

@Injectable({
  providedIn: 'root',
})
export class ShareLinkService extends AbstractNameFilterService<ShareLink> {
  constructor(http: HttpClient) {
    super(http, 'share_links')
  }

  getLinksForDocument(documentId: number): Observable<ShareLink[]> {
    return this.http.get<ShareLink[]>(
      `${this.baseUrl}documents/${documentId}/${this.resourceName}/`
    )
  }

  createLinkForDocument(
    documentId: number,
    file_version: FileVersion = FileVersion.Archive,
    expiration: Date = null
  ) {
    this.clearCache()
    return this.http.post<ShareLink>(this.getResourceUrl(), {
      document: documentId,
      file_version,
      expiration: expiration?.toISOString(),
    })
  }
}
