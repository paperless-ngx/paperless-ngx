import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, OnInit, inject, signal } from '@angular/core'
import { RouterModule } from '@angular/router'
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { takeUntil } from 'rxjs'
import { ConfirmButtonComponent } from 'src/app/components/common/confirm-button/confirm-button.component'
import { LoadingComponentWithPermissions } from 'src/app/components/loading-component/loading.component'
import { FileVersion, ShareLink } from 'src/app/data/share-link'
import { SHARE_LINK_BUNDLE_FILE_VERSION_LABELS } from 'src/app/data/share-link-bundle'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  PermissionAction,
  PermissionType,
} from 'src/app/services/permissions.service'
import { ShareLinkService } from 'src/app/services/rest/share-link.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-share-link-list',
  templateUrl: './share-link-list.component.html',
  imports: [
    CommonModule,
    ConfirmButtonComponent,
    IfPermissionsDirective,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
    RouterModule,
  ],
})
export class ShareLinkListComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  private readonly clipboard = inject(Clipboard)
  private readonly shareLinkService = inject(ShareLinkService)
  private readonly toastService = inject(ToastService)

  readonly links = signal<ShareLink[]>([])
  readonly total = signal(0)
  readonly page = signal(1)
  readonly copiedID = signal<number | null>(null)
  readonly error = signal<string | null>(null)
  readonly pageSize = 25
  readonly PermissionAction = PermissionAction
  readonly PermissionType = PermissionType

  ngOnInit(): void {
    this.reload()
  }

  reload(): void {
    this.loading.set(true)
    this.error.set(null)
    this.shareLinkService
      .list(this.page(), this.pageSize, 'created', true)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (results) => {
          this.links.set(results.results)
          this.total.set(results.count)
          this.loading.set(false)
        },
        error: (error) => {
          this.loading.set(false)
          this.error.set($localize`Failed to load share links.`)
          this.toastService.showError(
            $localize`Error retrieving share links.`,
            error
          )
        },
      })
  }

  setPage(page: number): void {
    this.page.set(page)
    this.reload()
  }

  getShareUrl(link: ShareLink): string {
    const apiURL = new URL(environment.apiBaseUrl)
    return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${
      link.slug
    }`
  }

  fileVersionLabel(version: FileVersion): string {
    return SHARE_LINK_BUNDLE_FILE_VERSION_LABELS[version] ?? version
  }

  copy(link: ShareLink): void {
    if (this.clipboard.copy(this.getShareUrl(link))) {
      this.copiedID.set(link.id)
      setTimeout(() => this.copiedID.set(null), 3000)
    }
  }

  delete(link: ShareLink): void {
    this.shareLinkService.delete(link).subscribe({
      next: () => {
        if (this.links().length === 1 && this.page() > 1) {
          this.page.update((page) => page - 1)
        }
        this.toastService.showInfo($localize`Share link deleted.`)
        this.reload()
      },
      error: (error) => {
        this.toastService.showError(
          $localize`Error deleting share link.`,
          error
        )
      },
    })
  }
}
