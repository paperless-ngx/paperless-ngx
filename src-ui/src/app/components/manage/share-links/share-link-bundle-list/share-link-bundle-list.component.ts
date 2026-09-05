import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
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
import { ConfirmButtonComponent } from 'src/app/components/common/confirm-button/confirm-button.component'
import { LoadingComponentWithPermissions } from 'src/app/components/loading-component/loading.component'

@Component({
  selector: 'pngx-share-link-bundle-list',
  templateUrl: './share-link-bundle-list.component.html',
  styleUrls: ['./share-link-bundle-list.component.scss'],
  imports: [
    ConfirmButtonComponent,
    CommonModule,
    NgbPopoverModule,
    NgxBootstrapIconsModule,
    FileSizePipe,
  ],
})
export class ShareLinkBundleListComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private readonly shareLinkBundleService = inject(ShareLinkBundleService)
  private readonly toastService = inject(ToastService)
  private readonly clipboard = inject(Clipboard)

  readonly bundles = signal<ShareLinkBundleSummary[]>([])
  readonly error = signal<string | null>(null)
  readonly copiedSlug = signal<string | null>(null)

  readonly statuses = ShareLinkBundleStatus
  readonly fileVersions = FileVersion

  private readonly refresh$ = new Subject<boolean>()

  ngOnInit(): void {
    this.refresh$
      .pipe(
        switchMap((silent) => {
          if (!silent) {
            this.loading.set(true)
          }
          this.error.set(null)
          return this.shareLinkBundleService.listAllBundles().pipe(
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
          this.bundles.set(results)
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
