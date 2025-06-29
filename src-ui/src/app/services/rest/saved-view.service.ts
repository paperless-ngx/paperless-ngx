import { HttpClient } from '@angular/common/http'
import { inject, Injectable } from '@angular/core'
import { combineLatest, Observable } from 'rxjs'
import { tap } from 'rxjs/operators'
import { Results } from 'src/app/data/results'
import { SavedView } from 'src/app/data/saved-view'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from '../settings.service'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class SavedViewService extends AbstractPaperlessService<SavedView> {
  protected http: HttpClient
  private settingsService = inject(SettingsService)

  public loading: boolean = true
  private savedViews: SavedView[] = []

  constructor() {
    super()
    this.resourceName = 'saved_views'
  }

  public list(
    page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    extraParams?: any
  ): Observable<Results<SavedView>> {
    return super.list(page, pageSize, sortField, sortReverse, extraParams).pipe(
      tap({
        next: (r) => {
          this.savedViews = r.results
          this.loading = false
          this.settingsService.dashboardIsEmpty =
            this.dashboardViews.length === 0
        },
        error: () => {
          this.loading = false
          this.settingsService.dashboardIsEmpty = true
        },
      })
    )
  }

  public reload() {
    this.listAll().subscribe()
  }

  get allViews() {
    return this.savedViews
  }

  get sidebarViews(): SavedView[] {
    const sidebarViews = this.savedViews.filter((v) => v.show_in_sidebar)

    const sorted: number[] = this.settingsService.get(
      SETTINGS_KEYS.SIDEBAR_VIEWS_SORT_ORDER
    )

    return sorted?.length > 0
      ? sorted
          .map((id) => sidebarViews.find((v) => v.id === id))
          .concat(sidebarViews.filter((v) => !sorted.includes(v.id)))
          .filter((v) => v)
      : [...sidebarViews]
  }

  get dashboardViews(): SavedView[] {
    const dashboardViews = this.savedViews.filter((v) => v.show_on_dashboard)

    const sorted: number[] = this.settingsService.get(
      SETTINGS_KEYS.DASHBOARD_VIEWS_SORT_ORDER
    )

    return sorted?.length > 0
      ? sorted
          .map((id) => dashboardViews.find((v) => v.id === id))
          .concat(dashboardViews.filter((v) => !sorted.includes(v.id)))
          .filter((v) => v)
      : [...dashboardViews]
  }

  create(o: SavedView) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  patch(o: SavedView, reload: boolean = false): Observable<SavedView> {
    if (o.display_fields?.length === 0) {
      o.display_fields = null
    }
    return super.patch(o).pipe(
      tap(() => {
        if (reload) {
          this.reload()
        }
      })
    )
  }

  patchMany(objects: SavedView[]): Observable<SavedView[]> {
    return combineLatest(objects.map((o) => this.patch(o, false))).pipe(
      tap(() => this.reload())
    )
  }

  delete(o: SavedView) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
