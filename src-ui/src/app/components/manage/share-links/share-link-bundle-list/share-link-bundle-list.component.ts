import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import {
  NgbPaginationModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, catchError, of, switchMap, takeUntil, timer } from 'rxjs'
import { FileVersion } from 'src/app/data/share-link'
import {
  SHARE_LINK_BUNDLE_FILE_VERSION_LABELS,
  SHARE_LINK_BUNDLE_STATUS_LABELS,
  ShareLinkBundleStatus,
  ShareLinkBundleSummary,
} from 'src/app/data/share-link-bundle'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import {
  SortEvent,
  SortableDirective,
} from 'src/app/directives/sortable.directive'
import { FileSizePipe } from 'src/app/pipes/file-size.pipe'
import { ShareLinkBundleService } from 'src/app/services/rest/share-link-bundle.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ConfirmButtonComponent } from 'src/app/components/common/confirm-button/confirm-button.component'
import { LoadingComponentWithPermissions } from 'src/app/components/loading-component/loading.component'

@Component({
  selector: 'pngx-share-link-bundle-list',
  templateUrl: './share-link-bundle-list.component.html',
  styleUrls: ['./share-link-bundle-list.component.scss'],
  imports: [
    ConfirmButtonComponent,
    CommonModule,
    FormsModule,
    NgbPaginationModule,
    NgbPopoverModule,
    NgxBootstrapIconsModule,
    SortableDirective,
    FileSizePipe,
  ],
})
export class ShareLinkBundleListComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private readonly shareLinkBundleService = inject(ShareLinkBundleService)
  private readonly settingsService = inject(SettingsService)
  private readonly toastService = inject(ToastService)
  private readonly clipboard = inject(Clipboard)

  readonly bundles = signal<ShareLinkBundleSummary[]>([])
  readonly error = signal<string | null>(null)
  readonly copiedSlug = signal<string | null>(null)
  readonly total = signal(0)
  readonly page = signal(1)
  readonly sortField = signal('created')
  readonly sortReverse = signal(true)

  readonly statuses = ShareLinkBundleStatus
  readonly fileVersions = FileVersion

  get pageSize(): number {
    return (
      this.settingsService.get(SETTINGS_KEYS.OBJECT_LIST_SIZES)
        ?.share_link_bundles || 25
    )
  }

  set pageSize(pageSize: number) {
    this.settingsService.set(SETTINGS_KEYS.OBJECT_LIST_SIZES, {
      ...this.settingsService.get(SETTINGS_KEYS.OBJECT_LIST_SIZES),
      share_link_bundles: pageSize,
    })
    this.settingsService.storeSettings().subscribe({
      next: () => {
        this.page.set(1)
        this.triggerRefresh(false)
      },
      error: (error) => {
        this.toastService.showError($localize`Error saving settings`, error)
      },
    })
  }

  private readonly refresh$ = new Subject<boolean>()

  ngOnInit(): void {
    this.refresh$
      .pipe(
        switchMap((silent) => {
          if (!silent) {
            this.loading.set(true)
          }
          this.error.set(null)
          return this.shareLinkBundleService
            .list(
              this.page(),
              this.pageSize,
              this.sortField(),
              this.sortReverse()
            )
            .pipe(
              catchError((error) => {
                if (!silent) {
                  this.loading.set(false)
                }
                this.error.set($localize`Failed to load share link bundles.`)
                this.toastService.showError(
                  $localize`Error retrieving share link bundles.`,
                  error
                )
                return of(null)
              })
            )
        }),
        takeUntil(this.unsubscribeNotifier)
      )
      .subscribe((results) => {
        if (results) {
          this.bundles.set(results.results)
          this.total.set(results.count)
          this.copiedSlug.set(null)
        }
        this.loading.set(false)
      })

    this.triggerRefresh(false)
    timer(5000, 5000)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.triggerRefresh(true))
  }

  ngOnDestroy(): void {
    super.ngOnDestroy()
  }

  getShareUrl(bundle: ShareLinkBundleSummary): string {
    const apiURL = new URL(environment.apiBaseUrl)
    return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${
      bundle.slug
    }`
  }

  setPage(page: number): void {
    this.page.set(page)
    this.triggerRefresh(false)
  }

  onSort(event: SortEvent): void {
    this.sortField.set(event.column || 'created')
    this.sortReverse.set(event.column ? event.reverse : true)
    this.page.set(1)
    this.triggerRefresh(false)
  }

  copy(bundle: ShareLinkBundleSummary): void {
    if (bundle.status !== ShareLinkBundleStatus.Ready) {
      return
    }
    const success = this.clipboard.copy(this.getShareUrl(bundle))
    if (success) {
      this.copiedSlug.set(bundle.slug)
      setTimeout(() => {
        this.copiedSlug.set(null)
      }, 3000)
    }
  }

  delete(bundle: ShareLinkBundleSummary): void {
    this.error.set(null)
    this.loading.set(true)
    this.shareLinkBundleService.delete(bundle).subscribe({
      next: () => {
        if (this.bundles().length === 1 && this.page() > 1) {
          this.page.update((page) => page - 1)
        }
        this.toastService.showInfo($localize`Share link bundle deleted.`)
        this.triggerRefresh(false)
      },
      error: (e) => {
        this.loading.set(false)
        this.toastService.showError(
          $localize`Error deleting share link bundle.`,
          e
        )
      },
    })
  }

  retry(bundle: ShareLinkBundleSummary): void {
    this.error.set(null)
    this.shareLinkBundleService.rebuildBundle(bundle.id).subscribe({
      next: (updated) => {
        this.toastService.showInfo(
          $localize`Share link bundle rebuild requested.`
        )
        this.replaceBundle(updated)
      },
      error: (e) => {
        this.toastService.showError($localize`Error requesting rebuild.`, e)
      },
    })
  }

  statusLabel(status: ShareLinkBundleStatus): string {
    return SHARE_LINK_BUNDLE_STATUS_LABELS[status] ?? status
  }

  fileVersionLabel(version: FileVersion): string {
    return SHARE_LINK_BUNDLE_FILE_VERSION_LABELS[version] ?? version
  }

  isExpired(expiration?: string): boolean {
    return !!expiration && Date.parse(expiration) <= Date.now()
  }

  private replaceBundle(updated: ShareLinkBundleSummary): void {
    const bundles = this.bundles()
    const index = bundles.findIndex((bundle) => bundle.id === updated.id)
    if (index >= 0) {
      this.bundles.set([
        ...bundles.slice(0, index),
        updated,
        ...bundles.slice(index + 1),
      ])
    } else {
      this.bundles.set([updated, ...bundles])
    }
  }

  private triggerRefresh(silent: boolean): void {
    this.refresh$.next(silent)
  }
}
