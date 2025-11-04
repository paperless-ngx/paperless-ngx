import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import {
  ShareBundleCreatePayload,
  ShareBundleSummary,
} from 'src/app/data/share-bundle'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class ShareBundleService extends AbstractNameFilterService<ShareBundleSummary> {
  constructor() {
    super()
    this.resourceName = 'share_bundles'
  }

  createBundle(
    payload: ShareBundleCreatePayload
  ): Observable<ShareBundleSummary> {
    this.clearCache()
    return this.http.post<ShareBundleSummary>(this.getResourceUrl(), payload)
  }

  listBundlesForDocuments(
    documentIds: number[]
  ): Observable<ShareBundleSummary[]> {
    const params = { documents: documentIds.join(',') }
    return this.http.get<ShareBundleSummary[]>(this.getResourceUrl(), {
      params,
    })
  }
}
