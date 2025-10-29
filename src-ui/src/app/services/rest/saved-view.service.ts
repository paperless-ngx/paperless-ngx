import { HttpClient } from '@angular/common/http'
import { inject, Injectable } from '@angular/core'
import { combineLatest, Observable, Subject } from 'rxjs'
import { takeUntil, tap } from 'rxjs/operators'
import { Results } from 'src/app/data/results'
import { SavedView } from 'src/app/data/saved-view'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from '../settings.service'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { DocumentService } from './document.service'

@Injectable({
  providedIn: 'root',
})
export class SavedViewService extends AbstractPaperlessService<SavedView> {
  protected http: HttpClient
  private settingsService = inject(SettingsService)
  private documentService = inject(DocumentService)

  private savedViews: SavedView[] = []
  private savedViewDocumentCounts: Map<number, number> = new Map()
  private unsubscribeNotifier: Subject<void> = new Subject<void>()

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
          this._loading = false
          this.settingsService.dashboardIsEmpty =
            this.dashboardViews.length === 0
        },
        error: () => {
          this._loading = false
          this.settingsService.dashboardIsEmpty = true
        },
      })
    )
  }

  public reload(callback: any = null) {
    this.listAll()
      .pipe(
        tap((r) => {
          if (callback) {
            callback(r)
          }
        })
      )
      .subscribe()
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

  public maybeRefreshDocumentCounts(views: SavedView[] = this.sidebarViews) {
    if (!this.settingsService.get(SETTINGS_KEYS.SIDEBAR_VIEWS_SHOW_COUNT)) {
      return
    }
    this.unsubscribeNotifier.next() // clear previous subscriptions
    views.forEach((view) => {
      this.documentService
        .listFiltered(
          1,
          1,
          view.sort_field,
          view.sort_reverse,
          view.filter_rules,
          { fields: 'id', truncate_content: true }
        )
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe((results: Results<Document>) => {
          this.setDocumentCount(view, results.count)
        })
    })
  }

  public setDocumentCount(view: SavedView, count: number) {
    this.savedViewDocumentCounts.set(view.id, count)
  }

  public getDocumentCount(view: SavedView): number {
    return this.savedViewDocumentCounts.get(view.id)
  }
}
