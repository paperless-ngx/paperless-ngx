import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { map } from 'rxjs/operators'
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

  listAllBundles(): Observable<ShareBundleSummary[]> {
    return this.list(1, 1000, 'created', true).pipe(
      map((response) => response.results)
    )
  }
}
