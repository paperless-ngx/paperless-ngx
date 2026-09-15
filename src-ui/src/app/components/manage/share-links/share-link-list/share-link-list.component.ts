import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, OnInit, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { takeUntil } from 'rxjs'
import { ConfirmButtonComponent } from 'src/app/components/common/confirm-button/confirm-button.component'
import { LoadingComponentWithPermissions } from 'src/app/components/loading-component/loading.component'
import { FileVersion, ShareLink } from 'src/app/data/share-link'
import { SHARE_LINK_BUNDLE_FILE_VERSION_LABELS } from 'src/app/data/share-link-bundle'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  SortEvent,
  SortableDirective,
} from 'src/app/directives/sortable.directive'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import {
  PermissionAction,
  PermissionType,
} from 'src/app/services/permissions.service'
import { ShareLinkService } from 'src/app/services/rest/share-link.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-share-link-list',
  templateUrl: './share-link-list.component.html',
  imports: [
    CommonModule,
    ConfirmButtonComponent,
    DocumentTitlePipe,
    FormsModule,
    IfPermissionsDirective,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
    RouterModule,
    SortableDirective,
  ],
})
export class ShareLinkListComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  private readonly clipboard = inject(Clipboard)
  private readonly shareLinkService = inject(ShareLinkService)
  private readonly settingsService = inject(SettingsService)
  private readonly toastService = inject(ToastService)

  readonly links = signal<ShareLink[]>([])
  readonly total = signal(0)
  readonly page = signal(1)
  readonly sortField = signal('created')
  readonly sortReverse = signal(true)
  readonly copiedID = signal<number | null>(null)
  readonly copiedDocumentID = signal<number | null>(null)
  readonly error = signal<string | null>(null)
  readonly PermissionAction = PermissionAction
  readonly PermissionType = PermissionType

  get pageSize(): number {
    return (
      this.settingsService.get(SETTINGS_KEYS.OBJECT_LIST_SIZES)?.share_links ||
      25
    )
  }

  set pageSize(pageSize: number) {
    this.settingsService.set(SETTINGS_KEYS.OBJECT_LIST_SIZES, {
      ...this.settingsService.get(SETTINGS_KEYS.OBJECT_LIST_SIZES),
      share_links: pageSize,
    })
    this.settingsService.storeSettings().subscribe({
      next: () => {
        this.page.set(1)
        this.reload()
      },
      error: (error) => {
        this.toastService.showError($localize`Error saving settings`, error)
      },
    })
  }

  ngOnInit(): void {
    this.reload()
  }

  reload(): void {
    this.loading.set(true)
    this.error.set(null)
    this.shareLinkService
      .list(this.page(), this.pageSize, this.sortField(), this.sortReverse())
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

  onSort(event: SortEvent): void {
    this.sortField.set(event.column || 'created')
    this.sortReverse.set(event.column ? event.reverse : true)
    this.page.set(1)
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

  isExpired(expiration?: string): boolean {
    return !!expiration && Date.parse(expiration) <= Date.now()
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

  copyDocumentID(documentID: number): void {
    if (this.clipboard.copy(documentID.toString())) {
      this.copiedDocumentID.set(documentID)
      setTimeout(() => this.copiedDocumentID.set(null), 3000)
    }
  }
}
