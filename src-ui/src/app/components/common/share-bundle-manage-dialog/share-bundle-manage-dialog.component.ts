import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, OnInit, inject } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { first } from 'rxjs'
import { ShareBundleSummary } from 'src/app/data/share-bundle'
import { ShareBundleService } from 'src/app/services/rest/share-bundle.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-share-bundle-manage-dialog',
  templateUrl: './share-bundle-manage-dialog.component.html',
  standalone: true,
  imports: [CommonModule, NgxBootstrapIconsModule],
})
export class ShareBundleManageDialogComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  private activeModal = inject(NgbActiveModal)
  private shareBundleService = inject(ShareBundleService)
  private toastService = inject(ToastService)
  private clipboard = inject(Clipboard)

  title = $localize`Bulk Share Links`

  bundles: ShareBundleSummary[] = []
  error: string
  copiedSlug: string

  ngOnInit(): void {
    this.fetchBundles()
  }

  fetchBundles(): void {
    this.loading = true
    this.error = null
    this.shareBundleService
      .listAllBundles()
      .pipe(first())
      .subscribe({
        next: (results) => {
          this.bundles = results
          this.loading = false
        },
        error: (e) => {
          this.loading = false
          this.error = $localize`Failed to load bulk share links.`
          this.toastService.showError(
            $localize`Error retrieving bulk share links.`,
            e
          )
        },
      })
  }

  getShareUrl(bundle: ShareBundleSummary): string {
    const apiURL = new URL(environment.apiBaseUrl)
    return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${
      bundle.slug
    }`
  }

  copy(bundle: ShareBundleSummary): void {
    const success = this.clipboard.copy(this.getShareUrl(bundle))
    if (success) {
      this.copiedSlug = bundle.slug
      setTimeout(() => {
        this.copiedSlug = null
      }, 3000)
    }
  }

  delete(bundle: ShareBundleSummary): void {
    this.shareBundleService.delete(bundle).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Bulk share link deleted.`)
        this.fetchBundles()
      },
      error: (e) => {
        this.toastService.showError(
          $localize`Error deleting bulk share link.`,
          e
        )
      },
    })
  }

  close(): void {
    this.activeModal.close()
  }
}
