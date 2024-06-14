import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { combineLatest, Observable } from 'rxjs'
import { tap } from 'rxjs/operators'
import { SavedView } from 'src/app/data/saved-view'
import { PermissionsService } from '../permissions.service'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { SettingsService } from '../settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'

@Injectable({
  providedIn: 'root',
})
export class SavedViewService extends AbstractPaperlessService<SavedView> {
  loading: boolean

  constructor(
    http: HttpClient,
    permissionService: PermissionsService,
    private settingsService: SettingsService
  ) {
    super(http, 'saved_views')
  }

  public initialize() {
    this.reload()
  }

  private reload() {
    this.loading = true
    this.listAll().subscribe((r) => {
      this.savedViews = r.results
      this.loading = false
      this.settingsService.dashboardIsEmpty = this.dashboardViews.length === 0
    })
  }

  private savedViews: SavedView[] = []

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

  update(o: SavedView) {
    return super.update(o).pipe(tap(() => this.reload()))
  }

  patchMany(objects: SavedView[]): Observable<SavedView[]> {
    return combineLatest(objects.map((o) => super.patch(o))).pipe(
      tap(() => this.reload())
    )
  }

  delete(o: SavedView) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
