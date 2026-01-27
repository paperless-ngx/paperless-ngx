import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, OnDestroy, OnInit, inject } from '@angular/core'
import { NgbActiveModal, NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, catchError, of, switchMap, takeUntil, timer } from 'rxjs'
import { FileVersion } from 'src/app/data/share-link'
import {
  SHARE_LINK_BUNDLE_FILE_VERSION_LABELS,
  SHARE_LINK_BUNDLE_STATUS_LABELS,
  ShareLinkBundleStatus,
  ShareLinkBundleSummary,
} from 'src/app/data/share-link-bundle'
import { FileSizePipe } from 'src/app/pipes/file-size.pipe'
import { ShareLinkBundleService } from 'src/app/services/rest/share-link-bundle.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
import { ConfirmButtonComponent } from '../confirm-button/confirm-button.component'

@Component({
  selector: 'pngx-share-link-bundle-manage-dialog',
  templateUrl: './share-link-bundle-manage-dialog.component.html',
  styleUrls: ['./share-link-bundle-manage-dialog.component.scss'],
  imports: [
    ConfirmButtonComponent,
    CommonModule,
    NgbPopoverModule,
    NgxBootstrapIconsModule,
    FileSizePipe,
  ],
})
export class ShareLinkBundleManageDialogComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private readonly activeModal = inject(NgbActiveModal)
  private readonly shareLinkBundleService = inject(ShareLinkBundleService)
  private readonly toastService = inject(ToastService)
  private readonly clipboard = inject(Clipboard)

  title = $localize`Share link bundles`

  bundles: ShareLinkBundleSummary[] = []
  error: string | null = null
  copiedSlug: string | null = null

  readonly statuses = ShareLinkBundleStatus
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
          return this.shareLinkBundleService.listAllBundles().pipe(
            catchError((error) => {
              if (!silent) {
                this.loading = false
              }
              this.error = $localize`Failed to load share link bundles.`
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

  getShareUrl(bundle: ShareLinkBundleSummary): string {
    const apiURL = new URL(environment.apiBaseUrl)
    return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${
      bundle.slug
    }`
  }

  copy(bundle: ShareLinkBundleSummary): void {
    if (bundle.status !== ShareLinkBundleStatus.Ready) {
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

  delete(bundle: ShareLinkBundleSummary): void {
    this.error = null
    this.loading = true
    this.shareLinkBundleService.delete(bundle).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Share link bundle deleted.`)
        this.triggerRefresh(false)
      },
      error: (e) => {
        this.loading = false
        this.toastService.showError(
          $localize`Error deleting share link bundle.`,
          e
        )
      },
    })
  }

  retry(bundle: ShareLinkBundleSummary): void {
    this.error = null
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

  close(): void {
    this.activeModal.close()
  }

  private replaceBundle(updated: ShareLinkBundleSummary): void {
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
