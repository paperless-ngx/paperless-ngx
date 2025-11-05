import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, OnDestroy, OnInit, inject } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, catchError, of, switchMap, takeUntil, timer } from 'rxjs'
import {
  SHARE_BUNDLE_FILE_VERSION_LABELS,
  SHARE_BUNDLE_STATUS_LABELS,
  ShareBundleStatus,
  ShareBundleSummary,
} from 'src/app/data/share-bundle'
import { FileVersion } from 'src/app/data/share-link'
import { FileSizePipe } from 'src/app/pipes/file-size.pipe'
import { ShareBundleService } from 'src/app/services/rest/share-bundle.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-share-bundle-manage-dialog',
  templateUrl: './share-bundle-manage-dialog.component.html',
  imports: [CommonModule, NgxBootstrapIconsModule, FileSizePipe],
})
export class ShareBundleManageDialogComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private activeModal = inject(NgbActiveModal)
  private shareBundleService = inject(ShareBundleService)
  private toastService = inject(ToastService)
  private clipboard = inject(Clipboard)

  title = $localize`Bulk Share Links`

  bundles: ShareBundleSummary[] = []
  error: string | null = null
  copiedSlug: string | null = null

  readonly statuses = ShareBundleStatus
  readonly fileVersions = FileVersion

  private readonly refresh$ = new Subject<boolean>()

  ngOnInit(): void {
    this.refresh$
      .pipe(
        switchMap((silent) => {
          if (!silent) {
            this.loading = true
          }
          this.error = null
          return this.shareBundleService.listAllBundles().pipe(
            catchError((error) => {
              if (!silent) {
                this.loading = false
              }
              this.error = $localize`Failed to load bulk share links.`
              this.toastService.showError(
                $localize`Error retrieving bulk share links.`,
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
          this.bundles = results
          this.copiedSlug = null
        }
        this.loading = false
      })

    this.triggerRefresh(false)
    timer(5000, 5000)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.triggerRefresh(true))
  }

  ngOnDestroy(): void {
    super.ngOnDestroy()
  }

  getShareUrl(bundle: ShareBundleSummary): string {
    const apiURL = new URL(environment.apiBaseUrl)
    return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${
      bundle.slug
    }`
  }

  copy(bundle: ShareBundleSummary): void {
    if (bundle.status !== ShareBundleStatus.Ready) {
      return
    }
    const success = this.clipboard.copy(this.getShareUrl(bundle))
    if (success) {
      this.copiedSlug = bundle.slug
      setTimeout(() => {
        this.copiedSlug = null
      }, 3000)
      this.toastService.showInfo($localize`Share link copied to clipboard.`)
    }
  }

  delete(bundle: ShareBundleSummary): void {
    this.error = null
    this.loading = true
    this.shareBundleService.delete(bundle).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Bulk share link deleted.`)
        this.triggerRefresh(false)
      },
      error: (e) => {
        this.loading = false
        this.toastService.showError(
          $localize`Error deleting bulk share link.`,
          e
        )
      },
    })
  }

  retry(bundle: ShareBundleSummary): void {
    this.error = null
    this.shareBundleService.rebuildBundle(bundle.id).subscribe({
      next: (updated) => {
        this.toastService.showInfo(
          $localize`Bulk share link rebuild requested.`
        )
        this.replaceBundle(updated)
      },
      error: (e) => {
        this.toastService.showError($localize`Error requesting rebuild.`, e)
      },
    })
  }

  statusLabel(status: ShareBundleStatus): string {
    return SHARE_BUNDLE_STATUS_LABELS[status] ?? status
  }

  fileVersionLabel(version: FileVersion): string {
    return SHARE_BUNDLE_FILE_VERSION_LABELS[version] ?? version
  }

  close(): void {
    this.activeModal.close()
  }

  private replaceBundle(updated: ShareBundleSummary): void {
    const index = this.bundles.findIndex((bundle) => bundle.id === updated.id)
    if (index >= 0) {
      this.bundles = [
        ...this.bundles.slice(0, index),
        updated,
        ...this.bundles.slice(index + 1),
      ]
    } else {
      this.bundles = [updated, ...this.bundles]
    }
  }

  private triggerRefresh(silent: boolean): void {
    this.refresh$.next(silent)
  }
}
