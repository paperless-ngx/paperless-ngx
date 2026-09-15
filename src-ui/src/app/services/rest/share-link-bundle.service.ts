import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import {
  ShareLinkBundleCreatePayload,
  ShareLinkBundleSummary,
} from 'src/app/data/share-link-bundle'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class ShareLinkBundleService extends AbstractNameFilterService<ShareLinkBundleSummary> {
  constructor() {
    super()
    this.resourceName = 'share_link_bundles'
  }

  createBundle(
    payload: ShareLinkBundleCreatePayload
  ): Observable<ShareLinkBundleSummary> {
    this.clearCache()
    return this.http.post<ShareLinkBundleSummary>(
      this.getResourceUrl(),
      payload
    )
  }
  rebuildBundle(bundleId: number): Observable<ShareLinkBundleSummary> {
    this.clearCache()
    return this.http.post<ShareLinkBundleSummary>(
      this.getResourceUrl(bundleId, 'rebuild'),
      {}
    )
  }
}
